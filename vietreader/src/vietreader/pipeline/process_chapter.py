"""process_chapter orchestrator: extract -> cache check -> match/resolve/llm/apply -> validate.

See spec §4 Phase 5 for the pseudocode this mirrors.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field, replace
from typing import Literal

from vietreader.core.applier import apply_changes
from vietreader.core.dictionary import CompiledDictionary, DictionaryEntry
from vietreader.core.matcher import match
from vietreader.core.models import Change, Policy, Span
from vietreader.core.resolver import AskDecision, resolve
from vietreader.core.validator import validate
from vietreader.db.repositories.chapter_cache import (
    ChapterCacheRepo,
    compute_raw_hash,
    compute_source_key,
)
from vietreader.db.repositories.run_log import RunLogRepo
from vietreader.extraction.base import Chapter, from_raw_text
from vietreader.extraction.fetcher import Fetcher
from vietreader.extraction.registry import Registry
from vietreader.llm.disambiguator import (
    CacheBackend,
    DisambiguationRequest,
    disambiguate_batch,
)
from vietreader.llm.provider import LLMProvider

CONTEXT_WIDTH = 60
PARAGRAPH_SEP = "\n\n"


@dataclass(frozen=True, slots=True)
class ProcessStats:
    span_count: int
    replace_count: int
    ask_count: int
    llm_calls: int
    llm_cache_hits: int
    duration_ms: float
    from_cache: bool


@dataclass(frozen=True, slots=True)
class ProcessResult:
    chapter: Chapter
    output_paragraphs: list[str]
    changelog: list[Change]
    stats: ProcessStats
    warnings: list[str]
    status: Literal["ok", "validation_failed"]
    violations: list[str] = field(default_factory=list)
    chapter_cache_id: int | None = None


def _context(paragraph: str, span: Span, width: int = CONTEXT_WIDTH) -> tuple[str, str]:
    left = paragraph[max(0, span.start - width) : span.start]
    right = paragraph[span.end : span.end + width]
    return left, right


def _change_to_dict(change: Change) -> dict:
    return asdict(change)


def _change_from_dict(data: dict) -> Change:
    return Change(**data)


async def process_chapter(
    *,
    source_url: str | None,
    raw_text: str | None,
    title: str | None,
    dictionary_entries: list[DictionaryEntry],
    dict_version_hash: str,
    prompt_version: str,
    model: str,
    provider: LLMProvider,
    chapter_cache_repo: ChapterCacheRepo,
    run_log_repo: RunLogRepo,
    llm_cache: CacheBackend | None = None,
    registry: Registry | None = None,
    fetcher: Fetcher | None = None,
    temperature: float = 0.0,
    batch_size: int = 40,
    max_retries: int = 2,
) -> ProcessResult:
    start = time.monotonic()

    # 1. extract -> Chapter (normalize happens inside from_raw_text / the extractors)
    if raw_text is not None:
        chapter = from_raw_text(raw_text, title=title)
    else:
        if source_url is None:
            raise ValueError("either source_url or raw_text must be provided")
        html = await (fetcher or Fetcher(user_agent="VietReaderBot/0.1")).fetch(source_url)
        chapter = (registry or Registry()).extract(html, source_url)

    raw_paragraphs = chapter.paragraphs
    raw_joined = PARAGRAPH_SEP.join(raw_paragraphs)
    raw_hash = compute_raw_hash(raw_joined)

    # Compile before the cache lookup as well: cache-hit statistics should describe all
    # matcher spans (including KEEP and fallback ASK), not only replacements in the changelog.
    compiled = CompiledDictionary.from_entries(dictionary_entries)

    # 2. cache_key; hit -> return cached result
    source_key = compute_source_key(raw_hash, dict_version_hash, prompt_version, model)
    cached = chapter_cache_repo.get(source_key)
    if cached is not None:
        changelog = [_change_from_dict(c) for c in json.loads(cached.changelog_json)]
        output_paragraphs = cached.output_text.split(PARAGRAPH_SEP)
        # Reopening a chapter counts as reading it: keeps the library ordered by activity.
        chapter_cache_repo.touch(cached.id)
        # The page is the authority on its own title. A chapter cached before the extractor
        # learned to read chapter headings kept a stale title (often the whole novel's name);
        # refresh it here so old entries heal on the next visit instead of staying wrong.
        if source_url and chapter.title and chapter.title != cached.title:
            chapter_cache_repo.set_title(cached.id, chapter.title)
            cached = replace(cached, title=chapter.title)
        # A pasted chapter has no navigation of its own; recover whatever was captured when
        # the chapter was first extracted so "next chapter" still works from the library.
        if chapter.next_url is None and chapter.prev_url is None:
            chapter = replace(chapter, next_url=cached.next_url, prev_url=cached.prev_url)
        cached_spans = [match(paragraph, compiled) for paragraph in raw_paragraphs]
        cached_ask_count = sum(
            span.policy is Policy.ASK for spans in cached_spans for span in spans
        )
        duration_ms = (time.monotonic() - start) * 1000
        stats = ProcessStats(
            span_count=sum(len(spans) for spans in cached_spans),
            replace_count=sum(1 for c in changelog if c.source == "replace"),
            ask_count=cached_ask_count,
            llm_calls=0,
            llm_cache_hits=0,
            duration_ms=duration_ms,
            from_cache=True,
        )
        return ProcessResult(
            chapter=chapter,
            output_paragraphs=output_paragraphs,
            changelog=changelog,
            stats=stats,
            warnings=[],
            status="ok",
            chapter_cache_id=cached.id,
        )

    # 3. compile dictionary (CompiledDictionary.from_entries recomputes version_hash; caller
    #    is responsible for keeping dict_version_hash in sync -- see Phase 6 wiring)
    # 4a. match, per paragraph
    spans_by_para: dict[int, list[Span]] = {}
    for index, paragraph in enumerate(raw_paragraphs):
        spans_by_para[index] = match(paragraph, compiled)

    # 4b. collect ASK spans across the whole chapter for one batched LLM call
    ask_requests: list[DisambiguationRequest] = []
    for para_index, spans in spans_by_para.items():
        paragraph = raw_paragraphs[para_index]
        for span_index, span in enumerate(spans):
            entry = compiled.entries_by_id[span.entry_id]
            if entry.policy is not Policy.ASK:
                continue
            left, right = _context(paragraph, span)
            ask_requests.append(
                DisambiguationRequest(
                    id=f"p{para_index}_s{span_index}",
                    span=span,
                    entry=entry,
                    left=left,
                    right=right,
                )
            )

    outcome = await disambiguate_batch(
        ask_requests,
        provider,
        model=model,
        prompt_version=prompt_version,
        temperature=temperature,
        batch_size=batch_size,
        max_retries=max_retries,
        cache=llm_cache,
    )
    decisions_by_id: dict[str, AskDecision | None] = {r.id: r.decision for r in outcome.results}
    warnings = [r.warning for r in outcome.results if r.warning]

    # 4c. resolve + apply, per paragraph
    changelog: list[Change] = []
    for para_index, spans in spans_by_para.items():

        def ask_resolver(
            span: Span, p_index: int, _spans: list[Span] = spans, _para_index: int = para_index
        ) -> AskDecision | None:
            span_index = _spans.index(span)
            return decisions_by_id.get(f"p{_para_index}_s{span_index}")

        changelog.extend(resolve(para_index, spans, compiled, ask_resolver))

    output_paragraphs = apply_changes(raw_paragraphs, changelog)

    # 5. validate
    result = validate(raw_paragraphs, output_paragraphs, changelog, compiled, spans_by_para)
    duration_ms = (time.monotonic() - start) * 1000

    for warning in warnings:
        run_log_repo.log(stage="disambiguate", level="WARN", message=warning)
    for warning in result.warnings:
        run_log_repo.log(stage="validate", level="WARN", message=warning)

    stats = ProcessStats(
        span_count=sum(len(s) for s in spans_by_para.values()),
        replace_count=sum(1 for c in changelog if c.source == "replace"),
        ask_count=len(ask_requests),
        llm_calls=outcome.llm_calls,
        llm_cache_hits=outcome.cache_hits,
        duration_ms=duration_ms,
        from_cache=False,
    )

    if not result.ok:
        for violation in result.violations:
            run_log_repo.log(stage="validate", level="ERROR", message=violation)
        return ProcessResult(
            chapter=chapter,
            output_paragraphs=raw_paragraphs,
            changelog=changelog,
            stats=stats,
            warnings=warnings + result.warnings,
            status="validation_failed",
            violations=result.violations,
        )

    # 6. cache + return
    cached_row = chapter_cache_repo.put(
        source_key=source_key,
        url=source_url,
        title=chapter.title,
        raw_hash=raw_hash,
        raw_text=raw_joined,
        output_text=PARAGRAPH_SEP.join(output_paragraphs),
        changelog_json=json.dumps([_change_to_dict(c) for c in changelog], ensure_ascii=False),
        dict_version_hash=dict_version_hash,
        prompt_version=prompt_version,
        model=model,
        next_url=chapter.next_url,
        prev_url=chapter.prev_url,
    )

    return ProcessResult(
        chapter=chapter,
        output_paragraphs=output_paragraphs,
        changelog=changelog,
        stats=stats,
        warnings=warnings + result.warnings,
        status="ok",
        chapter_cache_id=cached_row.id,
    )

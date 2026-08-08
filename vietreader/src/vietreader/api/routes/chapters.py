"""POST /api/chapters/process, GET /api/chapters/{id}."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from vietreader.api.deps import AppState, get_app_state, get_session
from vietreader.core.dictionary import CompiledDictionary
from vietreader.db.repositories.chapter_cache import ChapterCacheRepo
from vietreader.db.repositories.dictionary import DictionaryRepo
from vietreader.db.repositories.llm_cache import LLMCacheRepo
from vietreader.db.repositories.run_log import RunLogRepo
from vietreader.llm.disambiguator import PROMPT_VERSION
from vietreader.pipeline.process_chapter import process_chapter

router = APIRouter(prefix="/api/chapters", tags=["chapters"])


class ProcessChapterRequest(BaseModel):
    url: str | None = None
    raw_text: str | None = None
    title: str | None = None

    @model_validator(mode="after")
    def _require_url_or_raw_text(self) -> ProcessChapterRequest:
        if not self.url and not self.raw_text:
            raise ValueError("either 'url' or 'raw_text' must be provided")
        return self


class ChangeOut(BaseModel):
    para_index: int
    start: int
    end: int
    original: str
    replacement: str
    entry_id: int
    source: str


class StatsOut(BaseModel):
    span_count: int
    replace_count: int
    ask_count: int
    llm_calls: int
    llm_cache_hits: int
    duration_ms: float
    from_cache: bool


class ProcessChapterResponse(BaseModel):
    id: int | None = None
    title: str
    paragraphs: list[str]
    changelog: list[ChangeOut]
    stats: StatsOut
    warnings: list[str]
    status: Literal["ok", "validation_failed"]
    violations: list[str] = []
    next_url: str | None = None
    prev_url: str | None = None


class ChapterCacheOut(BaseModel):
    id: int
    title: str
    output_text: str
    url: str | None
    model: str
    prompt_version: str


@router.post("/process", response_model=ProcessChapterResponse)
async def process(
    body: ProcessChapterRequest,
    session: Session = Depends(get_session),
    state: AppState = Depends(get_app_state),
) -> ProcessChapterResponse:
    dict_repo = DictionaryRepo(session)
    entries = dict_repo.list_enabled()
    dict_version_hash = CompiledDictionary.from_entries(entries).version_hash

    result = await process_chapter(
        source_url=body.url,
        raw_text=body.raw_text,
        title=body.title,
        dictionary_entries=entries,
        dict_version_hash=dict_version_hash,
        prompt_version=PROMPT_VERSION,
        model=state.settings.llm_model,
        provider=state.provider,
        chapter_cache_repo=ChapterCacheRepo(session),
        run_log_repo=RunLogRepo(session),
        llm_cache=LLMCacheRepo(session),
        registry=state.registry,
        fetcher=state.fetcher,
        temperature=state.settings.llm_temperature,
        batch_size=state.settings.llm_batch_size,
        max_retries=state.settings.llm_max_retries,
    )
    session.commit()

    return ProcessChapterResponse(
        id=result.chapter_cache_id,
        title=result.chapter.title,
        paragraphs=result.output_paragraphs,
        changelog=[ChangeOut(**asdict(c)) for c in result.changelog],
        stats=StatsOut(**asdict(result.stats)),
        warnings=result.warnings,
        status=result.status,
        violations=result.violations,
        next_url=result.chapter.next_url,
        prev_url=result.chapter.prev_url,
    )


@router.get("/{chapter_id}", response_model=ChapterCacheOut)
async def get_chapter(chapter_id: int, session: Session = Depends(get_session)) -> ChapterCacheOut:
    repo = ChapterCacheRepo(session)
    cached = repo.get_by_id(chapter_id)
    if cached is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} not found in cache")
    return ChapterCacheOut(
        id=cached.id,
        title=cached.title,
        output_text=cached.output_text,
        url=cached.url,
        model=cached.model,
        prompt_version=cached.prompt_version,
    )

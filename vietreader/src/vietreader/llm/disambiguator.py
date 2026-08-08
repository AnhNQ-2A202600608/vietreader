"""L3 Disambiguator: batching, retry, parsing, fallback, cache interface (spec §3.4).

Cache semantics:
- Top-level JSON parse failure (or a provider exception, e.g. timeout) is a whole-batch
  failure: retried up to `max_retries` times, then every item in that batch falls back.
- Once a response parses as a JSON array, each item is judged independently: a missing id
  or an out-of-range `choice` only falls back *that* item — the rest of the batch is used
  as-is, with no extra retry. (This reading resolves an ambiguity in the work order text,
  which describes both failure modes with the same words; see DECISIONS.md Phase 3.)
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol

from vietreader.core.dictionary import DictionaryEntry
from vietreader.core.models import Span
from vietreader.core.resolver import AskDecision
from vietreader.llm.provider import DisambiguationItem, LLMProvider

PROMPT_VERSION = "v1"


class CacheBackend(Protocol):
    def get(self, key: str) -> int | None: ...

    def set(self, key: str, choice_index: int) -> None: ...


@dataclass(frozen=True, slots=True)
class DisambiguationRequest:
    id: str
    span: Span
    entry: DictionaryEntry
    left: str
    right: str


@dataclass(frozen=True, slots=True)
class DisambiguationResult:
    id: str
    decision: AskDecision | None  # None => fallback to KEEP (no change emitted)
    warning: str | None = None


def cache_key(
    prompt_version: str, model: str, term: str, candidates: list[str], left: str, right: str
) -> str:
    payload = prompt_version + model + term + "|".join(candidates) + left + right
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _chunk(items: list[DisambiguationRequest], size: int) -> Iterator[list[DisambiguationRequest]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _try_parse_choices(
    raw: str, batch: list[DisambiguationRequest]
) -> dict[str, int] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None

    by_id = {r.id: r for r in batch}
    choices: dict[str, int] = {}
    for item in data:
        if not isinstance(item, dict) or "id" not in item or "choice" not in item:
            continue
        req = by_id.get(item["id"])
        if req is None:
            continue
        choice = item["choice"]
        if not isinstance(choice, int) or isinstance(choice, bool):
            continue
        if not (0 <= choice < len(req.entry.candidates)):
            continue
        choices[req.id] = choice
    return choices


async def _call_batch_with_retry(
    batch: list[DisambiguationRequest],
    provider: LLMProvider,
    *,
    temperature: float,
    max_tokens: int,
    max_retries: int,
) -> dict[str, int]:
    items = [
        DisambiguationItem(
            id=r.id, term=r.entry.surface, left=r.left, right=r.right, candidates=r.entry.candidates
        )
        for r in batch
    ]
    for _attempt in range(max_retries + 1):
        try:
            raw = await provider.disambiguate(items, temperature=temperature, max_tokens=max_tokens)
        except Exception:  # provider timeout/network error: treat as a failed attempt
            continue
        parsed = _try_parse_choices(raw, batch)
        if parsed is not None:
            return parsed
    return {}


def _build_decision(req: DisambiguationRequest, choice_index: int) -> AskDecision:
    source: Literal["llm"] = "llm"
    return AskDecision(
        replacement=req.entry.candidates[choice_index], source=source, choice_index=choice_index
    )


async def disambiguate_batch(
    requests: list[DisambiguationRequest],
    provider: LLMProvider,
    *,
    model: str,
    prompt_version: str = PROMPT_VERSION,
    temperature: float = 0.0,
    batch_size: int = 40,
    max_retries: int = 2,
    cache: CacheBackend | None = None,
) -> list[DisambiguationResult]:
    """Resolve every ASK request. Never calls the provider when `requests` is empty."""
    if not requests:
        return []

    results: dict[str, DisambiguationResult] = {}
    keys: dict[str, str] = {}
    to_call: list[DisambiguationRequest] = []

    for req in requests:
        key = cache_key(
            prompt_version, model, req.entry.surface, req.entry.candidates, req.left, req.right
        )
        keys[req.id] = key
        cached_choice = cache.get(key) if cache is not None else None
        if cached_choice is not None:
            results[req.id] = DisambiguationResult(
                id=req.id, decision=_build_decision(req, cached_choice)
            )
        else:
            to_call.append(req)

    for batch in _chunk(to_call, batch_size):
        max_tokens = batch_size * 40
        choices = await _call_batch_with_retry(
            batch, provider, temperature=temperature, max_tokens=max_tokens, max_retries=max_retries
        )
        for req in batch:
            choice_index = choices.get(req.id)
            if choice_index is None:
                results[req.id] = DisambiguationResult(
                    id=req.id,
                    decision=None,
                    warning=(
                        f"LLM fallback for span {req.id!r} (term={req.entry.surface!r}): "
                        "no valid choice returned by provider"
                    ),
                )
                continue
            if cache is not None:
                cache.set(keys[req.id], choice_index)
            results[req.id] = DisambiguationResult(
                id=req.id, decision=_build_decision(req, choice_index)
            )

    return [results[req.id] for req in requests]

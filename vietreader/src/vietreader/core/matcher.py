"""L1 Matcher: Aho-Corasick span matching over the compiled dictionary. Deterministic, no LLM."""

from __future__ import annotations

from vietreader.core.dictionary import CompiledDictionary, DictionaryEntry
from vietreader.core.models import Policy, Span


class MatcherError(RuntimeError):
    """Raised when matching cannot preserve original-text offsets (see spec §3.1)."""


def _is_word_char(ch: str) -> bool:
    return ch.isalpha() or ch.isdigit() or ch == "_"


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _sort_key(item: tuple[int, int, int, DictionaryEntry]) -> tuple[int, int, int, int]:
    start, end, entry_id, entry = item
    length = end - start
    return (-length, -entry.priority, start, entry_id)


def match(paragraph: str, dictionary: CompiledDictionary) -> list[Span]:
    """Match `paragraph` (already NFC-normalized) against the compiled dictionary.

    Returns non-overlapping spans sorted by start, per spec §3.2:
    1. Raw Aho-Corasick matches.
    2. Word-boundary filter.
    3. KEEP spans claimed first, locking their region.
    4. Longest-match wins among the rest.
    5. Deterministic tie-break: priority desc, start asc, entry_id asc.
    """
    if not dictionary.entries_by_id:
        return []

    lowered = paragraph.lower()
    if len(lowered) != len(paragraph):
        raise MatcherError(
            "case-folding changed string length; cannot preserve span offsets "
            f"(len(original)={len(paragraph)}, len(lowered)={len(lowered)}). "
            "This is a BLOCKER per spec §3.1 — fallback matching strategy required."
        )

    raw_matches: list[tuple[int, int, int]] = []
    for end_index, entry_id in dictionary.automaton.iter(lowered):
        entry = dictionary.entries_by_id[entry_id]
        start = end_index - len(entry.surface) + 1
        end = end_index + 1
        raw_matches.append((start, end, entry_id))

    boundary_ok: list[tuple[int, int, int, DictionaryEntry]] = []
    for start, end, entry_id in raw_matches:
        before_ok = start == 0 or not _is_word_char(paragraph[start - 1])
        after_ok = end == len(paragraph) or not _is_word_char(paragraph[end])
        if before_ok and after_ok:
            boundary_ok.append((start, end, entry_id, dictionary.entries_by_id[entry_id]))

    keep_candidates = sorted(
        (m for m in boundary_ok if m[3].policy is Policy.KEEP), key=_sort_key
    )
    other_candidates = sorted(
        (m for m in boundary_ok if m[3].policy is not Policy.KEEP), key=_sort_key
    )

    claimed: list[tuple[int, int]] = []
    keep_intervals: list[tuple[int, int]] = []
    accepted: list[tuple[int, int, int, DictionaryEntry]] = []

    for start, end, entry_id, entry in keep_candidates:
        if any(_overlaps(start, end, cs, ce) for cs, ce in claimed):
            continue
        claimed.append((start, end))
        keep_intervals.append((start, end))
        accepted.append((start, end, entry_id, entry))

    for start, end, entry_id, entry in other_candidates:
        if any(_overlaps(start, end, ks, ke) for ks, ke in keep_intervals):
            continue
        if any(_overlaps(start, end, cs, ce) for cs, ce in claimed):
            continue
        claimed.append((start, end))
        accepted.append((start, end, entry_id, entry))

    accepted.sort(key=lambda item: item[0])

    return [
        Span(start=s, end=e, text=paragraph[s:e], entry_id=eid, policy=entry.policy)
        for s, e, eid, entry in accepted
    ]

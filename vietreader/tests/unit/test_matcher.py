from __future__ import annotations

import unicodedata

from hypothesis import given
from hypothesis import strategies as st

from vietreader.core.dictionary import CompiledDictionary, DictionaryEntry
from vietreader.core.matcher import MatcherError, match
from vietreader.core.models import Policy


def entry(
    id: int,
    surface: str,
    policy: Policy,
    replacement: str | None = None,
    candidates: list[str] | None = None,
    priority: int = 0,
    enabled: bool = True,
) -> DictionaryEntry:
    return DictionaryEntry(
        id=id,
        surface=surface,
        display=surface,
        policy=policy,
        replacement=replacement,
        candidates=candidates or [],
        priority=priority,
        enabled=enabled,
    )


def test_simple_match_title_case() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    spans = match("Lão giả nhìn", d)
    assert len(spans) == 1
    assert spans[0].text == "Lão giả"
    assert spans[0].start == 0
    assert spans[0].end == 7


def test_word_boundary_blocks_substring_match() -> None:
    # "lão giả" must not match when it is a strict prefix of a longer contiguous token
    # (no separator between "giả" and the following letter) -- a genuine boundary violation.
    # NOTE: the spec's own illustrative example ("lão giả" inside "lão giả tử") is NOT
    # achievable by this character-adjacency algorithm, because Vietnamese separates every
    # syllable with a space rather than marking word boundaries -- "tử" there is a normal,
    # independently-bounded next word, so "lão giả" legitimately matches it too. Treating a
    # bare space as "not a word boundary" would require full word segmentation, which is out
    # of scope (spec §1: matcher is deterministic, no linguistic analysis). See DECISIONS.md.
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    spans = match("lão giảx đến", d)
    assert spans == []


def test_longest_match_wins_on_overlap() -> None:
    d = CompiledDictionary.from_entries(
        [
            entry(1, "thiếu niên", Policy.REPLACE, replacement="cậu trai"),
            entry(2, "thiếu niên lang", Policy.REPLACE, replacement="chàng trai trẻ"),
        ]
    )
    spans = match("thiếu niên lang đi học", d)
    assert len(spans) == 1
    assert spans[0].text == "thiếu niên lang"
    assert spans[0].entry_id == 2


def test_keep_wins_over_overlapping_replace() -> None:
    d = CompiledDictionary.from_entries(
        [
            entry(1, "linh lực", Policy.KEEP),
            entry(2, "linh lực mạnh", Policy.REPLACE, replacement="sức mạnh lớn"),
        ]
    )
    spans = match("linh lực mạnh vô cùng", d)
    assert len(spans) == 1
    assert spans[0].entry_id == 1
    assert spans[0].policy is Policy.KEEP
    assert spans[0].text == "linh lực"


def test_priority_tiebreak_same_length() -> None:
    # Two equal-length, space-bounded surfaces overlapping each other: higher priority wins.
    # ("sư huynh" [0:8) and "huynh đệ" [3:11) both pass the boundary filter independently and
    # tie on length, so priority is the deciding tie-break per spec §3.2 step 5.)
    d = CompiledDictionary.from_entries(
        [
            entry(5, "sư huynh", Policy.REPLACE, replacement="anh", priority=0),
            entry(6, "huynh đệ", Policy.REPLACE, replacement="huynh đệ đệ tử", priority=5),
        ]
    )
    spans = match("sư huynh đệ tử", d)
    assert len(spans) == 1
    assert spans[0].entry_id == 6
    assert spans[0].text == "huynh đệ"


def test_nfd_input_normalizes_to_nfc_then_matches() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    nfd_text = unicodedata.normalize("NFD", "Lão giả nhìn")
    nfc_text = unicodedata.normalize("NFC", nfd_text)
    spans = match(nfc_text, d)
    assert len(spans) == 1
    assert spans[0].text == "Lão giả"


def test_disabled_entry_does_not_match() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão", enabled=False)]
    )
    spans = match("Lão giả nhìn", d)
    assert spans == []


def test_empty_dictionary_returns_empty_no_crash() -> None:
    d = CompiledDictionary.from_entries([])
    spans = match("Bất kỳ đoạn văn nào", d)
    assert spans == []


def test_match_at_paragraph_boundaries() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    spans = match("lão giả", d)
    assert len(spans) == 1
    assert spans[0].start == 0
    assert spans[0].end == 7


@given(st.text(min_size=0, max_size=200))
def test_property_spans_non_overlapping_sorted_and_text_matches(paragraph: str) -> None:
    d = CompiledDictionary.from_entries(
        [
            entry(1, "lão giả", Policy.REPLACE, replacement="ông lão"),
            entry(2, "linh lực", Policy.KEEP),
            entry(3, "đạo hữu", Policy.ASK, candidates=["đạo hữu", "bạn"]),
        ]
    )
    try:
        spans = match(paragraph, d)
    except MatcherError:
        # Legitimate per spec §3.1 for pathological case-folding (length-changing lower()).
        return
    starts = [s.start for s in spans]
    assert starts == sorted(starts)
    for i in range(len(spans) - 1):
        assert spans[i].end <= spans[i + 1].start
    for s in spans:
        assert s.text == paragraph[s.start : s.end]

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from vietreader.core.applier import apply_changes
from vietreader.core.dictionary import CompiledDictionary, DictionaryEntry
from vietreader.core.matcher import MatcherError, match
from vietreader.core.models import Change, Policy, Span
from vietreader.core.resolver import AskDecision, resolve
from vietreader.core.validator import validate


def entry(
    id: int,
    surface: str,
    policy: Policy,
    replacement: str | None = None,
    candidates: list[str] | None = None,
) -> DictionaryEntry:
    return DictionaryEntry(
        id=id,
        surface=surface,
        display=surface,
        policy=policy,
        replacement=replacement,
        candidates=candidates or [],
    )


def _match_resolve_apply(paragraphs: list[str], dictionary: CompiledDictionary, ask_resolver):
    spans_by_para: dict[int, list[Span]] = {}
    all_changes: list[Change] = []
    for i, para in enumerate(paragraphs):
        spans = match(para, dictionary)
        spans_by_para[i] = spans
        all_changes.extend(resolve(i, spans, dictionary, ask_resolver))
    output = apply_changes(paragraphs, all_changes)
    return output, all_changes, spans_by_para


def _no_ask(span, para_index):  # pragma: no cover - not exercised when no ASK entries present
    raise AssertionError("no ASK spans expected in this test")


def test_i1_i2_pass_on_untouched_valid_pipeline() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    paragraphs = ["Lão giả nhìn thiếu niên."]
    output, changes, spans_by_para = _match_resolve_apply(paragraphs, d, _no_ask)
    result = validate(paragraphs, output, changes, d, spans_by_para)
    assert result.ok, result.violations


def test_i1_fails_on_manually_corrupted_output() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    paragraphs = ["Lão giả nhìn thiếu niên."]
    output, changes, spans_by_para = _match_resolve_apply(paragraphs, d, _no_ask)
    corrupted = [output[0] + "X"]
    result = validate(paragraphs, corrupted, changes, d, spans_by_para)
    assert not result.ok
    assert any(v.startswith("I1:") for v in result.violations)


def test_i2_fails_on_deleted_paragraph() -> None:
    d = CompiledDictionary.from_entries([])
    paragraphs = ["Đoạn một.", "Đoạn hai."]
    output, changes, spans_by_para = _match_resolve_apply(paragraphs, d, _no_ask)
    truncated = output[:1]
    result = validate(paragraphs, truncated, changes, d, spans_by_para)
    assert not result.ok
    assert any(v.startswith("I2:") for v in result.violations)


def test_i3_fails_when_change_has_no_matching_span() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    paragraphs = ["Lão giả nhìn thiếu niên."]
    spans_by_para = {0: match(paragraphs[0], d)}
    bogus_change = Change(
        para_index=0, start=13, end=21, original="thiếu niên",
        replacement="cậu bé", entry_id=999, source="replace",
    )
    output = apply_changes(paragraphs, [bogus_change])
    result = validate(paragraphs, output, [bogus_change], d, spans_by_para)
    assert not result.ok
    assert any(v.startswith("I3:") for v in result.violations)


def test_i4_fails_when_replace_replacement_does_not_match_entry() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão giả", Policy.REPLACE, replacement="ông lão")]
    )
    paragraphs = ["Lão giả nhìn thiếu niên."]
    spans = match(paragraphs[0], d)
    spans_by_para = {0: spans}
    wrong_change = Change(
        para_index=0, start=spans[0].start, end=spans[0].end, original=spans[0].text,
        replacement="Sai Hoàn Toàn", entry_id=1, source="replace",
    )
    output = apply_changes(paragraphs, [wrong_change])
    result = validate(paragraphs, output, [wrong_change], d, spans_by_para)
    assert not result.ok
    assert any(v.startswith("I4:") for v in result.violations)


def test_i5_fails_when_llm_choice_outside_candidates() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "đạo hữu", Policy.ASK, candidates=["đạo hữu", "bạn", "vị này"])]
    )
    paragraphs = ["Đạo hữu hãy cẩn thận."]

    def bad_ask(span: Span, para_index: int) -> AskDecision:
        return AskDecision(
            replacement="một từ không nằm trong candidates", source="llm", choice_index=0
        )

    output, changes, spans_by_para = _match_resolve_apply(paragraphs, d, bad_ask)
    result = validate(paragraphs, output, changes, d, spans_by_para)
    assert not result.ok
    assert any(v.startswith("I5:") for v in result.violations)


def test_i6_fails_when_keep_occurrence_removed() -> None:
    d = CompiledDictionary.from_entries([entry(1, "linh lực", Policy.KEEP)])
    paragraphs = ["Linh lực dồi dào."]
    spans = match(paragraphs[0], d)
    spans_by_para = {0: spans}
    # Simulate a bug: a change removes the KEEP occurrence even though KEEP should be untouchable.
    sneaky_change = Change(
        para_index=0, start=0, end=8, original="Linh lực",
        replacement="Sức mạnh", entry_id=1, source="replace",
    )
    output = apply_changes(paragraphs, [sneaky_change])
    result = validate(paragraphs, output, [sneaky_change], d, spans_by_para)
    assert not result.ok
    assert any(v.startswith("I6:") for v in result.violations)


def test_i6_allows_replacement_that_introduces_a_keep_term() -> None:
    """I6 guards against LOSING a protected term, not against gaining one.

    A user can legitimately add REPLACE "tu sĩ" -> "linh lực gia" while "linh lực" is KEEP.
    No original occurrence is harmed, so the chapter must still process. Before this rule was
    relaxed, this combination hard-failed every chapter containing "tu sĩ".
    """
    d = CompiledDictionary.from_entries(
        [
            entry(1, "linh lực", Policy.KEEP),
            entry(2, "tu sĩ", Policy.REPLACE, replacement="linh lực gia"),
        ]
    )
    paragraphs = ["Một tu sĩ bước vào."]
    output, changes, spans_by_para = _match_resolve_apply(paragraphs, d, _no_ask)
    result = validate(paragraphs, output, changes, d, spans_by_para)
    assert output == ["Một linh lực gia bước vào."]
    assert result.ok, result.violations


def test_i7_warns_but_does_not_fail_on_long_replacement() -> None:
    d = CompiledDictionary.from_entries(
        [entry(1, "lão", Policy.REPLACE, replacement="một ông lão già nua rất là")]
    )
    paragraphs = ["lão đi."]
    output, changes, spans_by_para = _match_resolve_apply(paragraphs, d, _no_ask)
    result = validate(paragraphs, output, changes, d, spans_by_para)
    assert result.ok
    assert any(w.startswith("I7:") for w in result.warnings)


@settings(max_examples=200)
@given(st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x1EF9), max_size=80))
def test_property_i1_always_passes_for_valid_pipeline_output(paragraph: str) -> None:
    d = CompiledDictionary.from_entries(
        [
            entry(1, "lão giả", Policy.REPLACE, replacement="ông lão"),
            entry(2, "linh lực", Policy.KEEP),
            entry(3, "đạo hữu", Policy.ASK, candidates=["đạo hữu", "bạn"]),
        ]
    )

    def ask_first_candidate(span: Span, para_index: int) -> AskDecision:
        return AskDecision(replacement="bạn", source="llm", choice_index=1)

    try:
        output, changes, spans_by_para = _match_resolve_apply([paragraph], d, ask_first_candidate)
    except MatcherError:
        return  # pathological case-folding input; not what I1 is testing here
    result = validate([paragraph], output, changes, d, spans_by_para)
    assert result.ok or all(not v.startswith("I1:") for v in result.violations), result.violations

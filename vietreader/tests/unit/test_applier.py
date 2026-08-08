from __future__ import annotations

from vietreader.core.applier import apply_changes
from vietreader.core.models import Change
from vietreader.core.validator import reconstruct


def test_round_trip_apply_then_reconstruct() -> None:
    paragraphs = ["Lão giả nhìn thiếu niên."]
    changes = [
        Change(
            para_index=0,
            start=0,
            end=7,
            original="Lão giả",
            replacement="Ông lão",
            entry_id=1,
            source="replace",
        )
    ]
    output = apply_changes(paragraphs, changes)
    assert output == ["Ông lão nhìn thiếu niên."]
    assert reconstruct(output, changes) == paragraphs


def test_multiple_changes_varying_replacement_length_reconstructs() -> None:
    paragraphs = ["A lão giả B thiếu niên C linh lực D."]
    changes = [
        Change(
            para_index=0, start=2, end=9, original="lão giả",
            replacement="ông cụ già nua", entry_id=1, source="replace",
        ),
        Change(
            para_index=0, start=12, end=22, original="thiếu niên",
            replacement="cậu", entry_id=2, source="replace",
        ),
        Change(
            para_index=0, start=25, end=33, original="linh lực",
            replacement="mana", entry_id=3, source="replace",
        ),
    ]
    output = apply_changes(paragraphs, changes)
    assert reconstruct(output, changes) == paragraphs


def test_changes_at_start_and_end_of_paragraph() -> None:
    paragraphs = ["lão giả đi bộ về nhà linh lực"]
    changes = [
        Change(
            para_index=0, start=0, end=7, original="lão giả",
            replacement="ông cụ", entry_id=1, source="replace",
        ),
        Change(
            para_index=0, start=21, end=29, original="linh lực",
            replacement="mana", entry_id=2, source="replace",
        ),
    ]
    output = apply_changes(paragraphs, changes)
    assert output == ["ông cụ đi bộ về nhà mana"]
    assert reconstruct(output, changes) == paragraphs

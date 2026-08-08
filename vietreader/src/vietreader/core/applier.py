"""L4 Applier: applies Change[] to paragraphs to produce output text."""

from __future__ import annotations

from collections import defaultdict

from vietreader.core.models import Change


class ApplierError(RuntimeError):
    """Raised when changes overlap within a paragraph (matcher/resolver contract violation)."""


def apply_changes(paragraphs: list[str], changes: list[Change]) -> list[str]:
    by_para: dict[int, list[Change]] = defaultdict(list)
    for change in changes:
        by_para[change.para_index].append(change)

    output: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        para_changes = sorted(by_para.get(index, []), key=lambda c: c.start)
        output.append(_apply_to_paragraph(paragraph, para_changes))
    return output


def _apply_to_paragraph(paragraph: str, changes: list[Change]) -> str:
    parts: list[str] = []
    cursor = 0
    for change in changes:
        if change.start < cursor:
            raise ApplierError(
                f"overlapping changes at paragraph offset {change.start} (cursor={cursor})"
            )
        parts.append(paragraph[cursor : change.start])
        parts.append(change.replacement)
        cursor = change.end
    parts.append(paragraph[cursor:])
    return "".join(parts)

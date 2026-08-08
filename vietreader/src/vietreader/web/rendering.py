"""Server-side rendering helper: wraps changed spans in output paragraphs with
<span class="changed" data-original="..."> for the reader UI's highlight toggle."""

from __future__ import annotations

from collections import defaultdict
from html import escape

from vietreader.core.applier import output_positions
from vietreader.core.models import Change


def render_paragraphs_html(output_paragraphs: list[str], changelog: list[Change]) -> list[str]:
    by_para: dict[int, list[Change]] = defaultdict(list)
    for change in changelog:
        by_para[change.para_index].append(change)

    rendered: list[str] = []
    for index, paragraph in enumerate(output_paragraphs):
        changes = sorted(by_para.get(index, []), key=lambda c: c.start)
        positioned = output_positions(changes)

        parts: list[str] = []
        cursor = 0
        for out_start, out_end, change in positioned:
            parts.append(escape(paragraph[cursor:out_start]))
            parts.append(
                f'<span class="changed" data-source="{escape(change.source)}" '
                f'data-original="{escape(change.original)}">'
                f"{escape(paragraph[out_start:out_end])}</span>"
            )
            cursor = out_end
        parts.append(escape(paragraph[cursor:]))
        rendered.append("".join(parts))

    return rendered

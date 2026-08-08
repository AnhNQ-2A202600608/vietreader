"""Text normalization shared by extraction (L0) and the pipeline's raw_hash (spec §3.1).

Applied to every piece of text entering the system, BEFORE raw_hash is computed:
NFC unicode normalization, CRLF -> LF, strip trailing whitespace per line, collapse 3+
consecutive blank lines down to 2.
"""

from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    unified_newlines = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified_newlines.split("\n")]
    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return unicodedata.normalize("NFC", collapsed)


def split_paragraphs(text: str) -> list[str]:
    """Split already-normalized text into paragraphs on blank-line boundaries."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

"""Chapter (re-exported from core) + extractor Protocol + from_raw_text escape hatch.

Chapter itself lives in core/models.py (per repo layout §1.2, comment on core/models.py) so
that core stays the single source of truth for the type; this module just re-exports it
alongside the extraction-specific Protocol and error types, per Phase 4 deliverables.
"""

from __future__ import annotations

from typing import Protocol

from vietreader.core.models import Chapter
from vietreader.core.normalize import normalize_text, split_paragraphs
from vietreader.core.series import infer_chapter_title

__all__ = ["Chapter", "Extractor", "ExtractionError", "from_raw_text"]


class ExtractionError(RuntimeError):
    """Raised when HTML cannot be parsed into a Chapter (empty/broken markup, no content found)."""


class Extractor(Protocol):
    def extract(self, html: str, source_url: str) -> Chapter: ...


def from_raw_text(text: str, title: str | None = None) -> Chapter:
    """Escape hatch for pasted text: bypasses fetch/parse entirely (spec Phase 4)."""
    normalized = normalize_text(text)
    paragraphs = split_paragraphs(normalized)
    # Copying from many reading sites produces one visual paragraph per line but no blank
    # lines.  Rendering that as one paragraph collapses every newline into a wall of text.
    # Only use the adaptive path when there are no explicit blank-line boundaries, and require
    # at least three substantial lines so ordinary manually wrapped prose remains intact.
    if len(paragraphs) == 1:
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        substantial = [line for line in lines if len(line) >= 20]
        if len(lines) >= 3 and len(substantial) / len(lines) >= 0.6:
            paragraphs = lines
    normalized_title = infer_chapter_title(title, None, paragraphs)
    if not (title or "").strip() and paragraphs:
        opening = " ".join(paragraphs[0].split()).lstrip("# ").strip()
        if opening == normalized_title:
            # The inferred heading is rendered separately as the chapter title; keeping the
            # same line in the body would show it twice.
            paragraphs = paragraphs[1:]
    return Chapter(
        title=normalized_title,
        paragraphs=paragraphs,
        next_url=None,
        prev_url=None,
        source_url=None,
    )

"""Chapter (re-exported from core) + extractor Protocol + from_raw_text escape hatch.

Chapter itself lives in core/models.py (per repo layout §1.2, comment on core/models.py) so
that core stays the single source of truth for the type; this module just re-exports it
alongside the extraction-specific Protocol and error types, per Phase 4 deliverables.
"""

from __future__ import annotations

from typing import Protocol

from vietreader.core.models import Chapter
from vietreader.core.normalize import normalize_text, split_paragraphs

__all__ = ["Chapter", "Extractor", "ExtractionError", "from_raw_text"]


class ExtractionError(RuntimeError):
    """Raised when HTML cannot be parsed into a Chapter (empty/broken markup, no content found)."""


class Extractor(Protocol):
    def extract(self, html: str, source_url: str) -> Chapter: ...


def from_raw_text(text: str, title: str | None = None) -> Chapter:
    """Escape hatch for pasted text: bypasses fetch/parse entirely (spec Phase 4)."""
    normalized = normalize_text(text)
    paragraphs = split_paragraphs(normalized)
    normalized_title = normalize_text(title) if title else ""
    return Chapter(
        title=normalized_title,
        paragraphs=paragraphs,
        next_url=None,
        prev_url=None,
        source_url=None,
    )

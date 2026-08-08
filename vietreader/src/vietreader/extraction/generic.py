"""Generic trafilatura-based fallback extractor, used when no site adapter matches the domain."""

from __future__ import annotations

import trafilatura

from vietreader.core.models import Chapter
from vietreader.core.normalize import normalize_text, split_paragraphs
from vietreader.extraction.base import ExtractionError


class GenericExtractor:
    def extract(self, html: str, source_url: str) -> Chapter:
        if not html or not html.strip():
            raise ExtractionError(f"empty HTML input for {source_url!r}")

        result = trafilatura.bare_extraction(html, url=source_url, with_metadata=True)
        if not result or not result.get("text"):
            raise ExtractionError(f"trafilatura found no extractable content for {source_url!r}")

        title = normalize_text(result.get("title") or "")
        paragraphs = split_paragraphs(normalize_text(result["text"]))

        return Chapter(
            title=title,
            paragraphs=paragraphs,
            next_url=None,
            prev_url=None,
            source_url=source_url,
        )

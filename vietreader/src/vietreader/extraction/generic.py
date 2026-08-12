"""Generic trafilatura-based fallback extractor, used when no site adapter matches the domain."""

from __future__ import annotations

import trafilatura

from vietreader.core.models import Chapter
from vietreader.core.normalize import normalize_text
from vietreader.core.series import chapter_display_title
from vietreader.extraction.base import ExtractionError
from vietreader.extraction.chapter_title import find_chapter_title
from vietreader.extraction.navigation import find_navigation


class GenericExtractor:
    def extract(self, html: str, source_url: str) -> Chapter:
        if not html or not html.strip():
            raise ExtractionError(f"empty HTML input for {source_url!r}")

        result = trafilatura.bare_extraction(html, url=source_url, with_metadata=True)
        if not result or not result.get("text"):
            raise ExtractionError(f"trafilatura found no extractable content for {source_url!r}")

        title = normalize_text(result.get("title") or "")
        # trafilatura separates blocks with a SINGLE newline, so the shared blank-line splitter
        # would collapse a whole chapter into one wall of text. One non-empty line = one
        # paragraph here. This path is the fallback for every site without an adapter, so
        # getting it wrong costs paragraph breaks on most first reads.
        lines = [line.strip() for line in normalize_text(result["text"]).split("\n")]
        paragraphs = [line for line in lines if line]
        # trafilatura usually repeats the heading as the first block of the body text.
        if paragraphs and title and paragraphs[0] == title:
            paragraphs = paragraphs[1:]

        next_url, prev_url = find_navigation(html, source_url)
        # Nhiều site đặt thẻ <title> là tên bộ truyện, khiến mọi chương trùng tên nhau.
        # Ưu tiên tên chương lấy thẳng từ trang vì nó CÓ DẤU; suy từ slug URL là phương án cuối.
        title = find_chapter_title(html, source_url) or chapter_display_title(title, source_url)

        return Chapter(
            title=title,
            paragraphs=paragraphs,
            next_url=next_url,
            prev_url=prev_url,
            source_url=source_url,
        )

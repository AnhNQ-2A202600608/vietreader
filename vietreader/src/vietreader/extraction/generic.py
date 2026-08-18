"""Generic extractor: tries selectolax heuristics first, falls back to trafilatura."""

from __future__ import annotations

import trafilatura
from selectolax.parser import HTMLParser

from vietreader.core.models import Chapter
from vietreader.core.normalize import normalize_text
from vietreader.core.series import chapter_display_title
from vietreader.extraction.base import ExtractionError
from vietreader.extraction.chapter_title import find_chapter_title
from vietreader.extraction.navigation import find_navigation

COMMON_NOVEL_SELECTORS = (
    "#chapter-c",
    ".chapter-c",
    "#chapter-content",
    ".chapter-content",
    "#js-read-content",
    ".read-content",
    ".reading-content",
    ".chap-content",
    ".box-chap",
    ".content-box",
    ".box_doc",
    "#box_doc",
    ".truyen-content",
    ".entry-content",
    ".post-content",
    'div[itemprop="articleBody"]',
    "#content",
    ".content",
    ".txt-content",
    "article",
)

STRIP_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "header",
    "footer",
    ".ads",
    ".ad",
    ".advertisement",
    ".chapter-nav",
    ".btn",
    "button",
)


def _extract_via_heuristics(tree: HTMLParser) -> tuple[str, list[str]]:
    title_node = tree.css_first("h1, h2, .chapter-title, .title")
    title = normalize_text(title_node.text(strip=True)) if title_node else ""

    for selector in COMMON_NOVEL_SELECTORS:
        content_node = tree.css_first(selector)
        if content_node is not None:
            # Strip ads, scripts, buttons
            for s in STRIP_SELECTORS:
                for bad in content_node.css(s):
                    bad.decompose()

            p_nodes = content_node.css("p")
            if p_nodes:
                paragraphs = [
                    normalize_text(p.text(strip=True))
                    for p in p_nodes
                    if normalize_text(p.text(strip=True))
                ]
            else:
                raw_text = content_node.text(deep=True, separator="\n", strip=True)
                paragraphs = [
                    normalize_text(line)
                    for line in raw_text.split("\n")
                    if normalize_text(line)
                ]

            if paragraphs and title and paragraphs[0] == title:
                paragraphs = paragraphs[1:]

            if len(paragraphs) >= 2 or (paragraphs and len("".join(paragraphs)) > 100):
                return title, paragraphs
    return title, []


class GenericExtractor:
    def extract(self, html: str, source_url: str) -> Chapter:
        if not html or not html.strip():
            raise ExtractionError(f"empty HTML input for {source_url!r}")

        tree = HTMLParser(html)
        next_url, prev_url = find_navigation(html, source_url)

        # 1. Try common novel layout selectors via selectolax
        title, paragraphs = _extract_via_heuristics(tree)

        # 2. If heuristics didn't match, fall back to trafilatura
        if not paragraphs:
            result = trafilatura.bare_extraction(html, url=source_url, with_metadata=True)
            if result and result.get("text"):
                title = normalize_text(result.get("title") or "")
                lines = [line.strip() for line in normalize_text(result["text"]).split("\n")]
                paragraphs = [line for line in lines if line]
                if paragraphs and title and paragraphs[0] == title:
                    paragraphs = paragraphs[1:]

        # 3. If still empty, fall back to all <p> tags in <body>
        if not paragraphs:
            body = tree.css_first("body")
            if body is not None:
                for s in STRIP_SELECTORS:
                    for bad in body.css(s):
                        bad.decompose()
                p_nodes = body.css("p")
                paragraphs = [
                    normalize_text(p.text(strip=True))
                    for p in p_nodes
                    if len(p.text(strip=True)) > 20
                ]

        if not paragraphs:
            raise ExtractionError(
                f"Không tìm thấy nội dung văn bản trong trang {source_url!r}. "
                "Bạn có thể sao chép và dán trực tiếp nội dung chương vào ô bên dưới."
            )

        # Tên chương lấy từ trang hoặc suy từ slug
        detected_title = find_chapter_title(html, source_url) or chapter_display_title(
            title, source_url
        )

        return Chapter(
            title=detected_title,
            paragraphs=paragraphs,
            next_url=next_url,
            prev_url=prev_url,
            source_url=source_url,
        )

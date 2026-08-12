"""Tìm tên chương CÓ DẤU ngay trong trang truyện.

Trafilatura trả về tiêu đề trang, mà nhiều site đặt tiêu đề trang là tên bộ truyện — nên mọi
chương trích ra đều trùng tên nhau. Tên chương thật thường vẫn nằm đâu đó trong trang: trong
thẻ `<title>` dạng "Tên truyện - Chương 3 tai ách", trong `<h1>`, hoặc trong một phần tử có
class kiểu `chapter-name` / `book-title`.

Lấy từ trang thì giữ được dấu tiếng Việt; suy từ slug URL là phương án cuối vì slug không dấu.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from vietreader.core.series import chapter_number

# Dấu phân cách hay dùng giữa tên truyện và tên chương trong thẻ <title>.
_TITLE_SEPARATORS = re.compile(r"\s+[-–—|·:]\s+|\s+\|\s+")

_MAX_TITLE_CHARS = 150

# Các phần tử hay chứa tên chương, ngoài h1/h2/h3.
_TITLE_LIKE_SELECTOR = (
    '[class*="chapter"], [class*="chuong"], [class*="book-title"], [class*="title"]'
)


def _candidates(tree: HTMLParser) -> list[str]:
    found: list[str] = []

    title_node = tree.css_first("title")
    if title_node:
        raw = title_node.text(strip=True)
        found.append(raw)
        # "Tên truyện - Chương 3 tai ách" -> tách ra để lấy riêng vế chương.
        found.extend(part.strip() for part in _TITLE_SEPARATORS.split(raw))

    for selector in ("h1", "h2", "h3", _TITLE_LIKE_SELECTOR):
        for node in tree.css(selector):
            found.append(node.text(strip=True))

    return [text for text in found if text and len(text) <= _MAX_TITLE_CHARS]


def find_chapter_title(html: str, source_url: str) -> str | None:
    """Tên chương lấy từ trang, hoặc None nếu không tìm được ứng viên đáng tin.

    Chỉ nhận ứng viên nhắc đúng số chương của URL. Trong số đó chọn chuỗi NGẮN NHẤT: các phần
    tử bao ngoài thường dính cả tên bộ truyện lẫn tên chương ("Tên truyệnChương 3 tai ách"),
    còn phần tử đúng chỗ thì chỉ có mỗi tên chương.
    """
    expected = chapter_number(source_url)
    if expected is None:
        return None

    best: str | None = None
    for text in _candidates(HTMLParser(html)):
        if chapter_number(text) != expected:
            continue
        if best is None or len(text) < len(best):
            best = text
    return best

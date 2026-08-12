"""Đoán liên kết chương trước / chương sau trên một trang truyện bất kỳ.

Adapter YAML (`config/sites/*.yml`) cho kết quả chính xác nhất, nhưng phải viết riêng cho từng
site. Module này là phương án mặc định: dò theo `rel="next"/"prev"` và theo chữ trên liên kết
("Chương sau", "Chương trước", "Next"...), để một site chưa có adapter vẫn chuyển chương được.

Chỉ đoán, nên có thể trượt — người đọc sửa tay được ở màn hình đọc.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import urljoin, urlsplit

from selectolax.parser import HTMLParser


def _fold(text: str) -> str:
    """Bỏ dấu để "chương sau" và "chuong sau" khớp cùng một luật."""
    stripped = unicodedata.normalize("NFD", text.lower())
    without_marks = "".join(c for c in stripped if unicodedata.category(c) != "Mn")
    return " ".join(without_marks.split())


# Xếp theo độ đặc hiệu giảm dần: cụm rõ nghĩa trước, ký hiệu mũi tên sau cùng.
_NEXT_PATTERNS = ("chuong sau", "chuong tiep", "chuong ke", "tiep theo", "sau >", "next chapter",
                  "next", "ke tiep")
_PREV_PATTERNS = ("chuong truoc", "chuong ke truoc", "truoc do", "previous chapter", "previous",
                  "prev", "chuong cu")
_NEXT_SYMBOLS = ("»", "›", "→", ">>")
_PREV_SYMBOLS = ("«", "‹", "←", "<<")


def _candidate_score(label: str, patterns: tuple[str, ...], symbols: tuple[str, ...]) -> int:
    """Điểm càng cao càng chắc. 0 nghĩa là không khớp."""
    folded = _fold(label)
    if not folded:
        return 0
    for index, pattern in enumerate(patterns):
        if pattern in folded:
            return 100 - index  # cụm càng đặc hiệu, điểm càng cao
    if any(symbol in label for symbol in symbols):
        return 10  # chỉ có mũi tên: yếu, nhưng còn hơn không
    return 0


def _same_page(url: str, source_url: str) -> bool:
    a, b = urlsplit(url), urlsplit(source_url)
    return (a.netloc, a.path.rstrip("/")) == (b.netloc, b.path.rstrip("/"))


def find_navigation(html: str, source_url: str) -> tuple[str | None, str | None]:
    """Trả về (next_url, prev_url) tuyệt đối, hoặc None nếu không đoán được."""
    tree = HTMLParser(html)
    best_next: tuple[int, str] | None = None
    best_prev: tuple[int, str] | None = None

    for anchor in tree.css("a"):
        href = anchor.attributes.get("href")
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue

        absolute = urljoin(source_url, href)
        if _same_page(absolute, source_url):
            continue  # trỏ về chính trang này thì không phải điều hướng chương

        rel = (anchor.attributes.get("rel") or "").lower()
        label = anchor.text(strip=True) or anchor.attributes.get("title") or ""

        next_score = (
            1000 if "next" in rel else _candidate_score(label, _NEXT_PATTERNS, _NEXT_SYMBOLS)
        )
        prev_score = (
            1000 if "prev" in rel else _candidate_score(label, _PREV_PATTERNS, _PREV_SYMBOLS)
        )

        # "chương trước" chứa cả "truoc" lẫn khả năng khớp yếu ở luật next — ưu tiên bên nào
        # điểm cao hơn để một liên kết không bị nhận thành cả hai chiều.
        if next_score > prev_score and (best_next is None or next_score > best_next[0]):
            best_next = (next_score, absolute)
        elif prev_score > next_score and (best_prev is None or prev_score > best_prev[0]):
            best_prev = (prev_score, absolute)

    return (best_next[1] if best_next else None, best_prev[1] if best_prev else None)

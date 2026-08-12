"""Lấy tên chương CÓ DẤU từ trang, thay vì suy từ slug URL (vốn không dấu)."""

from __future__ import annotations

from vietreader.extraction.chapter_title import find_chapter_title

URL = "https://truyen.vn/truyen/ten-bo/chuong-3-tai-ach-Ab3xYzQm"


def test_takes_the_chapter_half_of_a_title_tag() -> None:
    """Kiểu phổ biến nhất: '<title>Tên truyện - Chương N ...'."""
    html = "<html><head><title>Tên Bộ Truyện - Chương 3 tai ách</title></head><body></body></html>"
    assert find_chapter_title(html, URL) == "Chương 3 tai ách"


def test_prefers_the_shortest_candidate_that_names_the_chapter() -> None:
    """Phần tử bao ngoài hay dính cả tên truyện lẫn tên chương; phần tử đúng chỗ thì không."""
    html = """<html><head><title>Tên Bộ Truyện</title></head><body>
      <span class="top-title">Tên Bộ TruyệnChương 3 tai ách</span>
      <p class="book-title">Chương 3 tai ách</p>
    </body></html>"""
    assert find_chapter_title(html, URL) == "Chương 3 tai ách"


def test_reads_a_heading_when_the_title_tag_is_only_the_novel_name() -> None:
    html = """<html><head><title>Tên Bộ Truyện</title></head>
      <body><h1>Chương 3: Tai ách</h1></body></html>"""
    assert find_chapter_title(html, URL) == "Chương 3: Tai ách"


def test_ignores_candidates_about_a_different_chapter() -> None:
    """Danh sách chương ở sidebar không được cướp mất tiêu đề của chương đang đọc."""
    html = """<html><head><title>Tên Bộ Truyện</title></head><body>
      <a class="chapter-name">Chương 4 chuyện khác</a>
      <a class="chapter-name">Chương 5 chuyện khác nữa</a>
      <p class="book-title">Chương 3 tai ách</p>
    </body></html>"""
    assert find_chapter_title(html, URL) == "Chương 3 tai ách"


def test_returns_none_when_nothing_names_this_chapter() -> None:
    html = "<html><head><title>Tên Bộ Truyện</title></head><body><p>Nội dung.</p></body></html>"
    assert find_chapter_title(html, URL) is None


def test_returns_none_when_the_url_has_no_chapter_number() -> None:
    html = "<html><head><title>Giới thiệu - Chương 3</title></head><body></body></html>"
    assert find_chapter_title(html, "https://truyen.vn/truyen/ten-bo/gioi-thieu") is None

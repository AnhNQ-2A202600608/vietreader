"""Dò liên kết chương trước / chương sau khi site chưa có adapter YAML."""

from __future__ import annotations

import pytest

from vietreader.extraction.navigation import find_navigation

SOURCE = "https://truyen.vn/truyen-abc/chuong-5"


def _page(nav_html: str) -> str:
    return f"<html><body><article><p>Nội dung.</p></article>{nav_html}</body></html>"


@pytest.mark.parametrize(
    ("nav", "label"),
    [
        ('<a href="/c4">Chương trước</a><a href="/c6">Chương sau</a>', "có dấu"),
        ('<a href="/c4">chuong truoc</a><a href="/c6">Chuong sau</a>', "không dấu"),
        ('<a rel="prev" href="/c4">«</a><a rel="next" href="/c6">»</a>', "rel=prev/next"),
        ('<a href="/c4">‹</a><a href="/c6">›</a>', "chỉ mũi tên"),
        ('<a href="/c4">Previous</a><a href="/c6">Next chapter</a>', "tiếng Anh"),
    ],
)
def test_detects_navigation_in_common_layouts(nav: str, label: str) -> None:
    next_url, prev_url = find_navigation(_page(nav), SOURCE)
    assert next_url == "https://truyen.vn/c6", label
    assert prev_url == "https://truyen.vn/c4", label


def test_returns_none_when_there_is_no_chapter_navigation() -> None:
    next_url, prev_url = find_navigation(_page('<a href="/trang-chu">Trang chủ</a>'), SOURCE)
    assert next_url is None
    assert prev_url is None


def test_one_link_is_never_claimed_as_both_directions() -> None:
    """"Chương trước" chứa cả chữ khớp luật next lẫn prev — chỉ được nhận một chiều."""
    next_url, prev_url = find_navigation(_page('<a href="/c4">Chương trước</a>'), SOURCE)
    assert prev_url == "https://truyen.vn/c4"
    assert next_url is None


def test_ignores_links_back_to_the_same_page() -> None:
    nav = f'<a href="{SOURCE}">Chương sau</a><a href="{SOURCE}/">Chương trước</a>'
    assert find_navigation(_page(nav), SOURCE) == (None, None)


def test_ignores_non_navigational_hrefs() -> None:
    nav = '<a href="#top">Chương sau</a><a href="javascript:void(0)">Chương trước</a>'
    assert find_navigation(_page(nav), SOURCE) == (None, None)


def test_relative_links_resolve_against_the_chapter_url() -> None:
    next_url, _ = find_navigation(_page('<a href="chuong-6">Chương sau</a>'), SOURCE)
    assert next_url == "https://truyen.vn/truyen-abc/chuong-6"

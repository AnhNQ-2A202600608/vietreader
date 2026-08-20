"""Series grouping heuristics (core/series.py) -- pure, no I/O."""

from __future__ import annotations

import pytest

from vietreader.core.series import (
    chapter_display_title,
    chapter_number,
    derive_series_key,
    infer_chapter_title,
    series_title_from_key,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://truyenfull.vn/dau-pha-thuong-khung/chuong-5/",
            "https://truyenfull.vn/dau-pha-thuong-khung",
        ),
        (
            "https://truyenfull.vn/dau-pha-thuong-khung/chuong-6",
            "https://truyenfull.vn/dau-pha-thuong-khung",
        ),
        # Query strings and fragments must not split a series into two.
        (
            "https://site.com/truyen-abc/chuong-1?page=2#top",
            "https://site.com/truyen-abc",
        ),
        # Deeper layouts keep every level except the chapter itself.
        (
            "https://site.com/the-loai/tien-hiep/truyen-abc/chuong-9",
            "https://site.com/the-loai/tien-hiep/truyen-abc",
        ),
    ],
)
def test_chapters_of_one_story_share_a_series_key(url: str, expected: str) -> None:
    assert derive_series_key(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "not-a-url",
        "https://site.com",
        "https://site.com/",
        # Only one segment: the "series" would be the entire host, which would wrongly merge
        # every unrelated story on that site.
        "https://site.com/chuong-5",
    ],
)
def test_no_series_is_claimed_when_the_url_cannot_prove_one(url: str | None) -> None:
    assert derive_series_key(url) is None


def test_two_stories_on_one_host_stay_separate() -> None:
    a = derive_series_key("https://site.com/truyen-a/chuong-1")
    b = derive_series_key("https://site.com/truyen-b/chuong-1")
    assert a != b


def test_chapter_title_falls_back_to_the_url_when_the_page_reuses_the_novel_name() -> None:
    """Nhiều site đặt <title> là tên bộ truyện, nên mọi chương trích ra đều trùng tên nhau và
    danh sách chương nhìn như bị lưu trùng lặp."""
    novel = "Tên Bộ Truyện"
    base = "https://truyen.vn/truyen/ten-bo-truyen"

    assert chapter_display_title(novel, f"{base}/chuong-2-canh-cua-Ab3xYzQm") == (
        "Chương 2 — Canh cua"
    )
    assert chapter_display_title(novel, f"{base}/chuong-3-tai-ach-Ab3xYzQn") == (
        "Chương 3 — Tai ach"
    )
    # Hai chương khác nhau phải ra hai tên khác nhau -- đó là mục đích của cả hàm này.
    assert chapter_display_title(novel, f"{base}/chuong-2-a-Ab3xYzQm") != chapter_display_title(
        novel, f"{base}/chuong-3-b-Ab3xYzQn"
    )


@pytest.mark.parametrize(
    ("title", "url"),
    [
        # Tiêu đề đã nói rõ chương mấy -> tin nó, không đụng vào.
        ("Chương 7: Gặp gỡ", "https://truyen.vn/truyen/abc/chuong-7-gap-go"),
        # Không có URL (chương dán tay) hoặc URL không có số chương -> giữ nguyên.
        ("Chương dán tay", None),
        ("Lời tựa", "https://truyen.vn/truyen/abc/gioi-thieu"),
    ],
)
def test_chapter_title_is_left_alone_when_it_is_already_specific(
    title: str, url: str | None
) -> None:
    assert chapter_display_title(title, url) == title


def test_series_title_defaults_to_a_readable_slug() -> None:
    assert series_title_from_key("https://truyenfull.vn/dau-pha-thuong-khung") == (
        "Dau Pha Thuong Khung"
    )


def test_infer_title_from_the_opening_paragraph_for_pasted_chapters() -> None:
    paragraphs = [
        "Chương 127 — Người trở về",
        "Mưa rơi rất lâu trên mái ngói cũ, phủ kín con đường dẫn vào thành.",
    ]
    assert infer_chapter_title("", None, paragraphs) == "Chương 127 — Người trở về"


def test_infer_short_unnumbered_heading_only_when_followed_by_long_prose() -> None:
    paragraphs = [
        "Gặp lại",
        "Mưa rơi rất lâu trên mái ngói cũ, phủ kín con đường dẫn vào thành và che mờ bóng người.",
    ]
    assert infer_chapter_title(None, None, paragraphs) == "Gặp lại"
    assert infer_chapter_title(None, None, ["Ta là ai?", paragraphs[1]]) == ""


@pytest.mark.parametrize(
    ("sources", "expected"),
    [
        (("https://site.com/truyen/chuong-12",), 12.0),
        (("https://site.com/truyen/chapter-7",), 7.0),
        ((None, "Chương 340: Kết thúc"), 340.0),
        # URL wins over title when both carry a number: it is the more reliable source.
        (("https://site.com/truyen/chuong-2", "Chương 999"), 2.0),
        (("https://site.com/truyen/gioi-thieu", "Lời tựa"), None),
        # URL có dấu tiếng Việt được percent-encode: "%C3" từng bị đọc thành "chương 3".
        (("https://vi.wikipedia.org/wiki/H%E1%BB%93_Ho%C3%A0n_Ki%E1%BA%BFm",), None),
        # Từ khoá lọt giữa một từ khác thì không tính.
        (("https://site.com/mua-chuong-2-cai",), 2.0),
        (("https://site.com/march-2024/bai-viet",), None),
    ],
)
def test_chapter_number_is_extracted_for_ordering(
    sources: tuple[str | None, ...], expected: float | None
) -> None:
    assert chapter_number(*sources) == expected

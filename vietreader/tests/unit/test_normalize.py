from __future__ import annotations

import unicodedata

from vietreader.core.normalize import normalize_text, split_paragraphs


def test_crlf_converted_to_lf() -> None:
    assert normalize_text("a\r\nb\r\nc") == "a\nb\nc"


def test_trailing_whitespace_per_line_is_stripped() -> None:
    assert normalize_text("a   \nb\t\n") == "a\nb\n"


def test_more_than_two_blank_lines_collapse_to_two() -> None:
    assert normalize_text("a\n\n\n\n\nb") == "a\n\nb"


def test_nfd_input_normalized_to_nfc() -> None:
    nfd = unicodedata.normalize("NFD", "lão giả")
    assert normalize_text(nfd) == unicodedata.normalize("NFC", "lão giả")


def test_split_paragraphs_on_blank_lines() -> None:
    text = normalize_text("Đoạn một.\n\nĐoạn hai.\n\n\nĐoạn ba.")
    assert split_paragraphs(text) == ["Đoạn một.", "Đoạn hai.", "Đoạn ba."]


def test_split_paragraphs_empty_text_returns_empty_list() -> None:
    assert split_paragraphs(normalize_text("")) == []

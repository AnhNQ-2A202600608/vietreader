from __future__ import annotations

from vietreader.core.casing import CasingShape, apply_casing, detect_shape


def test_detect_shape_lower() -> None:
    assert detect_shape("lão giả") is CasingShape.LOWER


def test_detect_shape_title() -> None:
    assert detect_shape("Lão giả") is CasingShape.TITLE


def test_detect_shape_upper() -> None:
    assert detect_shape("LÃO GIẢ") is CasingShape.UPPER


def test_detect_shape_mixed() -> None:
    assert detect_shape("LãO giả") is CasingShape.MIXED


def test_detect_shape_no_letters_defaults_to_lower() -> None:
    assert detect_shape("123 !!!") is CasingShape.LOWER


def test_apply_casing_lower_keeps_replacement_unchanged() -> None:
    replacement, warned = apply_casing("lão giả", "ông lão")
    assert replacement == "ông lão"
    assert warned is False


def test_apply_casing_title_uppercases_first_letter_only() -> None:
    replacement, warned = apply_casing("Lão giả", "ông lão")
    assert replacement == "Ông lão"
    assert warned is False


def test_apply_casing_title_with_empty_replacement_is_noop() -> None:
    replacement, warned = apply_casing("Lão giả", "")
    assert replacement == ""
    assert warned is False


def test_apply_casing_upper_uppercases_whole_replacement() -> None:
    replacement, warned = apply_casing("LÃO GIẢ", "ông lão")
    assert replacement == "ÔNG LÃO"
    assert warned is False


def test_apply_casing_mixed_keeps_replacement_and_warns() -> None:
    replacement, warned = apply_casing("LãO giả", "ông lão")
    assert replacement == "ông lão"
    assert warned is True

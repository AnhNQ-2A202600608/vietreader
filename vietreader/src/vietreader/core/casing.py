"""Casing transfer: apply the shape of the matched span onto its replacement."""

from __future__ import annotations

from enum import StrEnum


class CasingShape(StrEnum):
    LOWER = "lower"
    TITLE = "title"
    UPPER = "upper"
    MIXED = "mixed"


def detect_shape(text: str) -> CasingShape:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return CasingShape.LOWER
    if all(c.islower() for c in letters):
        return CasingShape.LOWER
    if all(c.isupper() for c in letters):
        return CasingShape.UPPER
    if letters[0].isupper() and all(c.islower() for c in letters[1:]):
        return CasingShape.TITLE
    return CasingShape.MIXED


def apply_casing(original: str, replacement: str) -> tuple[str, bool]:
    """Returns (transformed_replacement, is_mixed_warning)."""
    shape = detect_shape(original)
    if shape is CasingShape.LOWER:
        return replacement, False
    if shape is CasingShape.UPPER:
        return replacement.upper(), False
    if shape is CasingShape.TITLE:
        if not replacement:
            return replacement, False
        return replacement[0].upper() + replacement[1:], False
    return replacement, True

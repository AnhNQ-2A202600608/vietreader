"""Core domain models: Span, ChangeLog, Chapter, Decision. Pure, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


class Policy(StrEnum):
    KEEP = "keep"
    REPLACE = "replace"
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class Span:
    """A matched region in a paragraph's original text."""

    start: int
    end: int
    text: str
    entry_id: int
    policy: Policy

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span bounds: start={self.start}, end={self.end}")
        if len(self.text) != self.end - self.start:
            raise ValueError("span.text length must equal end - start")


@dataclass(frozen=True, slots=True)
class Change:
    """A single applied replacement; source of truth for the validator."""

    para_index: int
    start: int
    end: int
    original: str
    replacement: str
    entry_id: int
    source: Literal["replace", "llm", "llm_fallback"]
    llm_choice_index: int | None = None


@dataclass(frozen=True, slots=True)
class Chapter:
    """Result of L0 extraction."""

    title: str
    paragraphs: list[str] = field(default_factory=list)
    next_url: str | None = None
    prev_url: str | None = None
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

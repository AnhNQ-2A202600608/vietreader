"""DictionaryEntry and CompiledDictionary (L1 automaton + version hash). Pure, no I/O."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

import ahocorasick

from vietreader.core.models import Policy


class DictionaryEntryError(ValueError):
    """Raised when a DictionaryEntry violates its invariants."""


def normalize_surface(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


@dataclass(frozen=True, slots=True)
class DictionaryEntry:
    id: int
    surface: str
    display: str
    policy: Policy
    replacement: str | None = None
    candidates: list[str] = field(default_factory=list)
    priority: int = 0
    note: str = ""
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        surface_norm = unicodedata.normalize("NFC", self.surface)
        if not surface_norm:
            raise DictionaryEntryError("surface must not be empty")
        if "\n" in surface_norm or "\r" in surface_norm:
            raise DictionaryEntryError("surface must not contain newlines")
        if surface_norm != self.surface:
            raise DictionaryEntryError("surface must be pre-normalized to NFC")
        if self.surface != self.surface.lower():
            raise DictionaryEntryError("surface must be lowercase")

        if self.policy is Policy.REPLACE:
            if not self.replacement:
                raise DictionaryEntryError("REPLACE requires a non-empty replacement")
            if self.candidates:
                raise DictionaryEntryError("REPLACE must not have candidates")
        elif self.policy is Policy.ASK:
            if len(self.candidates) < 2:
                raise DictionaryEntryError("ASK requires at least 2 candidates")
            if self.replacement is not None:
                raise DictionaryEntryError("ASK must not have a replacement")
        elif self.policy is Policy.KEEP:
            if self.replacement is not None:
                raise DictionaryEntryError("KEEP must not have a replacement")
            if self.candidates:
                raise DictionaryEntryError("KEEP must not have candidates")


@dataclass(frozen=True, slots=True)
class CompiledDictionary:
    """Immutable, matcher-ready view over a set of enabled entries."""

    entries_by_id: dict[int, DictionaryEntry]
    automaton: ahocorasick.Automaton
    version_hash: str

    @staticmethod
    def _entry_sort_key(entry: DictionaryEntry) -> tuple[str, int]:
        return (entry.surface, entry.id)

    @classmethod
    def from_entries(cls, entries: list[DictionaryEntry]) -> CompiledDictionary:
        seen_surfaces: set[str] = set()
        for entry in entries:
            if not entry.enabled:
                continue
            if entry.surface in seen_surfaces:
                raise DictionaryEntryError(f"duplicate surface after normalize: {entry.surface!r}")
            seen_surfaces.add(entry.surface)

        automaton = ahocorasick.Automaton()
        entries_by_id: dict[int, DictionaryEntry] = {}
        for entry in entries:
            if not entry.enabled:
                continue
            entries_by_id[entry.id] = entry
            automaton.add_word(entry.surface, entry.id)
        automaton.make_automaton()

        sorted_entries = sorted(
            (e for e in entries if e.enabled), key=cls._entry_sort_key
        )
        hash_input = "\x1f".join(
            f"{e.id}|{e.surface}|{e.policy}|{e.replacement or ''}|"
            f"{','.join(e.candidates)}|{e.priority}"
            for e in sorted_entries
        )
        version_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        return cls(entries_by_id=entries_by_id, automaton=automaton, version_hash=version_hash)

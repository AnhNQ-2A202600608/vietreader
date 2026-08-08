"""LLMProvider Protocol + FakeProvider for offline, deterministic tests.

The provider's only job is: given a batch of disambiguation items, return the model's raw
text response (expected to be a JSON array per spec §3.4). Parsing, retry, and fallback logic
live in disambiguator.py — the provider itself never interprets or repairs the response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class DisambiguationItem:
    id: str
    term: str
    left: str
    right: str
    candidates: list[str]


class LLMProvider(Protocol):
    async def disambiguate(
        self,
        items: list[DisambiguationItem],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Return the raw text response. Expected shape: JSON array of {"id", "choice"}."""
        ...


FakeMode = Literal[
    "correct",
    "broken_json",
    "out_of_range",
    "missing_id",
    "timeout",
]


@dataclass
class FakeProvider:
    """Deterministic provider for offline tests.

    `choose` picks the candidate index for each item in "correct" mode (defaults to 0).
    `call_count` lets tests assert on how many times the provider was actually invoked
    (e.g. zero calls when a chapter has no ASK spans — spec §3.4).
    """

    mode: FakeMode = "correct"
    choose: dict[str, int] | None = None
    call_count: int = field(default=0, init=False)

    async def disambiguate(
        self,
        items: list[DisambiguationItem],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.call_count += 1

        if self.mode == "timeout":
            raise TimeoutError("FakeProvider: simulated provider timeout")

        if self.mode == "broken_json":
            return "{this is not valid json"

        results = []
        for item in items:
            if self.mode == "missing_id" and item is items[0]:
                continue
            if self.mode == "out_of_range":
                choice = len(item.candidates) + 5
            else:
                choice = (self.choose or {}).get(item.id, 0)
            results.append({"id": item.id, "choice": choice})

        return json.dumps(results, ensure_ascii=False)

"""L2 Resolver: turns Span[] into Change[] using dictionary policy + injectable AskResolver.

KEEP spans are skipped (protected, no change). REPLACE spans get their fixed replacement.
ASK spans are delegated to an injected `AskResolver` callable — in Phase 2 this is a test
stub; from Phase 5 onward it is backed by the real LLM disambiguator (L3). The resolver never
validates the AskResolver's output itself: that is the validator's (L5) job, so tests can prove
L5 actually catches bad input rather than trusting L2 to pre-filter it.
"""

from __future__ import annotations

from typing import Literal, NamedTuple, Protocol

from vietreader.core.casing import apply_casing
from vietreader.core.dictionary import CompiledDictionary
from vietreader.core.models import Change, Policy, Span


class AskDecision(NamedTuple):
    """Result of resolving one ASK span. `replacement` is the raw candidate text
    (casing is applied by the resolver, not by the AskResolver)."""

    replacement: str
    source: Literal["llm", "llm_fallback"]
    choice_index: int | None


class AskResolver(Protocol):
    def __call__(self, span: Span, para_index: int) -> AskDecision | None:
        """Return None to mean fallback-to-KEEP: no Change is emitted for this span."""
        ...


def resolve(
    para_index: int,
    spans: list[Span],
    dictionary: CompiledDictionary,
    ask_resolver: AskResolver,
) -> list[Change]:
    changes: list[Change] = []
    for span in spans:
        entry = dictionary.entries_by_id[span.entry_id]

        if entry.policy is Policy.KEEP:
            continue

        if entry.policy is Policy.REPLACE:
            assert entry.replacement is not None
            replacement, _mixed_warning = apply_casing(span.text, entry.replacement)
            changes.append(
                Change(
                    para_index=para_index,
                    start=span.start,
                    end=span.end,
                    original=span.text,
                    replacement=replacement,
                    entry_id=entry.id,
                    source="replace",
                )
            )
            continue

        if entry.policy is Policy.ASK:
            decision = ask_resolver(span, para_index)
            if decision is None:
                continue
            replacement, _mixed_warning = apply_casing(span.text, decision.replacement)
            changes.append(
                Change(
                    para_index=para_index,
                    start=span.start,
                    end=span.end,
                    original=span.text,
                    replacement=replacement,
                    entry_id=entry.id,
                    source=decision.source,
                    llm_choice_index=decision.choice_index,
                )
            )

    return changes

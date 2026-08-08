"""L5 Validator: invariants I1..I7 over (input, output, changelog). See spec §3.5."""

from __future__ import annotations

from collections import defaultdict

from vietreader.core.casing import apply_casing
from vietreader.core.dictionary import CompiledDictionary
from vietreader.core.matcher import match
from vietreader.core.models import Change, Policy, Span, ValidationResult


def reconstruct(output_paragraphs: list[str], changelog: list[Change]) -> list[str]:
    """Reverse-apply the changelog (right to left) to recover the original paragraphs
    from the output. This is I1: the proof that nothing was added or dropped."""
    by_para: dict[int, list[Change]] = defaultdict(list)
    for change in changelog:
        by_para[change.para_index].append(change)

    result: list[str] = []
    for index, out_para in enumerate(output_paragraphs):
        changes = sorted(by_para.get(index, []), key=lambda c: c.start)

        positioned: list[tuple[int, int, str]] = []
        shift = 0
        for change in changes:
            out_start = change.start + shift
            out_end = out_start + len(change.replacement)
            positioned.append((out_start, out_end, change.original))
            shift += len(change.replacement) - (change.end - change.start)

        text = out_para
        for out_start, out_end, original in reversed(positioned):
            text = text[:out_start] + original + text[out_end:]
        result.append(text)

    return result


def _keep_counts(paragraphs: list[str], keep_dict: CompiledDictionary) -> dict[int, int]:
    counts: dict[int, int] = defaultdict(int)
    for paragraph in paragraphs:
        for span in match(paragraph, keep_dict):
            counts[span.entry_id] += 1
    return counts


def validate(
    input_paragraphs: list[str],
    output_paragraphs: list[str],
    changelog: list[Change],
    dictionary: CompiledDictionary,
    spans_by_para: dict[int, list[Span]],
) -> ValidationResult:
    violations: list[str] = []
    warnings: list[str] = []

    # I2 first: I1's reconstruct assumes paragraph counts line up index-for-index.
    if len(output_paragraphs) != len(input_paragraphs):
        violations.append(
            f"I2: paragraph count changed ({len(input_paragraphs)} -> {len(output_paragraphs)})"
        )
    else:
        reconstructed = reconstruct(output_paragraphs, changelog)
        if reconstructed != input_paragraphs:
            violations.append(
                "I1: reconstruct(output, changelog) != input (byte-exact check failed)"
            )

    for change in changelog:
        spans = spans_by_para.get(change.para_index, [])
        if not any(
            s.start == change.start and s.end == change.end and s.entry_id == change.entry_id
            for s in spans
        ):
            violations.append(
                f"I3: change at para={change.para_index} start={change.start} "
                f"end={change.end} entry_id={change.entry_id} matches no matcher span"
            )

    for change in changelog:
        entry = dictionary.entries_by_id.get(change.entry_id)
        if entry is None:
            continue  # already reported via I3
        if change.source == "replace":
            if entry.replacement is None:
                violations.append(
                    f"I4: change {change.entry_id}@{change.start} has source='replace' but "
                    f"entry {entry.surface!r} (policy={entry.policy}) has no replacement"
                )
            else:
                expected, _ = apply_casing(change.original, entry.replacement)
                if change.replacement != expected:
                    violations.append(
                        f"I4: change {change.entry_id}@{change.start} replacement "
                        f"{change.replacement!r} != casing(entry.replacement) {expected!r}"
                    )
        elif change.source == "llm":
            allowed = {apply_casing(change.original, c)[0] for c in entry.candidates}
            if change.replacement not in allowed:
                violations.append(
                    f"I5: change {change.entry_id}@{change.start} replacement "
                    f"{change.replacement!r} not in casing(entry.candidates) {sorted(allowed)!r}"
                )

    keep_entries = [e for e in dictionary.entries_by_id.values() if e.policy is Policy.KEEP]
    if keep_entries:
        keep_dict = CompiledDictionary.from_entries(keep_entries)
        input_counts = _keep_counts(input_paragraphs, keep_dict)
        output_counts = _keep_counts(output_paragraphs, keep_dict)
        for entry in keep_entries:
            in_count = input_counts.get(entry.id, 0)
            out_count = output_counts.get(entry.id, 0)
            if in_count != out_count:
                violations.append(
                    f"I6: KEEP term {entry.surface!r} occurs {in_count} times in input "
                    f"but {out_count} times in output"
                )

    input_len = sum(len(p) for p in input_paragraphs)
    output_len = sum(len(p) for p in output_paragraphs)
    if input_len > 0:
        ratio = output_len / input_len
        if not (0.85 <= ratio <= 1.20):
            warnings.append(f"I7: length ratio {ratio:.3f} outside [0.85, 1.20]")

    return ValidationResult(ok=not violations, violations=violations, warnings=warnings)

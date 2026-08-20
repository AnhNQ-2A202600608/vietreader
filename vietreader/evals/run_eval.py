"""Eval harness (Phase 8): runs every case in evals/golden/*.yml through the REAL pipeline
(core matcher/resolver/applier/validator + llm.disambiguator), prints the metric table, and
writes evals/REPORT.md.

Usage:
    python evals/run_eval.py                 # offline, FakeProvider (CI-safe, no network)
    python evals/run_eval.py --live           # real Anthropic provider (needs an API key)
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietreader.core.applier import apply_changes  # noqa: E402
from vietreader.core.dictionary import CompiledDictionary, DictionaryEntry  # noqa: E402
from vietreader.core.matcher import match  # noqa: E402
from vietreader.core.models import Policy, Span  # noqa: E402
from vietreader.core.normalize import normalize_text, split_paragraphs  # noqa: E402
from vietreader.core.resolver import resolve  # noqa: E402
from vietreader.core.validator import validate  # noqa: E402
from vietreader.llm.disambiguator import (  # noqa: E402
    DisambiguationRequest,
    disambiguate_batch,
)
from vietreader.llm.provider import FakeProvider, LLMProvider  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
REPORT_PATH = Path(__file__).resolve().parent / "REPORT.md"
CONTEXT_WIDTH = 60


@dataclass(frozen=True, slots=True)
class GoldenCase:
    id: str
    input: str
    dictionary_ref: str
    expect_output: str
    must_keep: list[str]
    must_not_contain: list[str]


@dataclass
class CaseResult:
    case_id: str
    i1_pass: bool
    i6_pass: bool
    exact_match: bool
    sentence_count_delta: int
    had_ask_span: bool
    llm_calls: int
    word_count: int
    duration_ms: float
    output: str
    violations: list[str]


def load_dictionary(ref: str) -> CompiledDictionary:
    assert ref == "default", f"unknown dictionary_ref {ref!r}"
    data = yaml.safe_load((GOLDEN_DIR / "dictionary.yml").read_text(encoding="utf-8"))
    entries = [
        DictionaryEntry(
            id=i,
            surface=e["surface"],
            display=e["display"],
            policy=Policy(e["policy"]),
            replacement=e.get("replacement"),
            candidates=e.get("candidates") or [],
        )
        for i, e in enumerate(data["entries"], start=1)
    ]
    return CompiledDictionary.from_entries(entries)


def load_cases() -> list[GoldenCase]:
    cases = []
    for path in sorted(GOLDEN_DIR.glob("case_*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.append(
            GoldenCase(
                id=data["id"],
                input=data["input"],
                dictionary_ref=data["dictionary_ref"],
                expect_output=data["expect_output"],
                must_keep=data.get("must_keep") or [],
                must_not_contain=data.get("must_not_contain") or [],
            )
        )
    return cases


def _context(paragraph: str, span: Span, width: int = CONTEXT_WIDTH) -> tuple[str, str]:
    return paragraph[max(0, span.start - width) : span.start], paragraph[
        span.end : span.end + width
    ]


def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r"[.!?]+", text) if s.strip()])


async def run_case(case: GoldenCase, provider: LLMProvider) -> CaseResult:
    dictionary = load_dictionary(case.dictionary_ref)
    start = time.monotonic()

    normalized = normalize_text(case.input)
    paragraphs = split_paragraphs(normalized)

    spans_by_para: dict[int, list[Span]] = {}
    for i, para in enumerate(paragraphs):
        spans_by_para[i] = match(para, dictionary)

    ask_requests: list[DisambiguationRequest] = []
    for para_index, spans in spans_by_para.items():
        paragraph = paragraphs[para_index]
        for span_index, span in enumerate(spans):
            entry = dictionary.entries_by_id[span.entry_id]
            if entry.policy is not Policy.ASK:
                continue
            left, right = _context(paragraph, span)
            ask_requests.append(
                DisambiguationRequest(
                    id=f"p{para_index}_s{span_index}",
                    span=span,
                    entry=entry,
                    left=left,
                    right=right,
                )
            )

    outcome = await disambiguate_batch(ask_requests, provider, model="eval-model")
    decisions = {r.id: r.decision for r in outcome.results}

    changelog = []
    for para_index, spans in spans_by_para.items():

        def ask_resolver(span: Span, p_index: int, _spans=spans, _para_index=para_index):  # type: ignore[no-untyped-def]
            return decisions.get(f"p{_para_index}_s{_spans.index(span)}")

        changelog.extend(resolve(para_index, spans, dictionary, ask_resolver))

    output_paragraphs = apply_changes(paragraphs, changelog)
    result = validate(paragraphs, output_paragraphs, changelog, dictionary, spans_by_para)
    duration_ms = (time.monotonic() - start) * 1000

    output = "\n\n".join(output_paragraphs)
    output_lower = output.lower()
    i1_pass = not any(v.startswith("I1:") for v in result.violations)
    i6_pass = not any(v.startswith("I6:") for v in result.violations)
    # Case-insensitive, like the matcher itself: a KEEP term at sentence-start is legitimately
    # capitalized in the text (e.g. "Linh lực ..."), so a literal-case substring check would
    # wrongly flag correct output as missing the protected term.
    must_keep_ok = all(term.lower() in output_lower for term in case.must_keep)
    must_not_contain_ok = all(term.lower() not in output_lower for term in case.must_not_contain)
    exact_match = output == case.expect_output and must_keep_ok and must_not_contain_ok

    return CaseResult(
        case_id=case.id,
        i1_pass=i1_pass,
        i6_pass=i6_pass and must_keep_ok,
        exact_match=exact_match,
        sentence_count_delta=abs(_sentence_count(output) - _sentence_count(case.input)),
        had_ask_span=bool(ask_requests),
        llm_calls=outcome.llm_calls,
        word_count=len(re.findall(r"\S+", case.input)),
        duration_ms=duration_ms,
        output=output,
        violations=result.violations,
    )


def build_provider(live: bool) -> LLMProvider:
    if not live:
        return FakeProvider(mode="correct")  # default choice index 0, see DECISIONS.md
    import os

    from vietreader.llm.anthropic import AnthropicProvider

    api_key = os.environ.get("VIETREADER_LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("NOT RUN: --live requested but no API key in environment.", file=sys.stderr)
        sys.exit(2)
    return AnthropicProvider(api_key=api_key, model="claude-haiku-4-5-20251001")


def render_report(results: list[CaseResult], live: bool) -> str:
    n = len(results)
    reconstruction_pass_rate = sum(r.i1_pass for r in results) / n
    keep_preservation_rate = sum(r.i6_pass for r in results) / n
    exact_output_match = sum(r.exact_match for r in results) / n
    ask_cases = [r for r in results if r.had_ask_span]
    ambiguity_accuracy = (
        (sum(r.exact_match for r in ask_cases) / len(ask_cases)) if ask_cases else None
    )
    sentence_count_delta_all_zero = all(r.sentence_count_delta == 0 for r in results)
    zero_llm_chapter_ratio = sum(r.llm_calls == 0 for r in results) / n
    total_words = sum(r.word_count for r in results)
    total_llm_calls = sum(r.llm_calls for r in results)
    avg_llm_calls_per_1000_words = (total_llm_calls / total_words * 1000) if total_words else 0.0
    latencies = sorted(r.duration_ms for r in results)
    p95_latency_ms = latencies[int(0.95 * (len(latencies) - 1))] if latencies else 0.0

    lines = []
    lines.append(
        f"# Eval Report — VietReader (provider: {'live' if live else 'FakeProvider (offline)'})"
    )
    lines.append("")
    lines.append(f"Số golden case: {n}")
    lines.append("")
    lines.append("| Metric | Ngưỡng | Giá trị | Kết quả |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| reconstruction_pass_rate (I1) | 1.00 | {reconstruction_pass_rate:.4f} | "
        f"{'PASS' if reconstruction_pass_rate == 1.0 else 'FAIL — BLOCKER'} |"
    )
    lines.append(
        f"| keep_preservation_rate (I6) | 1.00 | {keep_preservation_rate:.4f} | "
        f"{'PASS' if keep_preservation_rate == 1.0 else 'FAIL — BLOCKER'} |"
    )
    lines.append(
        f"| exact_output_match | >= 0.90 | {exact_output_match:.4f} | "
        f"{'PASS' if exact_output_match >= 0.90 else 'FAIL'} |"
    )
    if ambiguity_accuracy is None:
        lines.append("| ambiguity_accuracy | >= 0.80 | N/A (no ASK cases) | — |")
    else:
        lines.append(
            f"| ambiguity_accuracy | >= 0.80 | {ambiguity_accuracy:.4f} | "
            f"{'PASS' if ambiguity_accuracy >= 0.80 else 'FAIL'} |"
        )
    lines.append(
        f"| sentence_count_delta == 0 (mọi case) | 0 | "
        f"{'0 trên mọi case' if sentence_count_delta_all_zero else 'CÓ case lệch'} | "
        f"{'PASS' if sentence_count_delta_all_zero else 'FAIL'} |"
    )
    lines.append(
        f"| zero_llm_chapter_ratio | báo cáo (kỳ vọng > 0.5) | {zero_llm_chapter_ratio:.4f} | — |"
    )
    lines.append(
        f"| avg_llm_calls_per_1000_words | báo cáo | {avg_llm_calls_per_1000_words:.4f} | — |"
    )
    lines.append(f"| p95_latency_ms | báo cáo | {p95_latency_ms:.2f} | — |")
    lines.append("")
    lines.append("## Chi tiết theo case")
    lines.append("")
    lines.append("| id | I1 | I6 | exact_match | ASK? | llm_calls | duration_ms |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r.case_id} | {'✓' if r.i1_pass else '✗'} | {'✓' if r.i6_pass else '✗'} | "
            f"{'✓' if r.exact_match else '✗'} | {'✓' if r.had_ask_span else ''} | "
            f"{r.llm_calls} | {r.duration_ms:.2f} |"
        )
    failures = [r for r in results if not r.exact_match]
    if failures:
        lines.append("")
        lines.append("## Case KHÔNG khớp expect_output (chi tiết để điều tra)")
        for r in failures:
            lines.append(f"- **{r.case_id}**: output = {r.output!r}")
            if r.violations:
                lines.append(f"  violations: {r.violations}")

    if not live:
        lines.append("")
        lines.append(
            '**Lưu ý:** chạy với `FakeProvider` (mode="correct", luôn chọn candidate index 0). '
            "`ambiguity_accuracy` ở chế độ này đo hành vi mặc định của FakeProvider, KHÔNG phải "
            "chất lượng LLM thật — xem DECISIONS.md mục Phase 8. Chạy `--live` với API key thật "
            "để có tín hiệu ý nghĩa cho metric này."
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    # Windows terminals may default to cp1252, which cannot print Vietnamese or ✓/✗.
    # Reconfigure only the CLI streams; report files are already written explicitly as UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="use the real Anthropic provider")
    args = parser.parse_args()

    provider = build_provider(args.live)
    cases = load_cases()
    assert len(cases) >= 40, f"expected >= 40 golden cases, found {len(cases)}"

    results = asyncio.run(_run_all(cases, provider))
    report = render_report(results, args.live)
    print(report)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")

    reconstruction_pass_rate = sum(r.i1_pass for r in results) / len(results)
    keep_preservation_rate = sum(r.i6_pass for r in results) / len(results)
    if reconstruction_pass_rate != 1.0 or keep_preservation_rate != 1.0:
        print("\nBLOCKER: I1 and/or I6 did not reach 1.00 — see report.", file=sys.stderr)
        sys.exit(1)


async def _run_all(cases: list[GoldenCase], provider: LLMProvider) -> list[CaseResult]:
    return [await run_case(case, provider) for case in cases]


if __name__ == "__main__":
    main()

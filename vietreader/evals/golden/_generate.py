"""One-time authoring helper: derives `expect_output` for each golden case by running the
REAL core pipeline (match -> resolve -> apply), so golden values are correct by construction
instead of hand-transcribed. Not part of the Phase 8 deliverables (only the *.yml case files
and run_eval.py are) -- kept in the repo for reproducibility/maintainability.

`run_eval.py` does NOT import this file: it independently re-runs the full pipeline (including
the LLM disambiguator) against the stored golden YAML and compares against `expect_output`,
so this script never becomes a source of circular "self-grading".
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from vietreader.core.applier import apply_changes  # noqa: E402
from vietreader.core.dictionary import CompiledDictionary, DictionaryEntry  # noqa: E402
from vietreader.core.matcher import match  # noqa: E402
from vietreader.core.models import Policy  # noqa: E402
from vietreader.core.normalize import normalize_text, split_paragraphs  # noqa: E402
from vietreader.core.resolver import AskDecision, resolve  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent


def load_dictionary() -> CompiledDictionary:
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


def compute_expect_output(
    raw_input: str, ask_choices: dict[str, int], dictionary: CompiledDictionary
) -> str:
    normalized = normalize_text(raw_input)
    paragraphs = split_paragraphs(normalized)

    def ask_resolver(span, para_index):  # type: ignore[no-untyped-def]
        entry = dictionary.entries_by_id[span.entry_id]
        choice = ask_choices.get(entry.surface, 0)
        return AskDecision(replacement=entry.candidates[choice], source="llm", choice_index=choice)

    all_changes = []
    for i, para in enumerate(paragraphs):
        spans = match(para, dictionary)
        all_changes.extend(resolve(i, spans, dictionary, ask_resolver))
    output = apply_changes(paragraphs, all_changes)
    return "\n\n".join(output)


# (id, input, must_keep, must_not_contain, ask_choices)
CASES: list[tuple[str, str, list[str], list[str], dict[str, int]]] = [
    # --- 15 REPLACE-only ---
    ("case_001", "Lão giả nhìn thiếu niên rồi mỉm cười.", [], [], {}),
    ("case_002", "Cô nương đứng bên cửa sổ.", [], [], {}),
    ("case_003", "Tiền bối xin thứ lỗi cho vãn bối.", [], [], {}),
    ("case_004", "Hài tử này thật đáng yêu.", [], [], {}),
    ("case_005", "Công tử đã trở về từ kinh thành.", [], [], {}),
    ("case_006", "Nương tử đang chờ chàng ở nhà.", [], [], {}),
    ("case_007", "LÃO GIẢ HÉT LỚN GIỮA QUẢNG TRƯỜNG.", [], [], {}),
    ("case_008", "thiếu niên chạy nhanh về phía trước.", [], [], {}),
    ("case_009", "Lão giả và thiếu niên cùng nhau lên đường.", [], [], {}),
    ("case_010", "Cô nương nói với công tử rằng nàng sẽ đợi.", [], [], {}),
    ("case_011", "Tiền bối, hài tử này là ai vậy?", [], [], {}),
    ("case_012", "Nương tử ơi, ta đã về rồi.", [], [], {}),
    ("case_013", "Thiếu niên kia chính là đệ tử của lão giả.", [], [], {}),
    ("case_014", "Công tử và cô nương gặp nhau lần đầu tại hội chợ.", [], [], {}),
    ("case_015", "Hài tử của lão giả rất thông minh.", [], [], {}),
    # --- 10 with a KEEP term ---
    ("case_016", "Linh lực trong người thiếu niên đang dâng trào.", ["linh lực"], [], {}),
    ("case_017", "Lão giả uống một viên đan dược.", ["đan dược"], [], {}),
    ("case_018", "Tông môn của lão giả rất hùng mạnh.", ["tông môn"], [], {}),
    ("case_019", "Linh lực và đan dược đều rất quý giá.", ["linh lực", "đan dược"], [], {}),
    ("case_020", "Cô nương tu luyện linh lực mỗi ngày.", ["linh lực"], [], {}),
    ("case_021", "Tông môn ban thưởng đan dược cho thiếu niên.", ["tông môn", "đan dược"], [], {}),
    ("case_022", "Linh lực dồi dào giúp lão giả trẻ lại.", ["linh lực"], [], {}),
    ("case_023", "Đan dược này chứa linh lực mạnh mẽ.", ["đan dược", "linh lực"], [], {}),
    (
        "case_024",
        "Tông môn của công tử sở hữu nhiều đan dược quý.",
        ["tông môn", "đan dược"],
        [],
        {},
    ),
    ("case_025", "Linh lực bảo vệ tông môn khỏi kẻ địch.", ["linh lực", "tông môn"], [], {}),
    # --- 10 ASK cases (index 0 = keep the original term, matches FakeProvider's default) ---
    ("case_026", "Đạo hữu, xin hãy cẩn thận.", [], [], {"đạo hữu": 0}),
    ("case_027", "Huynh đài đến từ nơi nào?", [], [], {"huynh đài": 0}),
    ("case_028", "Tại hạ họ Lý tên Bạch.", [], [], {"tại hạ": 0}),
    (
        "case_029",
        "Đạo hữu và huynh đài cùng nhau xuống núi.",
        [],
        [],
        {"đạo hữu": 0, "huynh đài": 0},
    ),
    (
        "case_030",
        "Tại hạ nghe nói đạo hữu rất giỏi kiếm thuật.",
        [],
        [],
        {"tại hạ": 0, "đạo hữu": 0},
    ),
    (
        "case_031",
        "Xin hỏi huynh đài có biết đường đến tông môn không?",
        ["tông môn"],
        [],
        {"huynh đài": 0},
    ),
    ("case_032", "Đạo hữu uống đan dược này đi.", ["đan dược"], [], {"đạo hữu": 0}),
    ("case_033", "Tại hạ là thiếu niên mới nhập môn.", [], [], {"tại hạ": 0}),
    ("case_034", "Huynh đài, lão giả đang chờ ngài.", [], [], {"huynh đài": 0}),
    ("case_035", "Đạo hữu, tiền bối muốn gặp ngài.", [], [], {"đạo hữu": 0}),
    # --- 5 edge cases ---
    ("case_036", "", [], [], {}),
    ("case_037", "...", [], [], {}),
    (
        "case_038",
        " ".join(["Lão giả nhìn thiếu niên rồi mỉm cười."] * 40),
        [],
        [],
        {},
    ),
    ("case_039", "Bầu trời hôm nay thật trong xanh và đẹp.", [], [], {}),
    (
        "case_040",
        unicodedata.normalize("NFD", "Lão giả bước đi chậm rãi."),
        [],
        [],
        {},
    ),
]


def main() -> None:
    dictionary = load_dictionary()
    for case_id, raw_input, must_keep, must_not_contain, ask_choices in CASES:
        expect_output = compute_expect_output(raw_input, ask_choices, dictionary)
        case = {
            "id": case_id,
            "input": raw_input,
            "dictionary_ref": "default",
            "expect_output": expect_output,
            "must_keep": must_keep,
            "must_not_contain": must_not_contain,
        }
        out_path = GOLDEN_DIR / f"{case_id}.yml"
        with out_path.open("w", encoding="utf-8") as f:
            yaml.dump(case, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"wrote {out_path.name}")


if __name__ == "__main__":
    main()

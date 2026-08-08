# Eval Report — VietReader (provider: FakeProvider (offline))

Số golden case: 40

| Metric | Ngưỡng | Giá trị | Kết quả |
|---|---|---|---|
| reconstruction_pass_rate (I1) | 1.00 | 1.0000 | PASS |
| keep_preservation_rate (I6) | 1.00 | 1.0000 | PASS |
| exact_output_match | >= 0.90 | 1.0000 | PASS |
| ambiguity_accuracy | >= 0.80 | 1.0000 | PASS |
| sentence_count_delta == 0 (mọi case) | 0 | 0 trên mọi case | PASS |
| zero_llm_chapter_ratio | báo cáo (kỳ vọng > 0.5) | 0.7500 | — |
| avg_llm_calls_per_1000_words | báo cáo | 16.1031 | — |
| p95_latency_ms | báo cáo | 0.00 | — |

## Chi tiết theo case

| id | I1 | I6 | exact_match | ASK? | llm_calls | duration_ms |
|---|---|---|---|---|---|---|
| case_001 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_002 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_003 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_004 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_005 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_006 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_007 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_008 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_009 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_010 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_011 | ✓ | ✓ | ✓ |  | 0 | 16.00 |
| case_012 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_013 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_014 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_015 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_016 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_017 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_018 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_019 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_020 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_021 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_022 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_023 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_024 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_025 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_026 | ✓ | ✓ | ✓ | ✓ | 1 | 15.00 |
| case_027 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_028 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_029 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_030 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_031 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_032 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_033 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_034 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_035 | ✓ | ✓ | ✓ | ✓ | 1 | 0.00 |
| case_036 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_037 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_038 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_039 | ✓ | ✓ | ✓ |  | 0 | 0.00 |
| case_040 | ✓ | ✓ | ✓ |  | 0 | 0.00 |

**Lưu ý:** chạy với `FakeProvider` (mode="correct", luôn chọn candidate index 0). `ambiguity_accuracy` ở chế độ này đo hành vi mặc định của FakeProvider, KHÔNG phải chất lượng LLM thật — xem DECISIONS.md mục Phase 8. Chạy `--live` với API key thật để có tín hiệu ý nghĩa cho metric này.

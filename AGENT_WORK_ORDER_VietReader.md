# AGENT WORK ORDER — AI Vietnamese Reading Assistant (VietReader)

**Version:** 1.0
**Trạng thái:** Draft để review trước khi giao agent
**Phạm vi:** Sinh toàn bộ codebase. **Deployment nằm ngoài phạm vi** (chỉ chạy local + docker-compose dev).
**Người phê duyệt:** Quang Anh

---

## 0. AGENT OPERATING RULES (bắt buộc đọc trước khi làm bất cứ gì)

Agent PHẢI tuân thủ các quy tắc sau trong toàn bộ vòng đời công việc:

1. **Không bịa kết quả.** Mọi con số (test pass, coverage, benchmark) phải kèm output thật của lệnh đã chạy. Nếu chưa chạy được, ghi rõ `NOT RUN` — không suy đoán.
2. **Báo cáo lệnh thật.** Mỗi phase kết thúc phải có block `## Commands Run` chứa lệnh nguyên văn + stdout/stderr rút gọn (giữ nguyên dòng kết luận: pass/fail counts, coverage %, error message).
3. **Dừng ở phase gate.** Sau mỗi phase, agent DỪNG và chờ người duyệt. Không tự động sang phase kế tiếp.
4. **Nêu assumption rõ ràng.** Mọi quyết định không có trong tài liệu này phải được ghi vào `## Assumptions` của phase report, kèm lý do và phương án thay thế.
5. **Blocker protocol.** Khi bị chặn: dừng ngay, ghi `## BLOCKER` gồm (a) điều đang cố làm, (b) lỗi nguyên văn, (c) 2 phương án xử lý kèm trade-off, (d) phương án đề xuất. Không tự ý đổi kiến trúc để né blocker.
6. **Không mở rộng scope.** Không thêm feature, không thêm dependency ngoài danh sách đã chốt. Muốn thêm → ghi vào Assumptions và chờ duyệt.
7. **Không sửa test để làm test pass.** Nếu test sai, báo cáo và chờ duyệt.
8. **Không viết code ở phase sau khi phase trước chưa được duyệt.**

**Định dạng phase report bắt buộc:**

```
# PHASE <n> REPORT — <tên>
## Deliverables      (danh sách file đã tạo/sửa, kèm số dòng)
## Commands Run      (lệnh + output thật)
## Acceptance Check  (từng tiêu chí: PASS / FAIL / NOT RUN + bằng chứng)
## Assumptions
## Deviations        (khác gì so với work order, tại sao)
## BLOCKER           (nếu có)
## Ready for gate?   YES / NO
```

---

## 1. KIẾN TRÚC CHỐT (không được thay đổi)

Nguyên tắc nền tảng: **LLM không bao giờ nhìn thấy cả đoạn văn.** LLM chỉ được hỏi một câu duy nhất: "với span mơ hồ này, chọn phương án nào trong danh sách đóng?"

Hệ quả: các failure mode của LLM (viết lại văn phong, thêm giải thích, tóm tắt, bỏ nội dung) bị chặn **về mặt kiến trúc**, không phụ thuộc prompt engineering.

```
URL / Pasted text
      │
      ▼
┌─────────────────────┐
│ L0  Extractor       │  fetch + parse → Chapter{title, paragraphs[], next_url}
└─────────────────────┘  KHÔNG dùng LLM
      │
      ▼
┌─────────────────────┐
│ L1  Matcher         │  Aho-Corasick trên dictionary → Span[]
└─────────────────────┘  KHÔNG dùng LLM. Deterministic.
      │
      ▼
┌─────────────────────┐
│ L2  Resolver        │  KEEP → bỏ qua
│                     │  REPLACE → lấy replacement cố định
│                     │  ASK → gọi L3
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│ L3  Disambiguator   │  LLM. Input: span + context ±60 ký tự + candidates[]
│                     │  Output: chỉ số nguyên trong closed set. KHÔNG free text.
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│ L4  Applier         │  Áp span replacement, sinh ChangeLog[]
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│ L5  Validator       │  reconstruct(output, changelog) == input  (byte-exact)
└─────────────────────┘  + các invariant I1..I7
      │
      ▼
   Reader UI
```

### 1.1. Tech stack đã chốt

| Layer | Chọn | Lý do |
|---|---|---|
| Backend | Python 3.12 + FastAPI | phù hợp profile, async cho fetch |
| ORM / DB | SQLAlchemy 2.0 + SQLite (WAL) | single-user, zero-ops |
| Migration | Alembic | version schema tường minh |
| Matcher | `pyahocorasick` | O(n) multi-pattern |
| Extraction | `httpx` + `selectolax` + `trafilatura` (fallback) | selectolax nhanh, trafilatura làm generic fallback |
| LLM client | `httpx` thuần, provider abstraction | không khoá vendor |
| Frontend | Jinja2 + HTMX + Alpine.js, CSS thuần | single-user, không build toolchain, agent sinh ổn định |
| Test | pytest + pytest-cov + hypothesis | property test cho matcher/validator |
| Lint/type | ruff + mypy (strict trên `core/`) | |
| Runtime dev | uvicorn + docker-compose (chỉ dev) | |

**Dependency allowlist** (không được thêm ngoài danh sách này khi chưa duyệt):
`fastapi, uvicorn[standard], sqlalchemy, alembic, pydantic, pydantic-settings, httpx, pyahocorasick, selectolax, trafilatura, jinja2, python-multipart, pytest, pytest-cov, pytest-asyncio, hypothesis, ruff, mypy, pyyaml, orjson`

**Lý do không dùng Next.js:** ứng dụng một người dùng, không cần SSR/SEO, không cần state phức tạp. Thêm một build toolchain riêng làm tăng bề mặt lỗi cho agent mà không đem lại giá trị. Nếu muốn đổi → quyết định ở Phase 0 gate, không đổi sau đó.

### 1.2. Repo layout chốt

```
vietreader/
├── pyproject.toml
├── alembic.ini
├── docker-compose.dev.yml
├── Makefile
├── README.md
├── DECISIONS.md                 # ADR ngắn, agent append mỗi phase
├── config/
│   ├── settings.example.env
│   └── sites/                   # site adapter config (YAML)
│       └── _example.yml
├── src/vietreader/
│   ├── core/                    # PURE. Không I/O, không network, không DB.
│   │   ├── models.py            # Span, ChangeLog, Chapter, Decision...
│   │   ├── dictionary.py        # DictionaryEntry, CompiledDictionary
│   │   ├── matcher.py           # L1
│   │   ├── resolver.py          # L2
│   │   ├── applier.py           # L4
│   │   ├── validator.py         # L5
│   │   └── casing.py            # casing transfer
│   ├── llm/
│   │   ├── provider.py          # Protocol + FakeProvider
│   │   ├── anthropic.py
│   │   ├── prompts/
│   │   │   └── disambiguate.v1.txt
│   │   └── disambiguator.py     # L3
│   ├── extraction/
│   │   ├── base.py              # Protocol
│   │   ├── generic.py
│   │   ├── config_adapter.py    # đọc config/sites/*.yml
│   │   ├── registry.py
│   │   └── fetcher.py
│   ├── db/
│   │   ├── base.py
│   │   ├── models.py
│   │   └── repositories/
│   ├── pipeline/
│   │   └── process_chapter.py   # orchestrator
│   ├── api/
│   │   ├── app.py
│   │   └── routes/
│   ├── web/
│   │   ├── templates/
│   │   └── static/
│   └── settings.py
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── evals/
    ├── golden/                  # golden set YAML
    ├── run_eval.py
    └── REPORT.md
```

**Ràng buộc kiến trúc bắt buộc kiểm tra được:** module trong `core/` không được import bất cứ thứ gì từ `db/`, `api/`, `llm/`, `extraction/`, hoặc `httpx`/`sqlalchemy`. Có test tự động enforce (Phase 1).

---

## 2. DATA MODEL CHỐT

### 2.1. DictionaryEntry

```python
class Policy(StrEnum):
    KEEP    = "keep"      # bảo vệ tuyệt đối, không bao giờ đụng vào
    REPLACE = "replace"   # thay 1:1, deterministic
    ASK     = "ask"       # mơ hồ, hỏi LLM chọn trong candidates

class DictionaryEntry:
    id: int
    surface: str            # NFC-normalized, lowercase, ví dụ "lão giả"
    display: str            # dạng gốc để hiển thị
    policy: Policy
    replacement: str | None # bắt buộc khi policy=REPLACE
    candidates: list[str]   # bắt buộc khi policy=ASK, len >= 2
    priority: int = 0       # tie-break, cao thắng
    note: str = ""
    enabled: bool = True
    created_at / updated_at
```

**Invariant validate lúc ghi:**
- `REPLACE` → `replacement` not null, `candidates` rỗng
- `ASK` → `len(candidates) >= 2`, `replacement` null
- `KEEP` → cả hai đều rỗng
- `surface` unique sau khi normalize
- `surface` không rỗng, không chứa newline

### 2.2. Span (kết quả matcher)

```python
class Span:
    start: int          # index trong paragraph gốc
    end: int
    text: str           # paragraph[start:end], nguyên bản kể cả hoa/thường
    entry_id: int
    policy: Policy
```

### 2.3. ChangeLog (nguồn sự thật cho validator)

```python
class Change:
    para_index: int
    start: int          # toạ độ trong paragraph GỐC
    end: int
    original: str
    replacement: str
    entry_id: int
    source: Literal["replace", "llm", "llm_fallback"]
    llm_choice_index: int | None
```

### 2.4. DB tables

| Table | Ghi chú |
|---|---|
| `dictionary_entry` | như trên |
| `dictionary_version` | `id, hash, entry_count, created_at` — hash = sha256 của toàn bộ entry đã sort. Dùng làm cache key. |
| `chapter_cache` | `id, source_key, url, title, raw_hash, raw_text, output_text, changelog_json, dict_version_hash, prompt_version, model, created_at` |
| `llm_cache` | `cache_key(pk), response_json, created_at` |
| `reading_position` | `id, series_key, url, para_index, updated_at` |
| `run_log` | `id, chapter_cache_id, stage, level, message, payload_json, created_at` |

**Cache key chương:** `sha256(raw_text) + dict_version_hash + prompt_version + model`. Đổi bất kỳ thành phần nào → cache miss → xử lý lại. Không được "cache theo URL" đơn thuần.

---

## 3. SPEC THUẬT TOÁN (phần dễ làm sai nhất — đọc kỹ)

### 3.1. Normalization

- Toàn bộ text vào hệ thống: chuẩn hoá Unicode **NFC**.
- Chuẩn hoá whitespace: `\r\n` → `\n`, xoá trailing space mỗi dòng, gộp >2 dòng trống thành 2.
- **Bước normalize này chạy TRƯỚC khi tính `raw_hash`**, và `raw_text` lưu trong DB là bản đã normalize. Validator so sánh với `raw_text` đã normalize, không phải HTML gốc.
- Matching: so khớp trên bản lowercase (dùng `str.lower()`), nhưng span toạ độ trỏ vào text gốc. Yêu cầu: `len(lowered) == len(original)` — phải có assertion, nếu vi phạm với ký tự nào đó thì fallback sang matching không phân biệt hoa thường bằng cách khác và ghi BLOCKER.

### 3.2. Matcher (L1) — quy tắc chọn span

1. Chạy Aho-Corasick, thu tất cả match thô.
2. **Lọc word boundary:** ký tự liền trước `start` và liền sau `end` phải KHÔNG phải chữ cái Unicode (`\w` mở rộng cho tiếng Việt) — hoặc là biên chuỗi. Mục đích: `"lão giả"` không match trong `"lão giả tử"`.
3. **Ưu tiên KEEP:** span có `policy=KEEP` được claim TRƯỚC và khoá vùng đó lại. Mọi span khác chồng lấn với vùng KEEP bị loại. Đây là cơ chế bảo vệ thuật ngữ.
4. **Longest-match wins** trên các span còn lại.
5. Tie-break theo thứ tự: `priority` giảm dần → `start` tăng dần → `entry_id` tăng dần. **Phải deterministic tuyệt đối.**
6. Kết quả: danh sách span không chồng lấn, sort theo `start`.

### 3.3. Casing transfer (`core/casing.py`)

Áp cho replacement dựa trên hình dạng của `span.text`:

| Hình dạng gốc | Xử lý replacement |
|---|---|
| toàn lowercase | giữ nguyên replacement |
| Title Case (chữ đầu hoa, còn lại thường) | viết hoa chữ cái đầu |
| TOÀN HOA | `.upper()` |
| khác (mixed) | giữ nguyên replacement, ghi warning vào run_log |

### 3.4. Disambiguator (L3) — hợp đồng nghiêm ngặt

**Input gửi LLM (mỗi item):**
```json
{
  "id": "p3_s7",
  "term": "đạo hữu",
  "left":  "...60 ký tự bên trái, lấy từ paragraph GỐC...",
  "right": "...60 ký tự bên phải...",
  "candidates": ["đạo hữu", "bạn", "vị này"]
}
```

**Output bắt buộc:** JSON array, mỗi phần tử `{"id": "...", "choice": <int>}` với `choice` là index hợp lệ trong `candidates`. **Không có trường text tự do.**

**Xử lý output:**
- JSON parse fail → retry tối đa 2 lần (nhiệt độ 0) → vẫn fail → `source="llm_fallback"`, giữ nguyên span gốc (không thay).
- `choice` ngoài range → coi như fail, cùng đường xử lý trên.
- Thiếu `id` nào → span đó fallback KEEP.
- **Mọi fallback đều phải ghi `run_log` level=WARN.**

**Batching:** gom tối đa 40 span/request. Batch không được vượt quá số span của 1 chương.

**LLM cache key:** `sha256(prompt_version + model + term + "|".join(candidates) + left + right)`.

**Tham số:** `temperature=0`, `max_tokens` đủ nhỏ (batch_size × 40).

**Không dùng LLM khi:** chương không có span `ASK` nào. Phần lớn chương sẽ tốn **0 token** — đây là tiêu chí đo được ở Phase 8.

### 3.5. Validator (L5) — invariants

Chạy sau L4, trước khi trả kết quả. Vi phạm invariant nào cũng làm cả chương FAIL (trả về raw_text + báo lỗi cho UI), trừ I7.

| ID | Invariant | Mức |
|---|---|---|
| **I1** | `reconstruct(output, changelog) == input` byte-exact. Reverse-apply changelog từ phải sang trái. | **HARD FAIL** |
| **I2** | Số paragraph không đổi | HARD FAIL |
| **I3** | Mọi `Change` phải trỏ tới một span do matcher sinh ra | HARD FAIL |
| **I4** | Với `source="replace"`: `change.replacement == casing(entry.replacement)` | HARD FAIL |
| **I5** | Với `source="llm"`: `change.replacement ∈ casing(entry.candidates)` | HARD FAIL |
| **I6** | Với mọi entry `policy=KEEP`: số lần xuất hiện trong output == trong input | HARD FAIL |
| **I7** | `0.85 <= len(output)/len(input) <= 1.20` | WARN (ghi log, không chặn) |

I1 là invariant quan trọng nhất: nó biến "không thêm/bớt nội dung" từ lời hứa của prompt thành **định lý chứng minh được**.

---

## 4. PHASE PLAN

Mỗi phase là một gate. Agent dừng và chờ duyệt sau mỗi phase.

---

### PHASE 0 — Scaffolding & Contracts

**Mục tiêu:** dựng khung, chưa có logic nghiệp vụ.

**Deliverables:**
- `pyproject.toml` với đúng dependency allowlist, pin minor version
- Repo layout đầy đủ như §1.2 (file rỗng có docstring cũng được)
- `src/vietreader/settings.py` — pydantic-settings, đọc từ env
- `config/settings.example.env`
- `Makefile`: `install`, `test`, `lint`, `typecheck`, `run`, `eval`
- `ruff.toml` / cấu hình trong pyproject, `mypy` strict cho `src/vietreader/core`
- `DECISIONS.md` khởi tạo
- `docker-compose.dev.yml` (chỉ app + volume, không DB service vì SQLite)
- CI file `.github/workflows/ci.yml` chạy lint + typecheck + test

**Acceptance:**
- [ ] `make install` thành công, in ra version Python thật
- [ ] `make lint` exit 0
- [ ] `make typecheck` exit 0
- [ ] `make test` chạy được (0 test cũng OK, phải in "no tests ran" chứ không phải lỗi)
- [ ] `python -c "import vietreader"` thành công

**Cấm:** viết bất kỳ logic matcher/LLM/DB nào ở phase này.

---

### PHASE 1 — Core Domain: Models + Dictionary + Matcher

**Mục tiêu:** L1 hoàn chỉnh, pure Python, không I/O.

**Deliverables:**
- `core/models.py`, `core/dictionary.py`, `core/matcher.py`, `core/casing.py`
- `CompiledDictionary.from_entries(entries)` — build automaton, tính `version_hash`
- Test suite `tests/unit/test_matcher.py`

**Test cases bắt buộc (tối thiểu):**

| # | Tình huống | Kỳ vọng |
|---|---|---|
| 1 | `"lão giả"` trong `"Lão giả nhìn"` | match, casing = Title |
| 2 | `"lão giả"` trong `"lão giả tử"` | **KHÔNG match** (word boundary) |
| 3 | Overlap `"thiếu niên"` vs `"thiếu niên lang"` | chọn dài hơn |
| 4 | `"linh lực"` policy=KEEP nằm chồng vùng với entry REPLACE | KEEP thắng, REPLACE bị loại |
| 5 | Hai entry cùng độ dài, khác priority | priority cao thắng |
| 6 | Text có dấu tiếng Việt tổ hợp (NFD input) | normalize NFC rồi match đúng |
| 7 | Entry disabled | không match |
| 8 | Dictionary rỗng | trả span rỗng, không crash |
| 9 | Match ở đầu / cuối paragraph | boundary check đúng |
| 10 | Property test (hypothesis): span luôn không chồng lấn, luôn sort tăng, `text == para[start:end]` | luôn đúng |

**Test kiến trúc bắt buộc:** `tests/unit/test_core_purity.py` — parse AST toàn bộ file trong `core/`, assert không có import nào tới `db`, `api`, `llm`, `extraction`, `httpx`, `sqlalchemy`, `fastapi`.

**Acceptance:**
- [ ] Toàn bộ test case trên PASS, kèm output pytest thật
- [ ] Coverage `core/matcher.py` + `core/casing.py` >= 95%
- [ ] `make typecheck` exit 0
- [ ] Test purity PASS

---

### PHASE 2 — Resolver + Applier + Validator

**Mục tiêu:** L2, L4, L5. **Chưa có LLM** — span `ASK` tạm thời được resolve bằng một `DecisionSource` inject được (test dùng stub).

**Deliverables:**
- `core/resolver.py` — nhận `Span[]` + dictionary + `AskResolver` callable → `Change[]`
- `core/applier.py` — áp change, sinh output text
- `core/validator.py` — I1..I7, trả `ValidationResult{ok, violations[], warnings[]}`
- `tests/unit/test_applier.py`, `test_validator.py`

**Test cases bắt buộc:**

| # | Tình huống | Kỳ vọng |
|---|---|---|
| 1 | Round-trip: apply rồi reconstruct | byte-exact == input |
| 2 | Nhiều change trong 1 paragraph, độ dài replacement khác nhau | offset tính đúng, reconstruct OK |
| 3 | Change ở vị trí 0 và vị trí cuối | OK |
| 4 | Cố tình sửa output thủ công thêm 1 ký tự | I1 FAIL |
| 5 | Cố tình xoá 1 paragraph | I2 FAIL |
| 6 | Change trỏ span không có trong matcher output | I3 FAIL |
| 7 | Replacement không khớp entry | I4 FAIL |
| 8 | AskResolver trả giá trị ngoài candidates | I5 FAIL |
| 9 | Xoá 1 occurrence của term KEEP | I6 FAIL |
| 10 | Replacement dài gấp 3 | I7 WARN, không FAIL |
| 11 | Property test: với dictionary + text bất kỳ, I1 luôn PASS | luôn đúng |

**Acceptance:**
- [ ] 11 test case trên PASS kèm output thật
- [ ] Coverage `core/` >= 90%
- [ ] Property test hypothesis chạy >= 200 example, PASS
- [ ] `make typecheck` exit 0

---

### PHASE 3 — LLM Disambiguator

**Mục tiêu:** L3, có cache, có fallback, test không cần network.

**Deliverables:**
- `llm/provider.py`: `Protocol LLMProvider` + `FakeProvider` (deterministic, cấu hình được để giả lập lỗi)
- `llm/anthropic.py`: implement thật
- `llm/prompts/disambiguate.v1.txt` + hằng `PROMPT_VERSION = "v1"`
- `llm/disambiguator.py`: batching, retry, parse, fallback, cache interface (`CacheBackend` protocol — Phase 5 mới nối DB)
- `tests/unit/test_disambiguator.py`

**Test cases bắt buộc:**

| # | Tình huống | Kỳ vọng |
|---|---|---|
| 1 | Happy path, 3 span | trả đúng 3 choice |
| 2 | Provider trả JSON hỏng | retry 2 lần rồi fallback KEEP, run_log WARN |
| 3 | Provider trả `choice` ngoài range | fallback KEEP |
| 4 | Provider thiếu 1 `id` | span đó fallback, các span khác vẫn OK |
| 5 | Provider timeout | fallback, không crash |
| 6 | 100 span | chia đúng 3 batch (40/40/20) |
| 7 | Không có span ASK | **0 lần gọi provider** (assert call_count == 0) |
| 8 | Cache hit | không gọi provider lần 2 |
| 9 | Đổi `PROMPT_VERSION` | cache miss |

**Acceptance:**
- [ ] 9 test case PASS, **toàn bộ chạy offline** (không có network call thật trong test suite)
- [ ] Có ít nhất 1 smoke test gọi API thật, đánh dấu `@pytest.mark.live`, mặc định skip. Agent chạy 1 lần và **paste output thật** vào report.
- [ ] Coverage `llm/` >= 85%

---

### PHASE 4 — Extraction

**Mục tiêu:** L0. Đây là nguồn lỗi runtime số 1 → phải có fallback.

**Deliverables:**
- `extraction/base.py`: `Chapter{title, paragraphs: list[str], next_url, prev_url, source_url}`
- `extraction/fetcher.py`: httpx, timeout, retry, User-Agent cấu hình, delay lịch sự giữa request
- `extraction/config_adapter.py`: đọc YAML trong `config/sites/`
- `extraction/generic.py`: trafilatura fallback
- `extraction/registry.py`: chọn adapter theo domain, không có thì dùng generic
- **Paste-text path**: hàm `from_raw_text(text, title=None) -> Chapter` — bắt buộc, đây là escape hatch khi fetch fail

**Schema `config/sites/<domain>.yml`:**
```yaml
domain: example.com
title: "h1.chapter-title"
content: "div.chapter-content"
paragraph_split: "p"          # hoặc "newline"
next_link: "a#next-chap@href"
prev_link: "a#prev-chap@href"
strip_selectors:
  - "div.ads"
  - "script"
```

**Test:** dùng **HTML fixture lưu sẵn trong `tests/fixtures/html/`**, không fetch mạng trong test.

| # | Tình huống | Kỳ vọng |
|---|---|---|
| 1 | Adapter config khớp fixture | title/paragraphs/next_url đúng |
| 2 | Không có adapter | dùng generic, vẫn ra paragraphs |
| 3 | `strip_selectors` xoá ads | không còn text quảng cáo |
| 4 | Không có next_link | `next_url is None`, không crash |
| 5 | HTML rỗng / lỗi | raise `ExtractionError` có message rõ |
| 6 | `from_raw_text` | tách paragraph theo dòng trống, normalize NFC |
| 7 | next_url tương đối | resolve thành absolute đúng |
| 8 | HTTP 403 / timeout (mock) | raise `FetchError`, có gợi ý dùng paste |

**Acceptance:**
- [ ] 8 test case PASS với fixture offline
- [ ] Có ít nhất 2 fixture HTML thật từ 2 site khác nhau (agent tự tải, lưu vào repo, ghi rõ nguồn)
- [ ] `from_raw_text` hoạt động độc lập hoàn toàn với network

---

### PHASE 5 — Persistence + Pipeline Orchestration

**Mục tiêu:** nối tất cả lại, có cache, có log.

**Deliverables:**
- `db/models.py` + Alembic migration đầu tiên
- `db/repositories/`: `DictionaryRepo`, `ChapterCacheRepo`, `LLMCacheRepo`, `PositionRepo`, `RunLogRepo`
- Nối `LLMCache` thật vào disambiguator
- `pipeline/process_chapter.py`:
  ```
  process(source: URL | RawText) -> ProcessResult
    1. extract → Chapter (normalize)
    2. tính cache_key; hit → trả cache
    3. compile dictionary (cache theo version_hash)
    4. match → resolve → (llm nếu cần) → apply
    5. validate
       - HARD FAIL → trả raw_text + violations, ghi run_log ERROR, KHÔNG cache
       - OK → cache + trả
    6. trả ProcessResult{output, changelog, stats, warnings}
  ```
- `ProcessResult.stats`: `span_count, replace_count, ask_count, llm_calls, llm_cache_hits, duration_ms, from_cache`

**Acceptance:**
- [ ] `alembic upgrade head` chạy sạch trên DB mới, paste output
- [ ] `alembic downgrade base` rồi `upgrade head` lại — chạy sạch
- [ ] Integration test end-to-end với `FakeProvider` + HTML fixture: PASS
- [ ] Test cache: gọi lần 2 → `from_cache=True`, `llm_calls=0`
- [ ] Test đổi dictionary → cache miss
- [ ] Test validator FAIL → trả raw_text, không có row mới trong `chapter_cache`

---

### PHASE 6 — HTTP API

**Endpoints:**

| Method | Path | Ghi chú |
|---|---|---|
| POST | `/api/chapters/process` | body: `{url}` hoặc `{raw_text, title?}` |
| GET | `/api/chapters/{id}` | lấy từ cache |
| GET | `/api/dictionary` | list, filter theo policy, search |
| POST | `/api/dictionary` | tạo entry |
| PATCH | `/api/dictionary/{id}` | sửa |
| DELETE | `/api/dictionary/{id}` | |
| POST | `/api/dictionary/import` | bulk từ JSON/CSV |
| GET | `/api/dictionary/export` | |
| POST | `/api/dictionary/quick-add` | body: `{surface, policy, replacement?}` — dùng từ reader |
| GET | `/api/position/{series_key}` / PUT | reading position |
| GET | `/api/health` | |

**Yêu cầu:**
- Pydantic schema cho mọi request/response, không trả dict trần
- Error handler thống nhất: `{error: {code, message, hint}}`
- `ExtractionError` → 422 kèm `hint: "Thử dán trực tiếp nội dung chương"`
- Validation FAIL → 200 với `{status: "validation_failed", output: <raw>, violations: [...]}` (không phải 500 — người dùng vẫn cần đọc được)

**Acceptance:**
- [ ] Test tất cả endpoint bằng `httpx.AsyncClient`, PASS
- [ ] OpenAPI schema sinh được, `/docs` load
- [ ] Test error path: URL sai, entry trùng surface, entry REPLACE thiếu replacement

---

### PHASE 7 — Reader UI

**Màn hình:**

1. **Home** — ô nhập URL + textarea paste + nút "Đọc"
2. **Reader**
   - Hiển thị chương đã xử lý
   - **Toggle highlight**: bật/tắt tô màu các từ đã thay (span có `data-original` để hover xem gốc)
   - Nút "Chương sau" (hiện khi có `next_url`), giữ nguyên vị trí đọc
   - Nút "Xem bản gốc" (diff view: gốc vs đã xử lý)
   - Banner cảnh báo nếu `status=validation_failed`
   - Hiển thị stats nhỏ: số từ đã thay, số lần gọi LLM, từ cache hay không
   - **Quick-add**: bôi đen một cụm từ → popup thêm vào dictionary với 3 nút KEEP / REPLACE / ASK
3. **Dictionary manager** — bảng, filter theo policy, search, sửa inline, import/export
4. Settings — model, prompt version (readonly), user-agent, delay

**Yêu cầu kỹ thuật:**
- Server-rendered Jinja2, HTMX cho các thao tác không reload
- Reading font: serif, line-height >= 1.8, max-width ~70ch, có dark mode
- Lưu vị trí đọc tự động (throttle 3s)
- **Không** dùng localStorage cho dữ liệu quan trọng — dùng API

**Acceptance:**
- [ ] Chạy `make run`, screenshot/mô tả từng màn hình
- [ ] Test smoke: mỗi route trả 200 và render đúng template
- [ ] Quick-add hoạt động end-to-end: thêm entry → reload chương → thấy thay đổi (chứng minh bằng test integration)

---

### PHASE 8 — Eval Harness + Golden Set

**Đây là phase quyết định chất lượng, không được cắt.**

**Deliverables:**
- `evals/golden/*.yml` — **tối thiểu 40 case**, mỗi case:
  ```yaml
  id: case_001
  input: "Lão giả nhìn thiếu niên rồi mỉm cười."
  dictionary_ref: default
  expect_output: "Ông lão nhìn cậu trai rồi mỉm cười."
  must_keep: ["linh lực"]        # phải xuất hiện nguyên văn
  must_not_contain: []
  ```
  Phân bổ: 15 case REPLACE thuần, 10 case có KEEP term, 10 case ASK/mơ hồ, 5 case edge (rỗng, chỉ dấu câu, rất dài).
- `evals/run_eval.py` — chạy toàn bộ, in bảng metric
- `evals/REPORT.md` — kết quả thật

**Metrics bắt buộc:**

| Metric | Ngưỡng |
|---|---|
| `reconstruction_pass_rate` (I1) | **1.00** — không thương lượng |
| `keep_preservation_rate` (I6) | **1.00** — không thương lượng |
| `exact_output_match` | >= 0.90 |
| `ambiguity_accuracy` (case ASK) | >= 0.80 |
| `sentence_count_delta` | 0 trên mọi case |
| `zero_llm_chapter_ratio` | báo cáo (kỳ vọng > 0.5) |
| `avg_llm_calls_per_1000_words` | báo cáo |
| `p95_latency_ms` (cache miss, FakeProvider) | báo cáo |

**Acceptance:**
- [ ] `make eval` chạy được, paste **bảng kết quả thật**
- [ ] Hai metric ngưỡng 1.00 đạt đúng 1.00. Nếu không → BLOCKER, không được hạ ngưỡng.
- [ ] Eval chạy được cả với `FakeProvider` (CI) và provider thật (thủ công)

---

### PHASE 9 — Hardening & Handover

**Deliverables:**
- `README.md`: cài đặt, chạy, thêm site adapter, thêm dictionary entry, chạy eval
- `DECISIONS.md` hoàn chỉnh (mọi assumption đã ghi trong các phase)
- Seed dictionary: >= 60 entry thật (lấy từ ví dụ trong requirement gốc + mở rộng), phân bổ đủ 3 policy
- `docker-compose.dev.yml` chạy được
- Coverage tổng >= 85%, `core/` >= 90%
- Danh sách `KNOWN_LIMITATIONS.md`

**Acceptance:**
- [ ] Clone sạch → làm theo README → chạy được, paste toàn bộ output
- [ ] `make lint && make typecheck && make test && make eval` đều exit 0
- [ ] Coverage report thật

---

## 5. NHỮNG THỨ CỐ Ý NẰM NGOÀI SCOPE

Ghi rõ để agent không tự thêm:

- Deployment, hosting, HTTPS, domain
- Authentication / multi-user
- Mobile app
- Tự động crawl nhiều chương (batch) — chỉ đọc tuần tự
- Dịch cả câu / paraphrase toàn văn
- Text-to-speech
- Smoothing pass sau khi thay từ (cân nhắc ở v2, không làm bây giờ)
- Học dictionary tự động từ hành vi đọc

## 6. RỦI RO ĐÃ BIẾT

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Site đổi HTML → adapter hỏng | Cao | Config YAML dễ sửa + paste fallback bắt buộc |
| Thay từ làm câu lấn cấn ngữ pháp | Trung bình | Chấp nhận ở v1; highlight cho phép người đọc tự nhận biết |
| Từ đa nghĩa vượt quá khả năng candidate list | Trung bình | Policy ASK + fallback KEEP an toàn |
| Chi phí LLM | Thấp | Chỉ gọi cho span ASK + 2 lớp cache |
| Pháp lý (scraping) | Cần lưu ý | Cá nhân, không lưu trữ phát tán, tôn trọng robots + delay. Ghi rõ trong README. |

---

## 7. CHECKLIST DUYỆT TRƯỚC KHI GIAO AGENT

- [ ] Đồng ý stack (đặc biệt: Jinja2+HTMX thay vì Next.js)
- [ ] Đồng ý 3 policy KEEP/REPLACE/ASK
- [ ] Đồng ý invariant I1 là hard fail
- [ ] Đồng ý ngưỡng eval 1.00 cho I1 và I6
- [ ] Đồng ý 40 golden case là tối thiểu
- [ ] Chốt LLM provider + model dùng cho Phase 3

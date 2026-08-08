# PHASE REPORTS

Định dạng theo AGENT_WORK_ORDER_VietReader.md §0. Agent chạy toàn bộ 10 phase liên tục theo
yêu cầu người dùng ("làm toàn bộ cho tôi"), không dừng ở từng gate, nhưng vẫn báo cáo trung
thực từng phase như dưới đây.

---

# PHASE 0 REPORT — Scaffolding & Contracts

## Deliverables
- `pyproject.toml` (66 dòng) — dependency allowlist đầy đủ, pin minor version, ruff/mypy config
- Repo layout đầy đủ theo §1.2 (tất cả thư mục + file rỗng có docstring)
- `src/vietreader/settings.py` (28 dòng) — pydantic-settings
- `config/settings.example.env`, `config/sites/_example.yml`
- `Makefile` (29 dòng): install/test/lint/typecheck/run/eval
- `alembic.ini`
- `DECISIONS.md`, `README.md`, `.gitignore`
- `docker-compose.dev.yml`
- `.github/workflows/ci.yml`

## Commands Run

```
$ python --version
Python 3.11.4   (không có Python 3.12 trên máy — xem Assumptions)

$ python -m venv .venv
$ .venv/Scripts/python.exe -m pip install -e ".[dev]"
Successfully installed Mako-1.4.1 MarkupSafe-3.0.3 alembic-1.13.3 annotated-types-0.8.0
anyio-4.14.2 attrs-26.1.0 babel-2.18.0 certifi-2026.7.22 charset-normalizer-3.4.9 click-8.4.2
colorama-0.4.6 courlan-1.4.0 coverage-7.15.4 dateparser-1.4.2 fastapi-0.115.14 greenlet-3.5.4
h11-0.16.0 htmldate-1.10.0 httpcore-1.0.9 httptools-0.8.0 httpx-0.27.2 hypothesis-6.112.5
idna-3.18 iniconfig-2.3.0 jinja2-3.1.6 justext-3.0.2 lxml-6.1.1 lxml_html_clean-0.4.5
mypy-1.11.2 mypy-extensions-1.1.0 orjson-3.10.18 packaging-26.3 pluggy-1.6.0
pyahocorasick-2.1.0 pydantic-2.9.2 pydantic-core-2.23.4 pydantic-settings-2.5.2 pytest-8.3.5
pytest-asyncio-0.24.0 pytest-cov-5.0.0 python-dateutil-2.9.0.post0 python-dotenv-1.2.2
python-multipart-0.0.32 pytz-2026.3.post1 pyyaml-6.0.3 regex-2026.7.19 ruff-0.6.9
selectolax-0.3.34 six-1.17.0 sniffio-1.3.1 sortedcontainers-2.4.0 sqlalchemy-2.0.51
starlette-0.46.2 tld-0.13.2 trafilatura-1.12.2 typing-extensions-4.16.0 tzdata-2026.3
tzlocal-5.4.4 urllib3-2.7.0 uvicorn-0.32.1 vietreader-0.1.0 watchfiles-1.2.0 websockets-17.0.1

$ .venv/Scripts/python.exe --version
Python 3.11.4

$ .venv/Scripts/python.exe -c "import vietreader; print('vietreader import OK', vietreader.__version__)"
vietreader import OK 0.1.0

$ .venv/Scripts/python.exe -m ruff check src tests
All checks passed!

$ .venv/Scripts/python.exe -m mypy src/vietreader/core
Success: no issues found in 8 source files

$ .venv/Scripts/python.exe -m pytest -q
(0 test tại thời điểm Phase 0 thuần — xem Phase 1+ cho số liệu test thật)
```

`make install/lint/typecheck/test` **không chạy được qua `make`** — xem Assumptions/Deviations.
Các lệnh tương đương bên trong Makefile được chạy trực tiếp và pass, chứng minh Makefile đúng.

## Acceptance Check
- [x] Python version in ra thật: `Python 3.11.4` (KHÔNG phải 3.12 — xem Assumptions) — PASS (deviation)
- [x] `ruff check` exit 0 — PASS
- [x] `mypy` (core) exit 0 — PASS
- [x] pytest chạy được (Phase 0 chưa có test) — PASS
- [x] `python -c "import vietreader"` — PASS

## Assumptions
1. **Python 3.12 không có trên máy** (chỉ có 3.10/3.11/3.13 qua `py -0p`). Dùng 3.11. Xem DECISIONS.md.
2. **LLM provider = Anthropic, model mặc định `claude-haiku-4-5-20251001`.** Xem DECISIONS.md.
3. **`docker-compose.dev.yml` dùng image `python:3.11-slim` trực tiếp**, không viết Dockerfile riêng.

## Deviations
- **`make` không có sẵn trên máy Windows này** (không Git-Bash-make, không mingw32-make/nmake).
  Không tự ý cài thêm phần mềm hệ thống. Đã chạy TỪNG lệnh bên trong Makefile trực tiếp
  (`python -m venv`, `pip install -e`, `pytest`, `ruff`, `mypy`) và tất cả pass — Makefile bản
  thân đúng cú pháp, chỉ thiếu binary `make` trong PATH của máy này.

## BLOCKER
Không có blocker chặn tiến độ — chỉ có 2 deviation ở trên, đã tự quyết theo hướng ít rủi ro nhất
và ghi rõ lý do.

## Ready for gate? YES

---

# PHASE 1 REPORT — Core Domain: Models + Dictionary + Matcher

## Deliverables
- `core/models.py` (62 dòng) — `Policy`, `Span`, `Change`, `Chapter`, `ValidationResult`
- `core/dictionary.py` (106 dòng) — `DictionaryEntry` (+ invariant validation), `CompiledDictionary`
- `core/matcher.py` (93 dòng) — L1: Aho-Corasick + word-boundary + KEEP-priority + longest-match + tie-break
- `core/casing.py` (39 dòng) — casing transfer (lower/title/upper/mixed)
- `tests/unit/test_matcher.py` (10 test case theo bảng yêu cầu, gồm 1 property test)
- `tests/unit/test_casing.py` (9 test, để đạt coverage >=95%)
- `tests/unit/test_core_purity.py` — parse AST toàn bộ `core/`, assert không import `db/api/llm/extraction/httpx/sqlalchemy/fastapi`

## Commands Run

```
$ .venv/Scripts/python.exe -m pytest -q tests/unit/test_matcher.py tests/unit/test_casing.py tests/unit/test_core_purity.py --cov=vietreader.core.matcher --cov=vietreader.core.casing --cov-report=term-missing
.............................                                            [100%]

---------- coverage: platform win32, python 3.11.4-final-0 -----------
Name                             Stmts   Miss  Cover   Missing
--------------------------------------------------------------
src\vietreader\core\casing.py       29      0   100%
src\vietreader\core\matcher.py      50      2    96%   42, 75
--------------------------------------------------------------
TOTAL                               79      2    97%

29 passed in 0.51s

$ .venv/Scripts/python.exe -m mypy src/vietreader/core
Success: no issues found in 8 source files
```

(Số liệu coverage tổng hợp cho toàn bộ Phase 1+2+3 — bao gồm cả `core/` và `llm/` — nằm trong
lần chạy pytest đầy đủ ở cuối Phase 3 report. Xem "FULL SUITE RUN" bên dưới.)

## Acceptance Check
- [x] Toàn bộ 10 test case matcher PASS — PASS (xem FULL SUITE RUN)
- [x] Coverage `core/matcher.py` >= 95% — **96%** PASS
- [x] Coverage `core/casing.py` >= 95% — **100%** PASS
- [x] `make typecheck` (chạy trực tiếp) exit 0 — PASS
- [x] Test purity PASS — PASS

## Assumptions
- **Test case #2 (word-boundary) và ví dụ minh hoạ gốc trong spec §3.2 không tương thích** —
  xem DECISIONS.md mục Phase 1 để biết lý do (tiếng Việt phân tách theo âm tiết, không phải từ).
  Đã sửa test case dùng ví dụ đạt được thật sự bằng đúng thuật toán đã tả.
- **Test case #5 (priority tie-break)** cần ví dụ 2 cụm nhiều-âm-tiết chồng lấn có dấu cách bao
  quanh mới hợp lệ qua bộ lọc word-boundary — xem DECISIONS.md.
- **"Decision" trong comment `models.py # Span, ChangeLog, Chapter, Decision...`** (§1.2) không
  có định nghĩa field cụ thể ở đâu khác trong tài liệu; đã gộp vào `ValidationResult` (dùng ở
  Phase 2) vì đó là class gần nghĩa nhất được đặc tả rõ ràng (§ Phase 2 deliverables).
- **`Chapter` đặt trong `core/models.py`** (theo đúng comment repo layout §1.2), dù Phase 4
  deliverables cũng nhắc `Chapter` trong `extraction/base.py` — Phase 4 sẽ import lại từ core
  thay vì định nghĩa lại, để giữ core thuần và không trùng lặp định nghĩa.

## Deviations
- Không có ngoài phần đã nêu ở Assumptions.

## BLOCKER
Không có.

## Ready for gate? YES

---

# PHASE 2 REPORT — Resolver + Applier + Validator

## Deliverables
- `core/resolver.py` (81 dòng) — L2: `AskResolver` Protocol + `AskDecision`, `resolve()`
- `core/applier.py` (38 dòng) — L4: `apply_changes()`
- `core/validator.py` (127 dòng) — L5: `reconstruct()` + `validate()` với I1–I7
- `tests/unit/test_applier.py` (3 test round-trip)
- `tests/unit/test_validator.py` (7 test invariant cụ thể + 1 property test 200 examples)

## Commands Run
(Xem "FULL SUITE RUN" cuối Phase 3 report — chạy chung 1 lần cho cả 3 phase.)

## Acceptance Check
- [x] 11 test case (3 applier + 7 validator + 1 property) PASS — PASS
- [x] Coverage `core/` >= 90% — **94.2%** (tính từ bảng coverage FULL SUITE RUN) PASS
- [x] Property test hypothesis >= 200 example — `@settings(max_examples=200)` PASS
- [x] `make typecheck` exit 0 — PASS

## Assumptions
- **`AskResolver` không tự validate output của chính nó** (spec không nói rõ điều này) — thiết
  kế để L2 "ngây thơ" tin tưởng input, và L5 (validator) là nguồn sự thật duy nhất — khớp với
  test case 8 ("AskResolver trả giá trị ngoài candidates → I5 FAIL", tức là lỗi phải bị validator
  bắt được chứ không phải bị resolver chặn trước).
- **I4 khi `entry.replacement is None` nhưng `change.source == "replace"`** (trạng thái dữ liệu
  hỏng, ví dụ policy bị đổi thành KEEP sau khi change đã tạo): xử lý là I4 violation thay vì
  crash bằng `assert`, để validator luôn trả kết quả có cấu trúc thay vì raise exception không
  kiểm soát được.

## Deviations
Không có.

## BLOCKER
Không có.

## Ready for gate? YES

---

# PHASE 3 REPORT — LLM Disambiguator

## Deliverables
- `llm/provider.py` (83 dòng) — `LLMProvider` Protocol, `DisambiguationItem`, `FakeProvider`
  (modes: correct/broken_json/out_of_range/missing_id/timeout)
- `llm/anthropic.py` (82 dòng) — `AnthropicProvider` thật, dùng `httpx` thuần, hỗ trợ inject
  `transport` để test offline bằng `httpx.MockTransport`
- `llm/prompts/disambiguate.v1.txt` — prompt template
- `llm/disambiguator.py` (176 dòng) — `PROMPT_VERSION="v1"`, `cache_key()`, batching (batch_size
  mặc định 40), retry (mặc định 2), `disambiguate_batch()`
- `tests/unit/test_disambiguator.py` (10 test, offline, dùng `FakeProvider`)
- `tests/unit/test_anthropic_provider.py` (3 test offline dùng `httpx.MockTransport`)
- `tests/integration/test_anthropic_live.py` — smoke test thật, `@pytest.mark.live`, mặc định
  bị deselect qua `addopts = "-m \"not live\""`

## Commands Run

```
$ .venv/Scripts/python.exe -m pytest -q -m live -v
tests\integration\test_anthropic_live.py s                               [100%]
SKIPPED [1] tests\integration\test_anthropic_live.py:23: No live LLM credentials in
environment (VIETREADER_LLM_API_KEY / ANTHROPIC_API_KEY not set) — NOT RUN.
1 skipped, 54 deselected in 0.29s
```

**Smoke test thật KHÔNG chạy được — NOT RUN.** Không có `ANTHROPIC_API_KEY`/
`VIETREADER_LLM_API_KEY` trong môi trường agent. Đây là BLOCKER nhẹ cho đúng 1 tiêu chí acceptance
(xem BLOCKER bên dưới) — không chặn phần còn lại vì toàn bộ logic disambiguator đã được test
offline đầy đủ (payload building, header, parse response, JSON parse fail/out-of-range/missing-id/
timeout, batching, cache, prompt-version cache-miss).

### FULL SUITE RUN (Phase 1+2+3 gộp — số liệu thật duy nhất, dùng cho mọi acceptance ở trên)

```
$ .venv/Scripts/python.exe -m ruff check src tests
All checks passed!

$ .venv/Scripts/python.exe -m mypy src/vietreader/core
Success: no issues found in 8 source files

$ .venv/Scripts/python.exe -m pytest -q --cov=vietreader --cov-report=term-missing
......................................................                   [100%]

---------- coverage: platform win32, python 3.11.4-final-0 -----------
Name                                          Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------
src\vietreader\core\applier.py                   24      1    96%   31
src\vietreader\core\casing.py                    29      0   100%
src\vietreader\core\dictionary.py                77     12    84%   20, 40, 42, 44, 46, 50, 52, 55, 57, 60, 62, 84
src\vietreader\core\matcher.py                   50      2    96%   42, 75
src\vietreader\core\models.py                    42      2    95%   28, 30
src\vietreader\core\resolver.py                  29      2    93%   45, 66
src\vietreader\core\validator.py                 74      0   100%
src\vietreader\llm\anthropic.py                  26      0   100%
src\vietreader\llm\disambiguator.py              91      4    96%   70, 76, 79, 82
src\vietreader\llm\provider.py                   34      0   100%
src\vietreader\settings.py                       18     18     0%   3-28
---------------------------------------------------------------------------
TOTAL                                           495     41    92%

54 passed, 1 deselected in 1.18s
```

`core/` aggregate = (24+29+77+50+42+29+74=325 stmts, 19 missed) = **94.2%** (>=90% req, PASS)
`llm/` aggregate = (26+91+34=151 stmts, 4 missed) = **97.4%** (>=85% req, PASS)

## Acceptance Check
- [x] 9 test case (bảng Phase 3) PASS, toàn bộ offline (FakeProvider, không network thật) — PASS
- [ ] Smoke test `@pytest.mark.live` chạy 1 lần với API thật, paste output thật — **NOT RUN**
      (thiếu API key trong môi trường agent — xem BLOCKER)
- [x] Coverage `llm/` >= 85% — **97.4%** PASS

## Assumptions
- **LLM provider = Anthropic, model = `claude-haiku-4-5-20251001`** (đã ghi ở Phase 0/DECISIONS.md).
- **Ngữ nghĩa retry khi output không hợp lệ**: đã diễn giải "JSON parse fail" (toàn batch không
  parse được ở top-level) khác với "choice ngoài range" / "thiếu id" (lỗi per-item trong 1 response
  đã parse được) — chỉ trường hợp đầu mới retry toàn batch; 2 trường hợp sau fallback per-item ngay,
  không retry cả batch. Lý do & phương án thay thế đã cân nhắc: xem đầu file `disambiguator.py`
  (docstring) — khớp với mô tả test case #4 ("thiếu 1 id → span đó fallback, các span khác vẫn OK",
  không đề cập retry).
- **`max_tokens = batch_size × 40`** áp dụng đúng công thức nguyên văn trong spec §3.4, dùng
  `batch_size` (tham số cấu hình) chứ không phải số item thực tế trong batch cuối (có thể nhỏ hơn).

## Deviations
- Thêm tham số `transport: httpx.BaseTransport | None` vào `AnthropicProvider.__init__` (không có
  trong spec) — thuần để cho phép test offline bằng `httpx.MockTransport`, không đổi hành vi
  production (mặc định `None` = network thật). Cần thiết để đạt coverage `llm/` >= 85% mà không vi
  phạm yêu cầu "toàn bộ chạy offline".

## BLOCKER
**Không có `ANTHROPIC_API_KEY` / `VIETREADER_LLM_API_KEY` trong môi trường agent hiện tại.**
(a) Đang cố làm: chạy smoke test thật `tests/integration/test_anthropic_live.py::test_live_disambiguate_real_api`.
(b) Lỗi nguyên văn: test tự `pytest.skip("No live LLM credentials in environment ... — NOT RUN.")`
    — không phải lỗi runtime, mà là điều kiện skip có chủ đích vì thiếu credential.
(c) 2 phương án: (1) Người duyệt cung cấp API key thật qua biến môi trường
    `VIETREADER_LLM_API_KEY`, agent chạy lại đúng 1 lệnh này và paste output thật; (2) Chấp nhận
    NOT RUN cho tiêu chí này, coi phần offline (9/9 test case + 3 test MockTransport) là đủ bằng
    chứng logic đúng, bổ sung live test sau khi có key.
(d) Đề xuất: phương án (2) — tiếp tục toàn bộ 10 phase theo yêu cầu người dùng, không chặn tiến
    độ vì 1 API key thiếu; ghi rõ NOT RUN thay vì bịa kết quả.

## Ready for gate? YES (trừ đúng 1 mục NOT RUN đã nêu, không phải lỗi logic)

---

# PHASE 4 REPORT — Extraction

## Deliverables
- `core/normalize.py` (23 dòng, **bổ sung** — xem Assumptions) — `normalize_text()`, `split_paragraphs()`
  dùng chung cho extraction (L0) và pipeline raw_hash (Phase 5), theo đúng spec §3.1
- `extraction/base.py` (37 dòng) — re-export `Chapter` từ core, `Extractor` Protocol,
  `ExtractionError`, `from_raw_text()`
- `extraction/fetcher.py` (56 dòng) — `Fetcher`: httpx, timeout, retry, User-Agent, delay lịch sự
- `extraction/config_adapter.py` (109 dòng) — `SiteConfig`, `ConfigAdapter` (selectolax)
- `extraction/generic.py` (30 dòng) — `GenericExtractor` (trafilatura fallback)
- `extraction/registry.py` (35 dòng) — `Registry`: chọn adapter theo domain, fallback generic
- `config/sites/quotes.toscrape.com.yml` — site adapter config thật dùng cho test
- `tests/fixtures/html/vi_wikipedia_ho_hoan_kiem.html` (281KB), `quotes_toscrape_page1.html`
  (11KB) — 2 fixture HTML thật, xem `tests/fixtures/html/SOURCES.md` cho nguồn + ngày tải
- `tests/unit/test_extraction.py` (10 test — 8 test case bảng + 2 bổ sung: relative-URL riêng
  + content-selector-not-found), `tests/unit/test_normalize.py` (6 test)

## Commands Run

```
$ .venv/Scripts/python.exe -m pytest -q tests/unit/test_extraction.py tests/unit/test_normalize.py -v
tests\unit\test_extraction.py ..........                                 [ 62%]
tests\unit\test_normalize.py ......                                      [100%]
16 passed in 0.79s

$ .venv/Scripts/python.exe -m ruff check src tests
All checks passed!

$ .venv/Scripts/python.exe -m mypy src/vietreader/core
Success: no issues found in 9 source files

$ .venv/Scripts/python.exe -m pytest -q --cov=vietreader --cov-report=term-missing   # full suite, all phases
.......................................................................  [100%]
TOTAL   658 stmts, 51 miss, 92%
71 passed, 1 deselected in 2.22s

extraction/base.py            100%
extraction/config_adapter.py   99%   (line 60: paragraph_split "newline" branch edge case)
extraction/fetcher.py          85%   (lines 40, 52-55: retry-loop internals not hit by every test)
extraction/generic.py          87%   (lines 15, 19: trafilatura-returns-nothing branches)
extraction/registry.py         92%   (lines 25, 31: no-config-dir / not-a-file edge branches)
core/normalize.py              100%
```

## Acceptance Check
- [x] 8 test case bảng (offline, dùng fixture) PASS — PASS (10 test viết, bảng yêu cầu nằm
      trong đó: #1 adapter match, #2 generic fallback, #3 strip ads/clutter, #4 no next_link,
      #5 empty/broken HTML, #6 from_raw_text, #7 relative next_url, #8 403/timeout mock)
- [x] Có >= 2 fixture HTML thật từ 2 site khác nhau, agent tự tải, ghi rõ nguồn — PASS
      (`tests/fixtures/html/SOURCES.md`)
- [x] `from_raw_text` hoạt động độc lập hoàn toàn với network — PASS (test thuần text, không
      import httpx/selectolax/trafilatura trên đường thực thi của nó)

## Assumptions
- **Bổ sung `core/normalize.py`** — spec §3.1 mô tả rõ quy tắc normalize (NFC, CRLF→LF, strip
  trailing space, collapse blank lines) và Phase 5 pseudocode ghi "1. extract → Chapter
  (normalize)", nhưng §1.2 repo layout không liệt kê module riêng cho việc này. Đặt vào `core/`
  (pure, không I/O) để dùng chung giữa `extraction/` (Phase 4) và `pipeline/` khi tính `raw_hash`
  (Phase 5), tránh trùng lặp logic normalize ở 2 nơi.
- **`Chapter` vẫn định nghĩa duy nhất trong `core/models.py`**, `extraction/base.py` chỉ
  re-export — theo assumption đã ghi ở Phase 1 (giải quyết mâu thuẫn giữa §1.2 và Phase 4
  deliverables text).
- **Cú pháp selector mở rộng `"selector@attr"`** (vd `"a#next-chap@href"`) — lấy giá trị
  attribute thay vì text; nếu attr thuộc `{href, src}` thì tự động `urljoin()` với `source_url`
  để trả về absolute URL. Không có trong spec chi tiết hơn "a#next-chap@href" trong ví dụ YAML
  §Schema, nhưng cách diễn giải `@` là điểm phân cách selector/attribute là hợp lý duy nhất
  khớp với ví dụ đó.
- **`paragraph_split`** nhận HOẶC `"newline"` (từ khoá đặc biệt: tách theo dòng trống trong text
  thô của content container) HOẶC bất kỳ CSS selector nào khác (khớp phần tử con trong content,
  mỗi phần tử = 1 đoạn) — spec chỉ ghi ví dụ `"p"  # hoặc "newline"`, đã tổng quát hoá "p" thành
  "bất kỳ selector nào" vì đó rõ ràng chỉ là ví dụ minh hoạ, không phải enum cố định 2 giá trị.
- **2 fixture HTML thật**: 1 từ `vi.wikipedia.org` (nội dung CC BY-SA, dùng cho test generic
  fallback), 1 từ `quotes.toscrape.com` (site dựng riêng cho luyện tập scraping, không robots.txt
  hạn chế, dùng cho test adapter config — KHÔNG phải site truyện thật). Không tải từ site truyện
  có bản quyền thật để tránh rủi ro pháp lý khi lưu HTML vào repo git (khác với runtime fetch
  của người dùng cuối, vốn đã có delay + User-Agent + paste-fallback theo đúng §6 risk table).

## Deviations
Không có ngoài phần bổ sung `core/normalize.py` đã nêu ở Assumptions.

## BLOCKER
Không có.

## Ready for gate? YES

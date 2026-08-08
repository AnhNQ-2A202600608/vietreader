# VietReader

Trợ lý đọc truyện tiếng Việt: LLM chỉ được hỏi "với span mơ hồ này, chọn phương án nào trong
danh sách đóng?" — không bao giờ nhìn thấy hay viết lại cả đoạn văn. Xem
`AGENT_WORK_ORDER_VietReader.md` (thư mục gốc repo, một cấp trên `vietreader/`) cho spec kiến
trúc đầy đủ, và `PHASE_REPORTS.md` / `DECISIONS.md` / `KNOWN_LIMITATIONS.md` trong thư mục này
cho lịch sử xây dựng, assumption và giới hạn hiện tại.

## Yêu cầu

- Python 3.11 (dự án pin `>=3.11,<3.13`; máy build gốc không có 3.12, xem `DECISIONS.md`)
- Không bắt buộc `make` — mọi lệnh dưới đây có thể chạy trực tiếp nếu máy bạn không có `make`
  (xem ghi chú ở mỗi bước)

## 1. Cài đặt

```bash
cd vietreader
python -m venv .venv

# Windows
.venv\Scripts\python.exe -m pip install -e ".[dev]"
# macOS/Linux
.venv/bin/python -m pip install -e ".[dev]"
```

Tương đương `make install`.

## 2. Cấu hình

```bash
cp config/settings.example.env .env
```

Sửa `.env`, tối thiểu cần set `VIETREADER_LLM_API_KEY` (Anthropic API key) nếu muốn dùng tính
năng ASK (dịch từ mơ hồ qua LLM) — không có key thì mọi tính năng khác (REPLACE, KEEP, extraction,
reader UI, dictionary manager) vẫn hoạt động bình thường; span ASK sẽ fallback giữ nguyên và ghi
WARN vào `run_log`.

## 3. Khởi tạo database

```bash
.venv/Scripts/python.exe -m alembic upgrade head
```

(Server cũng tự `create_all()` khi khởi động lần đầu để tiện dev — nhưng dùng Alembic là cách
chuẩn, có version history, downgrade được.)

## 4. Nạp từ điển mẫu (khuyến nghị)

```bash
.venv/Scripts/python.exe scripts/seed_dictionary.py
```

Nạp 65 entry mẫu (`config/seed_dictionary.yml`) — 35 REPLACE, 15 KEEP, 15 ASK, từ vựng tiên
hiệp/kiếm hiệp. An toàn chạy nhiều lần (bỏ qua entry đã tồn tại, không tạo trùng).

## 5. Chạy server

```bash
.venv/Scripts/python.exe -m uvicorn vietreader.api.app:app --reload --host 0.0.0.0 --port 8000
```

Tương đương `make run`. Mở `http://localhost:8000` — trang đọc; `/dictionary` — quản lý từ điển;
`/settings` — xem cấu hình (readonly); `/docs` — OpenAPI/Swagger UI của JSON API.

### Chạy bằng Docker (dev)

```bash
docker compose -f docker-compose.dev.yml up
```

## 6. Chạy test / lint / typecheck

```bash
.venv/Scripts/python.exe -m pytest -q --cov=vietreader --cov-report=term-missing
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m mypy src/vietreader/core
```

Tương đương `make test` / `make lint` / `make typecheck`.

## 7. Chạy eval (golden set)

```bash
.venv/Scripts/python.exe evals/run_eval.py            # offline, FakeProvider
.venv/Scripts/python.exe evals/run_eval.py --live      # provider thật, cần VIETREADER_LLM_API_KEY
```

Tương đương `make eval`. In bảng metric ra stdout và ghi `evals/REPORT.md`. Exit code khác 0 nếu
`reconstruction_pass_rate` (I1) hoặc `keep_preservation_rate` (I6) không đạt đúng 1.00.

## 8. Thêm một dictionary entry

Ba cách, chọn 1:

- **Qua UI**: vào `/dictionary`, điền form "Thêm entry mới".
- **Qua JSON API**: `POST /api/dictionary` với body
  `{"surface": "...", "display": "...", "policy": "replace|keep|ask", "replacement": "...", "candidates": [...]}`.
- **Qua reader UI (quick-add)**: bôi đen một cụm từ khi đang đọc → chọn KEEP/REPLACE/ASK trong
  popup hiện ra.

Quy tắc bắt buộc (được validate ở tầng `core.DictionaryEntry`, không cần nhớ thủ công — sai sẽ
báo lỗi rõ ràng):
- `surface` phải NFC-normalized, viết thường, không rỗng, không chứa newline, và duy nhất.
- `policy=replace` → bắt buộc có `replacement`, không được có `candidates`.
- `policy=ask` → bắt buộc `candidates` có ít nhất 2 phần tử, không được có `replacement`.
- `policy=keep` → không được có `replacement` hay `candidates`.

## 9. Thêm một site adapter (đọc URL từ site truyện cụ thể)

1. Tạo file `config/sites/<domain>.yml` (ví dụ `config/sites/truyenfull.vn.yml`), theo schema
   trong `config/sites/_example.yml`:
   ```yaml
   domain: <domain>              # phải khớp chính xác hostname trong URL
   title: "<CSS selector>"       # selector tới tiêu đề chương
   content: "<CSS selector>"     # selector tới container nội dung
   paragraph_split: "p"          # CSS selector cho mỗi đoạn văn, HOẶC "newline" để tách theo dòng trống
   next_link: "<CSS selector>@href"   # "@href" lấy giá trị attribute thay vì text; href/src tự resolve thành absolute URL
   prev_link: "<CSS selector>@href"   # tuỳ chọn
   strip_selectors:               # danh sách selector bị xoá khỏi content trước khi tách đoạn (quảng cáo, script...)
     - "div.ads"
     - "script"
   ```
2. Không cần restart gì đặc biệt — `extraction/registry.py` đọc `config/sites/*.yml` mỗi lần
   `Registry()` được khởi tạo (mỗi request trong dev vì `--reload`; production nên tránh khởi
   tạo lại `Registry` liên tục nếu muốn tối ưu — hiện tại đơn giản, dùng được cho quy mô cá nhân).
3. Test offline bằng fixture HTML thật (xem `tests/unit/test_extraction.py` và
   `tests/fixtures/html/SOURCES.md` làm ví dụ): tải 1 trang mẫu về `tests/fixtures/html/`, viết
   test dùng `ConfigAdapter(SiteConfig.from_yaml(...)).extract(html, url)` và assert
   title/paragraphs/next_url đúng.
4. Nếu site không có adapter, `Registry` tự fallback sang `GenericExtractor` (trafilatura) —
   không bắt buộc phải viết adapter cho mọi site trước khi dùng được.

## 10. Cấu trúc repo

Xem `AGENT_WORK_ORDER_VietReader.md` §1.2 cho sơ đồ đầy đủ. Tóm tắt các lớp (L0–L5):

```
URL / paste text → L0 Extractor → L1 Matcher → L2 Resolver → L3 Disambiguator (LLM) →
L4 Applier → L5 Validator → Reader UI
```

`src/vietreader/core/` là tầng thuần Python, không I/O — có test tự động
(`tests/unit/test_core_purity.py`) đảm bảo không bao giờ import `db/api/llm/extraction/httpx/
sqlalchemy/fastapi`.

## Giới hạn đã biết

Xem `KNOWN_LIMITATIONS.md`.

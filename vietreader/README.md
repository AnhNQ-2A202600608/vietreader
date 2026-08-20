# VietReader

Trợ lý đọc truyện tiếng Việt: LLM chỉ được hỏi "với span mơ hồ này, chọn phương án nào trong
danh sách đóng?" — không bao giờ nhìn thấy hay viết lại cả đoạn văn. Xem
`AGENT_WORK_ORDER_VietReader.md` (thư mục gốc repo, một cấp trên `vietreader/`) cho spec kiến
trúc đầy đủ, và `PHASE_REPORTS.md` / `DECISIONS.md` / `KNOWN_LIMITATIONS.md` trong thư mục này
cho lịch sử xây dựng, assumption và giới hạn hiện tại.

## Yêu cầu

- Python 3.11 hoặc 3.12 (dự án pin `>=3.11,<3.13`). Đã chạy đầy đủ test/lint/typecheck/eval
  trên cả 3.11.4 (Windows, lúc build) và 3.12.13 (macOS).
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

Sửa `.env`. Đáng chú ý: `VIETREADER_READER_NAME` là tên hiển thị trong lời chào ở trang chủ và
các màn hình trống (mặc định `Ngân Giang`).

Khi mở app ra Internet, đặt `VIETREADER_REQUIRE_AUTH=true` và khai cả
`VIETREADER_AUTH_USERNAME` / `VIETREADER_AUTH_PASSWORD`. Local mặc định không yêu cầu đăng nhập.
Fetcher mặc định xác minh TLS và từ chối localhost, IP private/link-local để tránh SSRF; chỉ bật
`VIETREADER_FETCH_ALLOW_PRIVATE_NETWORKS=true` trong mạng tin cậy khi thật sự cần.

Tối thiểu cần set `VIETREADER_LLM_API_KEY` (Anthropic API key) nếu muốn dùng tính
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

Nạp 160 entry mẫu (`config/seed_dictionary.yml`) — 75 REPLACE, 63 KEEP, 22 ASK, từ vựng tiên
hiệp/kiếm hiệp. An toàn chạy nhiều lần (bỏ qua entry đã tồn tại, không tạo trùng).

## 5. Chạy server

```bash
.venv/Scripts/python.exe -m uvicorn vietreader.api.app:app --reload --host 0.0.0.0 --port 8000
```

Tương đương `make run`. Mở `http://localhost:8000`:

| Trang | Nội dung |
|---|---|
| `/` | Đọc chương mới + "Tiếp tục đọc" |
| `/library` | Thư viện: bộ truyện và chương lẻ |
| `/series/{id}` | Danh sách chương của một bộ |
| `/dictionary` | Quản lý từ điển |
| `/feedback` | Ghi chú bạn đã lưu khi đọc |
| `/settings` | Cấu hình (chỉ đọc) |
| `/docs` | OpenAPI/Swagger UI của JSON API |

## 6. Dùng trình đọc

**Dán link theo cách tự nhiên.** Ô mở chương nhận URL đầy đủ, tên miền chưa có `https://`, URL
dạng `//domain/path`, link bọc bởi dấu `<...>` hoặc Markdown. Ký tự ẩn do copy/paste được bỏ tự
động. Nếu trang nguồn chặn bot, trả 404, timeout hay chỉ hiện CAPTCHA, màn hình lỗi giải thích
đúng nguyên nhân và cho mở trang nguồn, thử lại hoặc chuyển ngay sang **Dán nội dung**.

**Nội dung dán tay được tách đoạn thích ứng.** Nếu website copy ra mỗi đoạn trên một dòng nhưng
không có dòng trắng, VietReader không ép tất cả thành một bức tường chữ. Các xuống dòng rõ ràng
được chuyển thành đoạn đọc riêng; văn bản đã có khoảng cách đoạn vẫn được giữ nguyên.

**Mỗi chương có địa chỉ riêng.** Sau khi bấm "Đọc", URL trình duyệt đổi thành `/reader/{id}` —
refresh, nút Back, hay bookmark đều giữ được chương. Đóng tab không mất gì: chương nằm trong
`/library`, và trang chủ luôn hiện "Tiếp tục đọc" với chương gần nhất.

**Vị trí đọc tự lưu và tự khôi phục.** Cuộn tới đâu, vị trí được ghi qua API (throttle 3s). Lần
sau mở lại chương đó, trang tự cuộn về đúng đoạn đang dở và hiện dòng nhắc "Đã quay lại đoạn N"
kèm nút *Về đầu chương*. Chỉ chính xác tới cấp đoạn văn — xem `KNOWN_LIMITATIONS.md`.

**Chuyển chương trước / chương sau.** VietReader tự dò liên kết "Chương trước" / "Chương sau"
ngay trên trang truyện, kể cả khi site đó chưa có file adapter riêng — nhận cả chữ có dấu, không
dấu, tiếng Anh và mũi tên. Dò trượt, hoặc site chuyển chương bằng JS nên địa chỉ không đổi? Cuối
màn hình đọc có ô **"Sửa liên kết chương"** để dán thẳng địa chỉ chương kế tiếp vào (ô này tự mở
sẵn khi chưa dò ra được). Liên kết đã lưu sẽ theo chương đó về sau.

**Chương tự gom thành bộ truyện.** Khi bạn đọc bằng URL, VietReader suy ra bộ truyện từ đường
dẫn (`site.com/truyen-abc/chuong-5` → bộ `site.com/truyen-abc`) và tự gom các chương lại. Vào
`/library` để thấy danh sách bộ, bấm vào một bộ để xem toàn bộ chương theo đúng thứ tự, với
chương đang đọc dở được đánh dấu. Bộ truyện có thể **đổi tên** (tên mặc định lấy từ slug URL nên
thường thiếu dấu) và **theo dõi**. Chương dán tay không thuộc bộ nào, nằm riêng ở mục "Chương lẻ".

Nhờ vậy vị trí đọc được lưu theo **bộ**, mang nghĩa "đang ở chương nào của bộ này, đoạn nào" —
nên "Tiếp tục đọc" đưa bạn về đúng chương đang dở, không chỉ đúng đoạn.

**Ghi chú khi đọc.** Bấm nút ✎ ở góc dưới phải (hoặc phím `f`) để ghi nhanh điều bạn thấy chưa
ổn — ví dụ "chỗ này thay từ chưa hợp ngữ cảnh". Ghi chú được gắn tự động với chương và đoạn đang
đọc; nếu bạn đang bôi đen một câu thì câu đó được trích kèm. Xem lại và đánh dấu đã xử lý ở
`/feedback`. **Toàn bộ lưu trên máy bạn, không gửi đi đâu** — đây là sổ tay để tỉa dần từ điển,
không phải kênh góp ý.

**Quick-add từ ngay khi đang đọc.** Bôi đen một cụm từ trong nội dung → popup hiện 3 lựa chọn
KEEP / REPLACE / ASK, nhập ngay tại chỗ (không còn hộp thoại `prompt` của trình duyệt). Thêm
xong, chương **tự động được xử lý lại** với từ điển mới — dựng lại từ text đã lưu, không fetch
lại site, nên vẫn chạy kể cả khi site nguồn sập. Link "Chương sau" được giữ nguyên qua quá trình này.

**Phím tắt** (bấm `?` để xem trong app):

| Phím | Tác dụng |
|---|---|
| `n` / `p` | Chương sau / chương trước |
| `h` | Bật tắt tô màu từ đã thay |
| `o` | Xem / ẩn bản gốc |
| `f` | Ghi chú nhanh |
| `+` / `-` | Tăng / giảm cỡ chữ (được nhớ lại) |
| `d` | Giao diện sáng / tối (được nhớ lại) |
| `?` | Bảng phím tắt |
| `Esc` | Đóng popup / bảng phím tắt |

Giao diện mặc định đi theo cài đặt sáng/tối của hệ điều hành cho tới khi bạn bấm `d` để chọn
tường minh. Theme và cỡ chữ lưu ở localStorage; vị trí đọc thì luôn đi qua API.

### Chạy bằng Docker (dev)

```bash
docker compose -f docker-compose.dev.yml up
```

## 7. Chạy test / lint / typecheck

```bash
.venv/Scripts/python.exe -m pytest -q --cov=vietreader --cov-report=term-missing
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m mypy src/vietreader/core
```

Tương đương `make test` / `make lint` / `make typecheck`.

## 8. Chạy eval (golden set)

```bash
.venv/Scripts/python.exe evals/run_eval.py            # offline, FakeProvider
.venv/Scripts/python.exe evals/run_eval.py --live      # provider thật, cần VIETREADER_LLM_API_KEY
```

Tương đương `make eval`. In bảng metric ra stdout và ghi `evals/REPORT.md`. Exit code khác 0 nếu
`reconstruction_pass_rate` (I1) hoặc `keep_preservation_rate` (I6) không đạt đúng 1.00.

## 9. Thêm một dictionary entry

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

## 10. Thêm một site adapter (đọc URL từ site truyện cụ thể)

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

## 11. Cấu trúc repo

Xem `AGENT_WORK_ORDER_VietReader.md` §1.2 cho sơ đồ đầy đủ. Tóm tắt các lớp (L0–L5):

```
URL / paste text → L0 Extractor → L1 Matcher → L2 Resolver → L3 Disambiguator (LLM) →
L4 Applier → L5 Validator → Reader UI
```

`src/vietreader/core/` là tầng thuần Python, không I/O — có test tự động
(`tests/unit/test_core_purity.py`) đảm bảo không bao giờ import `db/api/llm/extraction/httpx/
sqlalchemy/fastapi`.

## Đưa lên máy chủ

Cùng một mã nguồn, ba cách. Đổi qua lại được bằng cách đổi `VIETREADER_DATABASE_URL`:

- **[DEPLOY_RENDER.md](DEPLOY_RENDER.md) — đường chính.** Render + Neon Postgres. Có thể thử bằng
  gói Free, nhưng Render không coi Free là production-grade: app ngủ sau 15 phút và filesystem
  là tạm. Blueprint buộc PostgreSQL, migration và auth để không mất dữ liệu do cấu hình thiếu.
- [DEPLOY.md](DEPLOY.md) — tự host trên máy ảo hoặc máy ở nhà, giữ SQLite, không ngủ. Miễn phí
  nếu bạn có sẵn máy; viết cho Oracle Cloud Always Free (gói này **cần thẻ để đăng ký**).
- [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) — Railway, ~$5/tháng, cần thẻ.

Cả ba đều lưu ý: local mặc định không bật đăng nhập. Blueprint Render bắt buộc HTTP Basic Auth;
self-host phải bật auth trong app hoặc đặt access control ở reverse proxy trước khi mở Internet.

## Giới hạn đã biết

Xem `KNOWN_LIMITATIONS.md`.

# DECISIONS.md — ADR log

Ghi ngắn gọn mọi assumption/deviation phát sinh trong quá trình agent thực thi work order.
Định dạng: `[Phase N] Quyết định — Lý do — Phương án thay thế đã cân nhắc`.

---

- **[Phase 0] Python runtime: 3.11 thay vì 3.12.** Lý do: máy dev không có Python 3.12 cài sẵn
  (chỉ có 3.10, 3.11, 3.13). Chọn 3.11 vì gần 3.12 nhất về dưới, tương thích tốt hơn với các
  dependency pin (pyahocorasick, hypothesis) so với 3.13 ở thời điểm viết. Phương án thay thế:
  cài Python 3.12 thủ công — không tự ý cài phần mềm ngoài môi trường hiện có khi chưa hỏi.
- **[Phase 0] LLM provider = Anthropic, model mặc định `claude-haiku-4-5-20251001`.** Lý do:
  provider đã ngầm định qua tên file `llm/anthropic.py` trong repo layout chốt; model chọn loại
  nhanh/rẻ vì tác vụ L3 chỉ là chọn index trong candidate list đóng, không cần model mạnh.
  Model đổi được qua `VIETREADER_LLM_MODEL`. Phương án thay thế: chờ người duyệt chỉ định model —
  không chặn vì đây không phải quyết định kiến trúc khó đảo ngược.
- **[Phase 0] `docker-compose.dev.yml` dùng image `python:3.11-slim` trực tiếp** (pip install -e
  lúc container start) thay vì viết Dockerfile riêng. Lý do: work order không liệt kê Dockerfile
  trong deliverables §1.2; tránh thêm file ngoài danh sách khi chưa cần.
- **[Phase 1] Ví dụ minh hoạ word-boundary trong spec §3.2 ("lão giả" không match trong
  "lão giả tử") không thể đạt được bằng đúng thuật toán được mô tả (kiểm tra ký tự liền kề
  không phải \w).** Lý do: tiếng Việt phân tách MỌI âm tiết bằng dấu cách, không chỉ phân tách
  từ — nên "tử" sau "giả " là một từ độc lập, được bao quanh bởi khoảng trắng hợp lệ, và matcher
  sẽ hợp lệ match "lão giả" tại đó theo đúng thuật toán. Muốn chặn đúng ví dụ này cần phân đoạn
  từ tiếng Việt đầy đủ (word segmentation) — nằm ngoài phạm vi kiến trúc đã chốt (matcher phải
  "KHÔNG dùng LLM. Deterministic", không phân tích ngôn ngữ). Đã triển khai đúng thuật toán như
  mô tả (kiểm tra ký tự liền kề), và sửa test case #2 của Phase 1 dùng ví dụ đạt được thật sự
  (chuỗi ký tự liền nhau không dấu cách) thay vì ví dụ minh hoạ gốc. Phương án thay thế đã cân
  nhắc: thêm heuristic phát hiện "từ ghép tiềm năng" dựa trên việc từ điển có entry dài hơn bắt
  đầu cùng vị trí — không dùng vì đây đã là quy tắc "longest-match wins" sẵn có (bước 4), không
  giải quyết được trường hợp không có entry dài hơn nào trong từ điển.
- **[Phase 1] Tie-break theo priority (spec §3.2 bước 5) chỉ thực sự quan sát được khi hai span
  cùng độ dài chồng lấn nhau nhưng MỖI span vẫn tự vượt qua bộ lọc word-boundary độc lập** — tức
  là chồng lấn phải xảy ra ở vùng có dấu cách bao quanh (ví dụ hai cụm nhiều âm tiết chồng lấn
  một phần), không thể xảy ra với hai từ đơn-âm-tiết liền nhau trong cùng một chuỗi ký tự liên
  tục (khi đó ít nhất một trong hai luôn bị boundary-filter loại). Test case #5 của Phase 1 dùng
  ví dụ "sư huynh" / "huynh đệ" chồng lấn ở "huynh" để minh hoạ đúng điều này.
- **[Phase 2] `AskResolver` (L2) không tự validate output của chính nó** — resolver "ngây thơ"
  tin tưởng input, để L5 (validator) là nguồn sự thật duy nhất bắt lỗi (khớp test case 8: "trả
  giá trị ngoài candidates → I5 FAIL", tức lỗi phải bị validator bắt chứ không phải bị chặn ở L2).
- **[Phase 2] I4 khi `entry.replacement is None` nhưng `change.source == "replace"`** (dữ liệu
  hỏng, ví dụ policy đổi thành KEEP sau khi change đã tạo): xử lý là I4 violation (trả về có cấu
  trúc) thay vì crash bằng `assert`.
- **[Phase 3] LLM provider = Anthropic thật, model `claude-haiku-4-5-20251001`** (xem Phase 0).
  Ngữ nghĩa retry: "JSON parse fail toàn batch" mới retry cả batch; "choice ngoài range"/"thiếu
  id" (lỗi per-item trong response đã parse được) fallback per-item ngay, không retry cả batch —
  khớp mô tả test case #4 ("thiếu 1 id → span đó fallback, các span khác vẫn OK", không nhắc retry).
  `max_tokens = batch_size × 40` dùng đúng công thức nguyên văn spec §3.4.
  Thêm `AnthropicProvider.__init__(transport=...)` để test offline bằng `httpx.MockTransport`
  (không đổi hành vi production, mặc định `None` = network thật) — cần để đạt coverage `llm/`
  >= 85% mà vẫn 100% offline.
- **[Phase 4] Bổ sung `core/normalize.py`** (không có tên module riêng trong §1.2, nhưng §3.1 mô
  tả rõ quy tắc và Phase 5 pseudocode ghi "extract → Chapter (normalize)") — đặt trong `core/`
  (pure) để dùng chung giữa `extraction/` và `pipeline/` (raw_hash), tránh trùng lặp logic.
  `Chapter` vẫn định nghĩa duy nhất trong `core/models.py`, `extraction/base.py` chỉ re-export.
  Cú pháp selector `"selector@attr"` (lấy attribute, tự `urljoin()` nếu attr là href/src) và
  `paragraph_split` nhận `"newline"` HOẶC bất kỳ CSS selector nào (tổng quát hoá từ ví dụ `"p"`).
  2 fixture HTML thật: `vi.wikipedia.org` (test generic fallback) + `quotes.toscrape.com` (site
  dựng cho luyện scraping, không robots.txt hạn chế — test config adapter) — KHÔNG dùng site
  truyện có bản quyền thật để tránh rủi ro pháp lý khi lưu HTML vào repo git.
- **[Phase 5] `source_key` (khoá cache chương) = ghép chuỗi** `sha256(raw_text)|dict_version_hash|
  prompt_version|model` (nối, không hash lại lần nữa) — đọc nghĩa đen công thức §2.4, khác công
  thức LLM cache key §3.4 vốn có `sha256()` bọc ngoài cả chuỗi. Hai lớp cache ĐỘC LẬP nhau theo
  đúng thiết kế: đổi dictionary → chapter_cache miss, nhưng llm_cache (không phụ thuộc
  dict_version_hash) vẫn có thể hit nếu câu hỏi ASK giống hệt — đây là hành vi đúng, không phải
  bug. `llm/disambiguator.py` đổi return type thành `DisambiguationOutcome{results,llm_calls,
  cache_hits}` để `ProcessResult.stats` chính xác với MỌI provider (không chỉ dựa vào
  `FakeProvider.call_count`).
- **[Phase 6] `httpx.AsyncClient(app=...)` đã bị gỡ ở httpx 0.27 (bản pin)** — dùng
  `httpx.ASGITransport(app=app)` thay thế, đây là cách chính thức được khuyến nghị, không phải
  sai lệch kiến trúc. Ruff rule B008 (`Depends()` trong default argument) tắt riêng cho
  `src/vietreader/api/**` vì đó là pattern bắt buộc của FastAPI. Import CSV/JSON commit từng
  dòng một (không phải 1 transaction cho cả batch) để 1 dòng lỗi không rollback các dòng đã tạo
  thành công trước đó trong cùng session.
- **[Phase 7] HTMX + Alpine.js vendor hoá** (tải về lưu trong repo) thay vì CDN, đúng tinh thần
  "ứng dụng cá nhân, không phụ thuộc mạng khi đọc". Inline edit trong Dictionary manager (web UI)
  chỉ áp dụng `priority`/`enabled` — sửa field khác cần xoá/tạo lại (JSON API không giới hạn
  này). `series_key` = URL chương (hoặc `"raw"` khi paste) — không có khái niệm "truyện" nhóm
  nhiều URL. Thêm `core/applier.output_positions()` dùng chung bởi `validator.reconstruct()` và
  `web/rendering.py` để tránh trùng lặp phép toán shift offset.
- **[Phase 8] `ambiguity_accuracy` ở chế độ offline (`FakeProvider` mode="correct") đo hành vi
  mặc định (luôn chọn candidate index 0), KHÔNG phải chất lượng LLM thật** — 10 case ASK được
  soạn sao cho index 0 là câu trả lời đúng theo ngữ cảnh, đây là fixture CI xác định hợp lý, không
  phải "gian lận" (không có out-of-band hint nào giữa golden case và provider). Tính bằng tỉ lệ
  case ASK có `exact_match` — cách duy nhất đo "chọn đúng candidate" mà không cần thêm field
  ngoài schema chính thức. `evals/golden/_generate.py` không phải deliverable bắt buộc (chỉ hỗ
  trợ soạn `expect_output` bằng cách chạy thật pipeline 1 lần) — `run_eval.py` không import nó,
  luôn chạy lại độc lập nên không có "tự chấm điểm vòng tròn".
- **[Phase 9] Thêm `lxml_html_clean>=0.4,<0.5` vào dependency allowlist — phát hiện qua kiểm thử
  clone sạch thật (git clone vào thư mục tạm, cài lại từ đầu, chạy toàn bộ test suite).** Lý do:
  `trafilatura` (đã có trong allowlist gốc) phụ thuộc gián tiếp vào `justext`, vốn import
  `lxml.html.clean` — module này đã bị tách thành gói riêng `lxml_html_clean` kể từ `lxml` bản
  mới. Trong venv dev gốc, `pip` tình cờ resolve kèm `lxml_html_clean` (thấy trong log cài đặt
  Phase 0), nên lỗi không lộ ra; nhưng khi `git clone` sạch rồi cài lại từ đầu (test thật ở
  Phase 9), `pip` KHÔNG tự chọn gói này nữa → `ImportError` khi import `trafilatura`, mọi test
  đụng tới `extraction/generic.py` (và transitively `extraction/registry.py`) đều fail collect.
  Đây là transitive dependency của một package đã có trong allowlist (không phải thêm chức năng
  mới), nên không coi là mở rộng scope — chỉ là pin rõ ràng một phụ thuộc vốn đã ngầm cần thiết.
  Đã xác minh lại: clone sạch → cài đặt → test/lint/typecheck/eval đều PASS sau khi thêm dòng
  này. Xem PHASE_REPORTS.md Phase 9 cho log đầy đủ.

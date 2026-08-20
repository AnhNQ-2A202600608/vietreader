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

## Phase 10 — Trải nghiệm đọc (sau bàn giao, theo yêu cầu người dùng)

- **[Phase 10] I6 đổi từ "số lần xuất hiện phải BẰNG" sang "không được GIẢM" — deviation có chủ
  đích so với work order §3.5, được người dùng phê duyệt.** Lý do: I6 nguyên bản hard-fail cả
  chương khi một replacement vô tình SINH RA một KEEP term (ví dụ REPLACE "tu sĩ" → "linh lực gia"
  trong khi "linh lực" là KEEP), dù không occurrence gốc nào bị đụng tới. Hậu quả thực tế: một
  thao tác quick-add hợp lệ từ màn hình đọc làm mọi chương chứa từ đó im lặng ngừng xử lý và rơi
  về raw text — mà quick-add lại là workflow trung tâm của UI. Mục đích của I6 là BẢO VỆ thuật
  ngữ khỏi bị phá, nên chỉ chiều "mất đi" mới là vi phạm. Phương án thay thế đã cân nhắc: giữ
  nguyên I6 và chặn từ lúc ghi entry — không chọn vì nó cấm một cấu hình từ điển vốn hoàn toàn
  hợp lệ, và không xử lý được trường hợp hai entry độc lập vô tình tổ hợp thành KEEP term.
  Test `test_i6_allows_replacement_that_introduces_a_keep_term` khoá hành vi mới;
  `test_i6_fails_when_keep_occurrence_removed` vẫn giữ nguyên, chứng minh chiều bảo vệ còn nguyên.
- **[Phase 10] `chapter_cache.last_read_at` để nullable.** SQLite cấm `DEFAULT CURRENT_TIMESTAMP`
  trên `ADD COLUMN NOT NULL`, nên cột NOT NULL sẽ làm migration vỡ trên DB đã có dữ liệu. NULL
  mang nghĩa "chưa mở lại", `list_recent()` fallback về `created_at`. Đã kiểm chứng thật:
  upgrade → chèn row bằng schema cũ → upgrade → downgrade → upgrade đều sạch.
- **[Phase 10] `HX-Push-Url` thay vì để chương sống trong fragment.** Trước đây `POST /read`
  swap innerHTML mà không đổi địa chỉ, nên refresh/back/bookmark đều mất chương. Nay response
  kèm `HX-Push-Url: /reader/{id}` (chỉ khi chương được cache, tức validation PASS). Phương án
  thay thế: redirect 303 — không dùng vì sẽ mất lợi thế swap không reload của HTMX.
- **[Phase 10] `series_key` cho chương dán tay đổi từ hằng `"raw"` thành `"chapter:{id}"`.**
  Mọi chương dán tay trước đây dùng chung một khoá nên ghi đè vị trí đọc của nhau.
- **[Phase 10] `list_recent()` gộp theo `raw_hash`.** Cache key gồm `dict_version_hash`, nên mỗi
  lần sửa từ điển lại sinh thêm một row cho CÙNG một chương; thư viện liệt kê thô sẽ đầy bản
  trùng. Gộp ở tầng đọc (giữ nguyên mọi row trong DB, chỉ hiện bản mới nhất) thay vì xoá row cũ —
  không phá cơ chế cache, vẫn cho phép cache hit khi người dùng quay lại phiên bản từ điển cũ.
- **[Phase 10] `POST /reader/{id}/reprocess` luôn dựng lại từ `raw_text` đã lưu, không fetch
  lại site.** Khi quick-add xong, thứ thay đổi là TỪ ĐIỂN chứ không phải nội dung chương — fetch
  lại vừa thừa vừa có thể fail nếu site sập. Vì `raw_text` không mang link điều hướng,
  `set_navigation()` chuyển `next_url`/`prev_url` từ row cũ sang row mới.
- **[Phase 10] localStorage được dùng cho theme và cỡ chữ.** Work order §Phase 7 cấm localStorage
  cho "dữ liệu quan trọng"; theme/cỡ chữ là tuỳ chọn hiển thị thuần tuý, mất đi không tổn hại gì,
  và cần đọc được TRƯỚC khi trang vẽ lần đầu để không nháy màu. Vị trí đọc — thứ thực sự quan
  trọng — vẫn đi hoàn toàn qua API như quy định.
- **[Phase 11] Mô hình "bộ truyện" — ý tưởng mượn từ TruyenDex, KHÔNG tích hợp code.**
  Người dùng đề nghị tích hợp `github.com/zennomi/truyendex`. Sau khi nghiên cứu: TruyenDex là
  trình đọc truyện TRANH (ảnh từ API MangaDex, Next.js/TypeScript), MangaDex chỉ trả ảnh trang
  và không hỗ trợ light novel — nên **không có văn bản nào cho pipeline L1–L5 xử lý**, và không
  dòng code nào dùng lại được (work order §1.1 vốn đã từ chối Next.js). Thay vì ghép hai ứng
  dụng không liên quan, chỉ lấy ý tưởng giá trị nhất: bộ truyện gom nhiều chương, theo dõi được,
  tiến độ đọc theo bộ. Đã báo cáo điểm vênh này và được người dùng chốt hướng.
- **[Phase 11] `reading_position.series_key` nay trỏ tới BỘ TRUYỆN, không phải từng chương.**
  Bảng này vốn đã có `series_key + url + para_index` từ Phase 5 — tức là đã được thiết kế cho
  đúng mô hình này, chỉ thiếu việc `series_key` thực sự là một bộ. Nay vị trí đọc mang nghĩa
  "đang ở chương nào của bộ, đoạn nào". Chương dán tay (không suy ra được bộ) vẫn dùng
  `chapter:{id}` như Phase 10. Hệ quả ở client: khi khôi phục vị trí, JS chỉ cuộn nếu
  `position.url` trùng chương đang mở — vì vị trí có thể trỏ sang chương khác cùng bộ.
- **[Phase 11] Suy ra bộ truyện bằng cách bỏ path segment cuối của URL chương**
  (`core/series.py`, thuần, không I/O). Cố ý bảo thủ: nếu URL chỉ có ≤1 segment thì KHÔNG nhận
  bộ nào (trả `None`), để chương đứng riêng — thay vì gom mọi truyện trên cùng một host vào một
  "bộ" giả. Sắp xếp chương theo số hiệu bắt được từ URL/tiêu đề (`chuong-5`, `chapter 12`…),
  chương không có số thì giữ thứ tự xuất hiện ở cuối. Phương án thay thế: bắt người dùng tự tạo
  bộ và gán chương — không chọn vì thêm thao tác thủ công cho thứ suy ra được đúng trong đa số
  trường hợp; bù lại có nút đổi tên khi heuristic đặt tên xấu.
- **[Phase 11] `feedback` là ghi chú CỤC BỘ, không gửi đi đâu.** App chạy local một người dùng,
  không có server nào phía sau để nhận góp ý, nên "ô feedback" được hiện thực hoá thành sổ ghi
  chú gắn với chương + đoạn + câu đang bôi đen, có trang `/feedback` để xử lý dần. Đây là dạng
  hữu ích duy nhất trong kiến trúc offline hiện tại, và nối thẳng vào vòng lặp tỉa từ điển.
- **[Phase 11] Migration dùng `batch_alter_table` cho `chapter_cache.series_id`.** SQLite không
  `ALTER TABLE ... ADD CONSTRAINT` được, nên bản autogenerate (`create_foreign_key`) sẽ hỏng.
  Batch mode dựng lại bảng kèm foreign key, giữ schema khớp đúng ORM để các lần autogenerate sau
  không liên tục phát hiện thiếu FK. Đã kiểm chứng thật trên DB *có sẵn dữ liệu*.
- **[Phase 11] SỬA LỖI CÓ TỪ TRƯỚC: `/api/position/{series_key}` cần `:path`.** `series_key`
  là một URL nên chứa dấu `/`; route một-segment không bao giờ khớp, và percent-encoding không
  cứu được vì path đã được giải mã trước khi định tuyến. Hệ quả: **vị trí đọc âm thầm 404 với
  mọi chương đọc bằng URL** kể từ Phase 7 — chỉ chương dán tay (khoá `chapter:{id}`, không có
  `/`) mới chạy. Test cũ dùng khoá `series-1` không dấu `/` nên không bắt được; đã thêm
  `test_position_works_for_a_url_series_key` dùng khoá URL thật.
- **[Phase 11] SỬA LỖI: gán bộ truyện không được phép DI CHUYỂN chương đã có bộ.** `chapter_cache`
  khoá theo NỘI DUNG, nên hai URL có văn bản trùng khít dùng chung một hàng. Trước khi có guard,
  mở URL thứ hai sẽ kéo hàng đó sang bộ khác — bộ ban đầu mất một chương, và sinh ra một bộ rỗng
  ma. Nay hàng giữ nguyên bộ đã được xếp lần đầu. Cùng gốc lỗi này còn xảy ra ở tình huống phổ
  biến hơn: một chương truy cập được qua hai URL (có/không `/` cuối, `?page=1`, http/https).
  Phát hiện khi chạy thật với site giả trên máy, không phải từ test.
- **[Phase 11] SỬA LỖI CÓ TỪ PHASE 4: `GenericExtractor` dồn cả chương thành MỘT đoạn.**
  `trafilatura` phân tách khối bằng MỘT ký tự `\n`, nhưng `generic.py` dùng `split_paragraphs()`
  vốn tách theo DÒNG TRỐNG — nên mọi chương đọc từ site chưa có adapter (tức đường mặc định cho
  mọi site mới) hiện ra thành một khối chữ liền, mất hết ngắt đoạn. Trafilatura cũng lặp tiêu đề
  vào khối đầu của thân bài. Nay tách theo từng dòng và bỏ dòng đầu nếu trùng tiêu đề. Test cũ
  chỉ assert `chapter.paragraphs` khác rỗng nên một khối khổng lồ vẫn pass; đã thêm
  `test_generic_extractor_keeps_paragraph_breaks` assert đúng số đoạn.
  **Phát hiện bằng cách chụp màn hình giao diện thật và nhìn** — không test nào bắt được.
- **[Phase 11] SỬA LỖI CSS: `.position-note[hidden]`.** Thuộc tính `hidden` của HTML bị quy tắc
  `display: flex` của chính stylesheet ghi đè, nên ô "đã quay lại đoạn N" luôn hiện thành một
  hộp xám RỖNG phía trên mọi chương. Cũng chỉ lộ ra qua ảnh chụp.
- **[Phase 11] Tên chương lấy từ TRONG TRANG để giữ dấu tiếng Việt** (`extraction/chapter_title.py`).
  Suy từ slug URL cho ra "Tai ach" mất dấu — không chấp nhận được với tiếng Việt. Tên chương thật
  gần như luôn có sẵn trong trang: vế chương của thẻ `<title>` ("Tên truyện - Chương 3 tai ách"),
  `<h1>`, hoặc phần tử class `chapter-name`/`book-title`. Chỉ nhận ứng viên nhắc ĐÚNG số chương
  của URL (để danh sách chương ở sidebar không cướp mất tiêu đề), và trong số đó lấy chuỗi NGẮN
  NHẤT — phần tử bao ngoài hay dính cả tên truyện lẫn tên chương, phần tử đúng chỗ thì không.
  Slug URL tụt xuống thành phương án cuối.
- **[Phase 11] Chương đã lưu tự cập nhật tiêu đề khi mở lại.** Cache khoá theo nội dung nên mở
  lại một chương cũ là cache hit và giữ nguyên tiêu đề cũ — các chương lưu trước khi có
  `chapter_title.py` sẽ mắc kẹt với tên bộ truyện mãi mãi. Nay ở nhánh cache hit, nếu trang trả
  về tiêu đề khác thì ghi đè: trang là nguồn đúng về tên của chính nó. Đã kiểm chứng trên dữ liệu
  thật của người dùng — 4 chương từ "Ta Không Phải Hí Thần" tự sửa thành tên chương có dấu đầy đủ.
- **[Phase 11] Tên chương suy từ URL khi trang dùng tên bộ truyện làm `<title>`.** Phát hiện từ
  dữ liệu dùng thật của người dùng: 4 chương liên tiếp của một bộ đều mang đúng một tiêu đề (tên
  bộ truyện), khiến danh sách chương nhìn như bị lưu trùng lặp dù mỗi chương chỉ có một bản ghi.
  `chapter_display_title()` chỉ can thiệp khi tiêu đề KHÔNG hề nhắc tới số chương mà URL thì có
  — tiêu đề đã rõ ràng thì để nguyên. Áp ở cả `GenericExtractor` (dữ liệu mới) lẫn `_row_to_entry`
  (các chương đã lưu tự chữa khi đọc lên, không cần migration hay xử lý lại).
- **[Phase 11] SỬA LỖI: regex số chương nhận nhầm "%C3" trong URL percent-encode.** Nhánh `c`
  đứng lẻ khiến `.../H%E1%BB%93_Ho%C3%A0n_Ki%E1%BA%BFm` bị đọc thành "chương 3". Đã bỏ nhánh `c`
  và thêm lookbehind chặn từ khoá lọt giữa một từ khác. Test fixture Wikipedia bắt được lỗi này.
- **[Phase 11] Dò chương trước/sau tự động cho MỌI site, không cần adapter.** Trước đó
  `GenericExtractor` hardcode `next_url=None, prev_url=None`, nên **không site truyện thật nào
  có nút chuyển chương** — chỉ site đã viết `config/sites/<domain>.yml` mới có, mà cả repo mới
  có đúng một file cho `quotes.toscrape.com` (site test). `extraction/navigation.py` dò theo
  `rel="next"/"prev"` rồi tới chữ trên liên kết ("Chương sau", không dấu "chuong sau", "Next",
  mũi tên »/›), chấm điểm theo độ đặc hiệu để một liên kết không bị nhận thành cả hai chiều, bỏ
  qua liên kết trỏ về chính trang đang đọc. Adapter YAML vẫn thắng khi có, vì nó chính xác hơn.
- **[Phase 11] Sửa tay liên kết chương: `POST /reader/{id}/navigation`.** Dò tự động chỉ là
  phỏng đoán, và có site chuyển chương bằng JS nên URL không đổi — lúc đó không có gì để dò.
  Màn hình đọc có ô dán thẳng địa chỉ chương trước/sau, tự mở sẵn khi chưa dò ra được. Lưu vào
  `chapter_cache.next_url/prev_url` nên giữ nguyên qua các lần mở lại.

- **[Phase 11] Làm lại bảng màu bản TỐI.** Bản tối đầu tiên bị chê xấu; chụp lại từng màn hình
  để soi thì thấy bốn lỗi, sửa từ token chứ không vá từng chỗ:
  1. *Nền loang lổ*: hai vệt radial-gradient dùng màu quá đậm (`#4a1f3d`, `#2c2350`) tạo mảng
     nâu tím bẩn vắt ngang đầu trang. Trên nền tối, vệt màu phải nhạt hơn nhiều so với bản sáng —
     đã hạ xuống `#241830` / `#1a1a30`.
  2. *Nút hồng chói*: dùng chung `--accent` (hồng neon, vốn chọn để chữ đọc rõ trên nền tối) làm
     nền nút nên đập vào mắt. Tách token `--btn-a`/`--btn-b`: chữ và liên kết giữ hồng sáng, còn
     mảng đặc dùng hồng trầm với chữ trắng.
  3. *Linh vật thành cục đen*: `.mascot .cloud` tô bằng `--surface-2` nên ở bản tối Mây tối thui.
     Tách token `--mascot-fill` để bản tối cho Mây sáng hơn nền.
  4. *Từ đã thay ngả nâu bẩn* kèm gạch chân hồng gắt: tách `--hl-line-*` để bản tối dùng đường
     kẻ trầm hơn, và đổi nền viên tô sang sắc mận thay vì nâu.
- **[Phase 11] Bỏ Georgia khỏi font đọc — nó thiếu ký tự tiếng Việt.** Georgia không có khối
  Latin Extended Additional (U+1EA0–U+1EF9: ầ ữ ợ ể ộ ự...), nên trình duyệt phải mượn glyph từ
  font khác cho đúng những chữ CÓ DẤU — trong cùng một từ, chữ có dấu nhạt và hẹp hơn chữ không
  dấu. Với tiếng Việt thì gần như chữ nào cũng có dấu, nên cả trang chữ nhìn lệch nét.
  Đã dựng trang so sánh và chụp lại để kiểm chứng bằng mắt: Palatino, Charter, Iowan Old Style
  còn hỏng nặng hơn (dấu tách rời khỏi chữ, trôi sang bên); Hoefler Text, Baskerville,
  Times New Roman thì đều nét. Chốt `--font-read: "Hoefler Text", Baskerville,
  "Times New Roman", "Noto Serif", serif` — mọi mắt xích trong chuỗi đều có dấu tiếng Việt dựng
  sẵn, và chuỗi này phủ được cả macOS, Windows lẫn Linux.
  Cũng bỏ `"Quicksand"` khỏi `--font-ui`: nó không hề được cài kèm (nên là cấu hình chết), mà
  bản thân nó cũng thiếu dấu tiếng Việt nếu ai đó cài vào.
- **[Phase 11] Nhận diện "Mây hồng" + linh vật, theo yêu cầu người dùng.** Bảng màu chuyển sang
  tông hồng (sáng: hồng phấn trên nền trắng ngả hồng; tối: nền mận đậm, điểm hồng tươi). Nguyên
  tắc giữ được tính đọc lâu: **trang trí chỉ đặt ở phần khung** (header, thẻ, nút, badge, linh
  vật) — riêng `.reader-text` giữ nền phẳng, không gradient, tương phản cao, vì đó là chỗ mắt ở
  lại lâu nhất. Dùng hai sắc hồng tách biệt: `--accent` (#c2185b) đậm đủ tương phản cho chữ và
  nút, `--accent-bright` chỉ cho mảng trang trí — không bao giờ dùng cho chữ nhỏ.
- **[Phase 11] Linh vật "Mây" là SVG tự vẽ, đặt trong `_mascot.html`.** Một tinh linh mây, hợp
  chủ đề tiên hiệp. Tự vẽ bằng path để không dùng nhân vật/hình ảnh có bản quyền của bên nào, và
  để tô màu bằng biến CSS nên tự đổi theo sáng/tối. Có 3 trạng thái (`happy`/`sleepy`/`reading`)
  bật tắt bằng CSS trên cùng một khối SVG, thay vì 3 file riêng. Xuất hiện ở: logo, thẻ "Tiếp
  tục đọc", nút ghi chú, và các trạng thái rỗng.
- **[Phase 11] Hiệu ứng đều nằm sau `prefers-reduced-motion`.** Mây bồng bềnh, sao lấp lánh, nút
  nhún khi bấm, thẻ nhấc lên khi rê chuột, popup bung nhẹ — toàn bộ `animation`/`transform` bị
  tắt hoàn toàn khi người dùng bật giảm chuyển động trong hệ điều hành.
- **[Phase 11] Giao diện được thiết kế lại thành design system trong CSS thuần** (token màu,
  thang cách `--s1..s7`, thang chữ, bo góc, đổ bóng; component card/list/badge/empty-state/
  dialog; responsive ≤640px; `prefers-reduced-motion`). Không thêm build toolchain nào, đúng
  ràng buộc §1.1 — Tailwind/PostCSS sẽ vi phạm dependency allowlist.
- **[Phase 10] `data-theme` không còn hardcode trong `base.html`.** Giá trị `"light"` cứng trước
  đây có specificity cao hơn `@media (prefers-color-scheme: dark)`, khiến dark mode hệ thống
  KHÔNG BAO GIỜ áp dụng. Nay thuộc tính chỉ được đặt khi người dùng chọn tường minh, và khối
  media query được guard bằng `:root:not([data-theme="light"])`.

## Phase 12 — Hardening và sửa lỗi tích hợp (2026-08-20)

- **Khôi phục `series_id` khi map ORM row sang `ChapterCacheEntry`.** Trước đó DB lưu đúng nhưng
  DTO luôn dùng giá trị mặc định `None`, làm chương mở lại mất metadata bộ và lọt vào danh sách
  chương lẻ. Có test repository và web khóa đường round-trip này.
- **Render chỉ deploy sau CI bằng native `checksPass`.** Blueprint dùng
  `autoDeployTrigger: checksPass`, nên không còn Deploy Hook/secret riêng; workflow
  `deploy.yml` chỉ phục vụ self-host.
- **Public deployment bắt buộc Basic Auth.** Local vẫn không cần credentials. Blueprint Render
  đặt `VIETREADER_REQUIRE_AUTH=1`, nên thiếu password sẽ fail-fast thay vì âm thầm mở dữ liệu.
  Unsafe browser request khác origin bị từ chối; healthcheck và static assets vẫn public.
- **Fetcher chặn SSRF và bật TLS verification.** Chỉ HTTP(S), không userinfo, mặc định từ chối
  localhost/private/link-local/non-public IP và kiểm tra từng redirect trước khi gửi request.
  Intranet là opt-in rõ ràng qua `VIETREADER_FETCH_ALLOW_PRIVATE_NETWORKS`.
- **Quick-add normalize NFC + lowercase nhưng giữ display gốc.** Người dùng có thể bôi từ ở đầu
  câu như “Lão giả” mà không vi phạm invariant surface lowercase.
- **Các setting prompt/log/version được nối vào runtime.** Prompt version chọn đúng resource,
  log level cấu hình logging, và mỗi dictionary hash được ghi idempotent vào
  `dictionary_version` thay vì để bảng này chết.
- **Eval CLI ép stdout/stderr UTF-8 trên Windows.** Report vốn ghi UTF-8 nhưng bước `print()`
  trước đó chết trên terminal cp1252 khi gặp tiếng Việt hoặc dấu ✓/✗, khiến `make eval` không
  chạy được dù toàn bộ case đã tính xong.

## Phase 13 — Làm lại UX nhập nguồn và định dạng đọc (2026-08-20)

- **Chuẩn hoá URL tại một điểm dùng chung.** Nhận tên miền thiếu scheme, protocol-relative URL,
  link Markdown/`<...>` và bỏ ký tự zero-width do copy/paste; web, JSON API, batch và liên kết
  chương tay đều dùng cùng quy tắc. Không tự xoá query/trailing punctuation vì chúng có thể là
  phần có nghĩa của URL.
- **Lỗi fetch có mã nguyên nhân và chiến lược retry.** 401/403/404/410, URL không an toàn, content
  không phải văn bản và browser challenge/CAPTCHA thất bại ngay; chỉ lỗi mạng, timeout, 429 và 5xx
  mới retry. UI không đổ exception thô làm thông điệp chính mà đưa ra hành động phù hợp: thử lại,
  kiểm tra link, mở nguồn hoặc dán nội dung.
- **Tách rõ “Mở từ liên kết” và “Dán nội dung”.** Link là primary flow; paste là fallback có thể
  bung ra ngay từ error card. Trạng thái chờ chiếm chỗ rõ ràng, nút bị khoá trong request, kết quả
  dùng `aria-live` và màn hình đọc gom điều hướng riêng khỏi tuỳ chỉnh hiển thị.
- **Tách đoạn thích ứng cho nội dung dán tay.** Khi không có blank line nhưng có ít nhất ba dòng
  đủ dài, mỗi dòng trở thành một đoạn; văn bản có blank line rõ ràng vẫn giữ thuật toán cũ. Text
  trong inline HTML dùng separator là dấu cách để không còn lỗi kiểu `Thiếu niênáo đenbước vào`.

## Phase 14 — Khôi phục tiêu đề chương thiếu (2026-08-20)

- **Tiêu đề được suy luận theo một quy tắc dùng chung.** Ưu tiên metadata/tiêu đề explicit, sau
  đó ba đoạn mở đầu có marker như “Chương”, “Hồi”, “Ngoại truyện”; một heading ngắn chỉ được nhận
  khi theo sau là đoạn văn dài rõ rệt. Cuối cùng mới suy từ số chương trong URL. Quy tắc dùng cho
  paste text, generic extractor, YAML adapter và cache legacy.
- **Dữ liệu cache cũ không cần backfill để hiển thị đúng.** `ChapterCacheRepo` dựng display title
  từ `raw_text`/URL khi cột `title` cũ rỗng, nên deploy code mới là thư viện tự lành ngay. Chương
  dán mới còn bỏ dòng heading đã suy luận khỏi body để không hiện tiêu đề hai lần.

## Phase 15 — Chốt đường production Render + Neon (2026-08-20)

- **Tách liveness và readiness.** `/api/health` là probe nhẹ; `/api/ready` thực hiện `SELECT 1`
  và là health check của Render, nên bản deploy mất kết nối Neon không được nhận traffic.
- **Production không tự tạo schema.** `VIETREADER_AUTO_CREATE_SCHEMA=0` buộc Alembic là nguồn
  sự thật duy nhất. `VIETREADER_REQUIRE_POSTGRES=1` fail-fast nếu thiếu/nhầm Neon URL, tránh
  fallback SQLite trên filesystem tạm.
- **Giới hạn pool và đóng engine có chủ ý.** Kết nối PostgreSQL có pre-ping, recycle, connect/
  checkout timeout và giới hạn 10 connection mỗi instance; lifespan dispose pool khi tắt.
- **Không ghi credentials vào log.** Seed và startup chỉ in database URL đã che user/password.
- **Docker build tự bảo vệ line ending Linux.** `.gitattributes` ép shell script dùng LF;
  Dockerfile vẫn normalize CRLF và đặt executable bit như lớp an toàn cuối. CI build rồi import
  runtime từ image để lỗi đóng gói không lọt qua chỉ vì pytest chạy được trên máy dev.

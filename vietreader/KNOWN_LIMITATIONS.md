# KNOWN LIMITATIONS

Trung thực về những gì chưa hoàn thiện / chưa được kiểm chứng đầy đủ, tính đến hết Phase 13.

## Chưa chạy được với LLM thật
Không có `ANTHROPIC_API_KEY` trong môi trường agent lúc build. Toàn bộ logic L3
(`llm/disambiguator.py`, `llm/anthropic.py`) đã test offline đầy đủ (`httpx.MockTransport`,
`FakeProvider`) và pass, nhưng **chưa có lần chạy thật nào với model Anthropic thật**:
- `tests/integration/test_anthropic_live.py` — skip, `NOT RUN`.
- `evals/run_eval.py --live` — skip, `NOT RUN`.
- `ambiguity_accuracy` trong `evals/REPORT.md` đo hành vi `FakeProvider` (luôn chọn candidate
  index 0), KHÔNG phải chất lượng đáng tin cậy của LLM thật. Cần chạy `--live` với API key thật
  trước khi coi số liệu này là đại diện cho chất lượng sản phẩm.

## Kiểm thử UI
UI có test HTTP/ASGI tự động và đã được kiểm tra qua một máy chủ Uvicorn local chạy thật; lượt gần
nhất còn tải end-to-end một trang mẫu công khai bằng URL thiếu `https://`. Bộ điều khiển trình duyệt
trực quan trong môi trường xác minh hiện tại không khởi tạo được do lỗi metadata của connector, nên
visual regression, khác biệt Safari/iOS và thao tác chọn chữ bằng cảm ứng vẫn cần kiểm tra trên
trình duyệt hoặc thiết bị thật.

## `make` — ĐÃ GIẢI QUYẾT (Phase 10)
Giới hạn này thuộc về máy Windows dùng để build ban đầu, không phải về code. Trên máy macOS hiện
tại, `make lint`, `make typecheck`, `make test`, `make eval` đều đã được gọi THẬT qua `make` và
exit 0, trên Python 3.12.13 (thay vì 3.11 như deviation Phase 0 ghi).

## Tên chương: lấy từ trang trước, slug URL là phương án cuối
Nhiều site đặt thẻ `<title>` của trang là TÊN BỘ TRUYỆN, nên tiêu đề trafilatura trả về khiến
mọi chương trùng tên nhau. `extraction/chapter_title.py` tìm tên chương thật ngay trong trang
(vế chương của thẻ `<title>`, `<h1>`, phần tử class `chapter-name`/`book-title`...) nên **giữ
nguyên dấu tiếng Việt**.

Chỉ khi trong trang không có chỗ nào nhắc đúng số chương thì mới suy từ slug URL — và slug vốn
không dấu, nên ra "Chương 3 — Tai ach". Số chương luôn đúng, đủ để phân biệt và sắp xếp. Gặp
trường hợp này thì viết adapter YAML cho site đó với selector trỏ thẳng vào thẻ tiêu đề chương.

## Dò chương trước/sau là phỏng đoán
`extraction/navigation.py` dựa vào `rel="next"/"prev"` và chữ trên liên kết. Sẽ trượt khi site
dùng nút JS không phải thẻ `<a>`, khi chữ trên nút bất thường, hoặc khi trang có nhiều cụm điều
hướng (ví dụ vừa có "chương sau" ở đầu vừa có ở cuối, trỏ khác nhau). Adapter YAML trong
`config/sites/` vẫn là cách chính xác nhất cho site đọc thường xuyên. Khi cả hai đều không được,
dùng ô "Sửa liên kết chương" ở cuối màn hình đọc để dán tay.

## Nhóm bộ truyện là heuristic theo URL, không phải metadata thật
Bộ truyện được suy ra bằng cách bỏ segment cuối của URL chương (`https://site/truyen-abc/chuong-5`
→ `https://site/truyen-abc`). Đúng với đa số site truyện Việt, nhưng sẽ sai nếu:
- Site đặt URL phẳng (`site.com/chuong-5`) → không nhận bộ nào, chương đứng lẻ (cố ý, xem
  DECISIONS.md Phase 11).
- Site đổi cấu trúc URL giữa chừng, hoặc cùng một truyện có nhiều đường dẫn khác nhau → bị tách
  thành nhiều bộ. Phải đổi tên/gộp thủ công; chưa có chức năng gộp hai bộ làm một.

Tên bộ mặc định lấy từ slug URL (`dau-pha-thuong-khung` → "Dau Pha Thuong Khung") nên thường
thiếu dấu tiếng Việt — có nút đổi tên trong trang bộ truyện.

## Thứ tự chương dựa vào số hiệu bắt được từ URL/tiêu đề
Regex bắt các dạng `chuong-5`, `chapter 12`, `chap.7`. Chương không có số (ngoại truyện, lời tựa)
xếp cuối theo thứ tự đọc lần đầu. Truyện đánh số kiểu `5.1`, `5b` hoặc dùng chữ ("chương năm")
sẽ xếp sai.

## Hai URL có nội dung trùng khít dùng chung một hàng cache
`chapter_cache` khoá theo NỘI DUNG (`raw_hash + dict_version + prompt + model` — spec §2.4), nên
hai URL khác nhau mà văn bản giống hệt sẽ dùng chung một hàng. Chương giữ bộ truyện được xếp
LẦN ĐẦU và không bị di chuyển (xem DECISIONS.md Phase 11), nhưng hệ quả là URL thứ hai không có
hàng riêng: nó hiện dưới bộ của URL thứ nhất. Gặp phải khi một chương truy cập được qua nhiều URL
(có/không `/` cuối, `?page=1`, http/https), hoặc chương placeholder "nội dung đang cập nhật".
Muốn xử lý triệt để phải tách "chương tại một URL" khỏi "kết quả xử lý một đoạn văn bản" thành
hai bảng — thay đổi kiến trúc cache đã chốt, chưa làm.

## Ghi chú (feedback) hoàn toàn cục bộ
Không gửi đi đâu, không đồng bộ, không có thông báo. Đây là sổ tay trong file SQLite của bạn.
Ghi chú trỏ tới `chapter_cache_id` cụ thể; nếu chương đó được xử lý lại sau khi sửa từ điển,
bản ghi cache mới có id khác — ghi chú cũ vẫn trỏ tới bản cũ (vẫn mở được, nhưng là nội dung
trước khi sửa).

## Vị trí đọc chỉ chính xác tới cấp đoạn văn
Vị trí được lưu/khôi phục theo chỉ số paragraph, không theo offset pixel hay câu. Khi mở lại, trang
cuộn tới ĐẦU đoạn đang đọc dở chứ không đúng dòng đang nhìn. Với cỡ chữ rất lớn và đoạn văn dài,
sai lệch có thể tới vài dòng. Đủ dùng cho đọc truyện, nhưng không phải khôi phục chính xác tuyệt đối.

## Việc xử lý lại chương tích luỹ row trong `chapter_cache`
Mỗi lần sửa từ điển rồi mở lại một chương sẽ sinh thêm một row cache mới cho cùng chương đó (cache
key bao gồm `dict_version_hash` — đúng thiết kế). Thư viện đã gộp theo `raw_hash` nên người dùng
chỉ thấy một mục, nhưng các row cũ KHÔNG bị dọn. Chưa có lệnh vacuum/dọn cache; với quy mô cá nhân
thì không đáng lo, nhưng file DB sẽ lớn dần nếu bạn sửa từ điển rất thường xuyên.

## Word segmentation tiếng Việt
Matcher (L1) dùng kiểm tra ký tự liền kề (word-boundary theo \w mở rộng), KHÔNG phân đoạn từ
tiếng Việt đầy đủ. Vì tiếng Việt phân tách MỌI âm tiết bằng dấu cách (không chỉ phân tách từ),
matcher có thể match một cụm ngắn khi nó thực ra là phần đầu của một từ ghép dài hơn nhưng KHÔNG
có trong từ điển (ví dụ: "lão giả" trong "lão giả tử" nếu "giả tử" không phải entry nào — xem
DECISIONS.md mục Phase 1). Muốn khắc phục hoàn toàn cần phân đoạn từ tiếng Việt đầy đủ — nằm
ngoài phạm vi kiến trúc đã chốt (§1: matcher phải deterministic, không phân tích ngôn ngữ).

## Smoothing / ngữ pháp sau khi thay từ
Đúng theo §5 (ngoài phạm vi v1): thay từ có thể làm câu lấn cấn ngữ pháp (ví dụ chia động từ,
giới từ không khớp sau khi thay danh từ/đại từ). Không có smoothing pass. Người đọc dựa vào
highlight + "Xem bản gốc" để tự nhận biết.

## Inline edit trong Dictionary manager (web UI) chỉ giới hạn `priority`/`enabled`
Sửa `surface`/`policy`/`replacement`/`candidates` qua UI web cần xoá rồi tạo lại (JSON API
`PATCH /api/dictionary/{id}` KHÔNG bị giới hạn này — hỗ trợ sửa mọi field). Xem Phase 7
Assumptions.

## Bảo vệ URL fetch là bảo thủ
Fetcher chỉ cho HTTP(S), xác minh TLS và mặc định chặn localhost, IP private, link-local cùng các
địa chỉ không public. Vì vậy URL chương nằm trong intranet/NAS sẽ bị từ chối cho tới khi người vận
hành chủ động đặt `VIETREADER_FETCH_ALLOW_PRIVATE_NETWORKS=true`. Không bật biến này trên service
công khai.

## Coverage `core/dictionary.py` 86% (không phải 100%)
Các dòng chưa cover chủ yếu là nhánh raise lỗi invariant cụ thể (`DictionaryEntryError` cho từng
điều kiện sai riêng lẻ — REPLACE thiếu replacement, ASK thiếu candidates, v.v.) — đã test một số
nhánh tiêu biểu qua `db/repositories/dictionary.py` và API, nhưng không test riêng từng nhánh raise
trong `core/dictionary.py`. Không ảnh hưởng tới ngưỡng coverage bắt buộc (`core/` tổng thể vẫn
>= 90%, xem PHASE_REPORTS.md Phase 9).

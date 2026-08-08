# KNOWN LIMITATIONS

Trung thực về những gì chưa hoàn thiện / chưa được kiểm chứng đầy đủ, tính đến hết Phase 9.

## Chưa chạy được với LLM thật
Không có `ANTHROPIC_API_KEY` trong môi trường agent lúc build. Toàn bộ logic L3
(`llm/disambiguator.py`, `llm/anthropic.py`) đã test offline đầy đủ (`httpx.MockTransport`,
`FakeProvider`) và pass, nhưng **chưa có lần chạy thật nào với model Anthropic thật**:
- `tests/integration/test_anthropic_live.py` — skip, `NOT RUN`.
- `evals/run_eval.py --live` — skip, `NOT RUN`.
- `ambiguity_accuracy` trong `evals/REPORT.md` đo hành vi `FakeProvider` (luôn chọn candidate
  index 0), KHÔNG phải chất lượng đáng tin cậy của LLM thật. Cần chạy `--live` với API key thật
  trước khi coi số liệu này là đại diện cho chất lượng sản phẩm.

## Screenshot UI
Môi trường agent không có trình duyệt/khả năng chụp ảnh màn hình. Phase 7 đã xác minh UI bằng
HTTP request thật (curl/httpx) tới server thật đang chạy + 11 test tự động qua `httpx.AsyncClient`
(bao gồm 1 test end-to-end quick-add thật), nhưng chưa có ai xác nhận trải nghiệm thị giác thật
trong trình duyệt (bố cục, dark mode, popup quick-add khi bôi đen chuột thật, v.v.).

## `make` không chạy được trên máy build
Không có binary `make` trên máy Windows dùng để build (không Git-Bash-make/mingw32-make/nmake).
Mọi lệnh trong `Makefile` đã được chạy trực tiếp (không qua `make`) và pass — bản thân `Makefile`
đúng cú pháp — nhưng tiêu chí acceptance gốc dạng `make install && make test` chưa từng thực sự
được gọi qua `make`. Cài `make` (qua Chocolatey/scoop/WSL) trước khi coi acceptance này là đã đạt
100% theo đúng nghĩa đen.

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

## `series_key` (nhóm chương theo truyện) đơn giản hoá
`series_key` hiện = URL của chương (hoặc `"raw"` khi paste text), KHÔNG có khái niệm "truyện"
độc lập nhóm nhiều chương/URL khác nhau lại với nhau. Vị trí đọc được lưu theo từng URL/nguồn
riêng biệt, không tự động liên kết "chương 2" với "chương 1" của cùng bộ truyện trừ khi URL cùng
series_key. Xem Phase 7 Assumptions.

## Coverage `core/dictionary.py` 86% (không phải 100%)
Các dòng chưa cover chủ yếu là nhánh raise lỗi invariant cụ thể (`DictionaryEntryError` cho từng
điều kiện sai riêng lẻ — REPLACE thiếu replacement, ASK thiếu candidates, v.v.) — đã test một số
nhánh tiêu biểu qua `db/repositories/dictionary.py` và API, nhưng không test riêng từng nhánh raise
trong `core/dictionary.py`. Không ảnh hưởng tới ngưỡng coverage bắt buộc (`core/` tổng thể vẫn
>= 90%, xem PHASE_REPORTS.md Phase 9).

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

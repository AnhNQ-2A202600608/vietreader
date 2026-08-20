# VietReader — Danh sách công việc & Trạng thái dự án (TODO & Roadmap)

> Cập nhật lần cuối: **20/08/2026**
> Trạng thái hiện tại: **Production-hardened (Render + Neon; bắt buộc auth khi deploy theo blueprint)**
> Domain: **https://vietreader.onrender.com**

---

## 1. Những việc ĐÃ HOÀN THÀNH (Completed)

### 🚀 Triển khai & Vận hành Đám mây (Deployment & Cloud Infrastructure)
- [x] **Render Web Service + Neon PostgreSQL**:
  - Cấu hình file `render.yaml` tự động build `Dockerfile` từ nhánh `main`.
  - Tự động chuyển đổi giữa SQLite (Local) và PostgreSQL (Neon trên Production) với cơ chế `pool_pre_ping`.
  - Tự động chạy Migration và nạp từ điển mẫu khi khởi động container (`VIETREADER_SEED_ON_START=1`).
- [x] **Monitor và keepalive tuỳ chọn cho gói Free**:
  - `/api/health` hỗ trợ GET/HEAD cho monitor ngoài; `/api/ready` kiểm tra cả kết nối Neon.
  - Workflow dự phòng **GitHub Actions** (`.github/workflows/keepalive.yml`) chỉ chạy khi có secret.
  - Keepalive không phải SLA; production cần ổn định nên dùng Render Starter hoặc cao hơn.
- [x] **CI/CD Tự động hóa**:
  - Tự động kiểm tra chất lượng mã nguồn (Ruff linter + Mypy typecheck + test/eval).
  - Render dùng native `autoDeployTrigger: checksPass`; không cần Deploy Hook hoặc secret riêng.
- [x] **Hardening ứng dụng công khai**:
  - HTTP Basic Auth bắt buộc trong blueprint Render; health/readiness vẫn công khai cho monitor.
  - Chặn request thay đổi trạng thái từ origin khác; fetcher chặn SSRF tới localhost/private IP.
  - Bật xác minh TLS và kiểm tra lại mọi đích redirect trước khi tải.
  - Readiness kiểm tra Neon bằng `SELECT 1`; production fail-fast nếu thiếu PostgreSQL,
    migration Alembic là nguồn schema duy nhất và database URL được che khỏi log.

---

### 📚 Xử lý & Bóc tách Truyện thông minh (Smart Extraction & Fetcher)
- [x] **Giả lập trình duyệt chuẩn (Anti-Bot Bypass)**:
  - Cập nhật User-Agent chuẩn Chrome Desktop và thêm đầy đủ bộ header `Accept`, `Accept-Language: vi-VN`.
  - Bật cơ chế tự động chuyển hướng (`follow_redirects=True`) để không bị lỗi khi web truyện đổi link.
- [x] **Tích hợp Site Adapters cho các web truyện lớn**:
  - Cấu hình trích xuất chuẩn cho: **Truyện Full** (`truyenfull.vn`, `truyenfull.io`), **Tàng Thư Viện** (`tangthuvien.net`), **Mê Truyện Chữ** (`metruyenchu.com`), **WikiDịch** (`wikidich.net`).
- [x] **Bộ trích xuất đa tầng (Multi-layer Fallback Extractor)**:
  - Tự động quét và loại bỏ quảng cáo, nút bấm, script rác.
  - Sử dụng `selectolax` heuristic phân tích cấu trúc truyện trước khi chuyển qua `trafilatura`.
- [x] **Xử lý lỗi thân thiện**:
  - Bổ sung trang báo lỗi `_reader_error.html` khi link bị chặn Cloudflare và hướng dẫn người dùng dán nội dung chữ trực tiếp.
  - Tự động cuộn trang (`scrollIntoView`) mượt mà đến phần nội dung truyện sau khi xử lý xong.

---

### 📖 Bộ Từ điển & Ngôn ngữ (Dictionary System)
- [x] **Mở rộng kho từ vựng Hán-Việt, Tiên hiệp & Kiếm hiệp**:
  - Bổ sung hàng trăm thuật ngữ phân loại theo 3 chính sách:
    - **`REPLACE`**: Chuẩn hóa từ xưng hô (*lão gia, phu quân, hạ nhân, điếm tiểu nhị, chưởng quầy, nha hoàn, lệnh huynh...*) và các cụm từ hành động (*khẽ giật mình, sắc mặt đại biến, khóe miệng co giật...*).
    - **`KEEP`**: Bảo vệ thuật ngữ tu tiên không bị dịch sai (*trúc cơ, luyện khí, hóa thần, luyện hư, hợp thể, đại thừa, thần thức, công pháp, tâm pháp, trận pháp, linh căn, đoạt xá, phi thăng...*).
    - **`ASK`**: Đưa các từ ngữ phụ thuộc ngữ cảnh vào hỏi LLM (*trẫm, ái khanh, thần, nô tỳ, tiểu nhân, lão nô, tiên sinh...*).
- [x] **Tối ưu hóa script nạp dữ liệu (`seed_dictionary.py`)**:
  - Chỉ kiểm tra và nạp các từ chưa có trong Database, tránh ghi đè dữ liệu người dùng tùy chỉnh.

---

### 🎨 Giao diện & Trải nghiệm Người dùng (UX & Aesthetics)
- [x] **Hệ thống Typography chuẩn đọc sách**:
  - Tích hợp font chữ **Literata** (Google Books) chuyên dụng cho đọc truyện dài tập, hiển thị dấu tiếng Việt sắc nét.
  - Tích hợp font **Plus Jakarta Sans** cho toàn bộ UI và thanh điều hướng.
- [x] **Chế độ đọc 3 tông màu (Theme Switcher)**:
  - Hỗ trợ luân phiên 3 giao diện: **Sáng (Light)**, **Sepia (Giấy cổ điển dịu mắt)**, và **Tối (Dark)**.
- [x] **Nút nổi cuộn nhanh lên đầu trang (`Scroll-to-top`)**:
  - Tự động xuất hiện khi cuộn qua 350px và cuộn mượt mà lên đầu trang khi bấm.
- [x] **Hiệu ứng chuyển cảnh mượt mà**:
  - Hiệu ứng đổi màu mềm (`cubic-bezier transitions`), phản hồi bấm nút xúc giác (`active scale 0.97`).
  - Thanh tiến trình đọc (Reading Progress Bar) gradient ở đỉnh trang.

---

## 2. Kế hoạch & Đề xuất Cải thiện Tiếp theo (Roadmap / Next Improvements)

### ⚡ Cải thiện Hiệu năng & Tiện ích đọc
- [ ] **Tự động tải trước chương tiếp theo (Prefetching Next Chapter)**:
  - Khi người dùng cuộn đến 70% chương hiện tại, hệ thống tự động ngầm gửi request lấy chương sau để khi bấm "Chương sau →" là hiển thị tức thì.
- [ ] **Chế độ đọc ngoại tuyến (Offline Reading / PWA Service Worker)**:
  - Cho phép lưu 5-10 chương gần nhất vào bộ nhớ trình duyệt (IndexedDB / Cache API) để đọc được ngay cả khi mất mạng.
- [ ] **Tùy chỉnh khoảng cách dòng & Lề đọc (Line-height & Margin Controls)**:
  - Bổ sung thanh trượt tùy chỉnh khoảng cách dòng (dày/thưa) và độ rộng cột đọc trong trang Cài đặt (`/settings`).

---

### 🌐 Mở rộng Bóc tách Truyện (More Site Adapters)
- [ ] Bổ sung cấu hình YAML cho các trang truyện mới:
  - `bachngocsach.com.vn`
  - `truyenchu.vn`
  - `nettruyen` / `truyenqq` (truyện chữ)
  - `69shu.me` / `qidian.com` (site tiếng Trung gốc)
- [ ] Bổ sung cơ chế phát hiện số chương thông minh hơn cho các URL dạng số tùy biến.

---

### 🤖 Nâng cấp Trí tuệ Nhân tạo (LLM Disambiguation)
- [ ] **Hỗ trợ thêm nhiều Provider LLM miễn phí / tốc độ cao**:
  - Tích hợp **Google Gemini Flash** (rất nhanh và có gói Free hào phóng).
  - Tích hợp **Groq** (tốc độ siêu nhanh, Llama 3).
  - Tích hợp **OpenAI** / **DeepSeek API**.
- [ ] **Ghi nhớ ngữ cảnh xưng hô theo nhân vật**:
  - Tự động nhớ mối quan hệ giữa các nhân vật chính trong cùng một bộ truyện để nhất quán đại từ xưng hô xuyên suốt hàng trăm chương.

---

## 3. Lệnh kiểm tra & Bảo trì nhanh

```bash
# Chạy toàn bộ test
pytest -q

# Kiểm tra định dạng code & typecheck
python -m ruff check src tests scripts
python -m mypy src/vietreader/core

# Khởi động server local
uvicorn vietreader.api.app:app --reload --port 8000
```

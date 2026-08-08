# VietReader

AI Vietnamese Reading Assistant — LLM chỉ chọn giữa các phương án đóng cho từng span mơ hồ,
không bao giờ nhìn thấy hay viết lại cả đoạn văn. Xem `AGENT_WORK_ORDER_VietReader.md` (thư mục
gốc repo) cho spec đầy đủ.

> Tài liệu này sẽ được hoàn thiện đầy đủ ở Phase 9 (cài đặt, chạy, thêm site adapter, thêm
> dictionary entry, chạy eval). Hiện tại (Phase 0) mới có khung dự án.

## Quick start (dev, chưa đầy đủ tính năng)

```bash
cd vietreader
make install
make lint
make typecheck
make test
```

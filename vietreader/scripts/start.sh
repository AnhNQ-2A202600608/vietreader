#!/bin/sh
# Lệnh khởi động của container. Trước đây nằm gọn trong CMD của Dockerfile, tách ra vì giờ có
# thêm bước seed có điều kiện và nhét hết vào một dòng `sh -c` thì không ai đọc nổi.
set -e

# In ra database đang dùng, che phần mật khẩu. Trên nền tảng có đĩa tạm (Render free), quên
# khai VIETREADER_DATABASE_URL nghĩa là app âm thầm quay về SQLite rồi mất sạch dữ liệu sau
# mỗi lần khởi động lại. Một dòng log ở đây biến lỗi im lặng đó thành lỗi nhìn thấy được.
python - <<'PY'
import os, re
url = os.environ.get("VIETREADER_DATABASE_URL", "(không đặt — sẽ dùng mặc định trong settings.py)")
print("==> database:", re.sub(r"://[^@/]*@", "://***@", url))
if url.startswith("sqlite") or url.startswith("(không đặt"):
    print("    LƯU Ý: đang dùng SQLite. Chỉ an toàn khi máy có đĩa bền.")
    print("    Trên Render free (đĩa tạm) thì dữ liệu sẽ mất — xem DEPLOY_RENDER.md §3.")
PY

# Migration chạy TRƯỚC khi lên server: không có cửa sổ nào mà code mới chạy trên schema cũ.
# migrations/env.py đọc VIETREADER_DATABASE_URL — cùng biến app dùng — nên nó migrate đúng
# database mà app sẽ mở.
echo "==> alembic upgrade head"
alembic upgrade head

# Nạp từ điển mẫu lúc khởi động. Mặc định TẮT: khi tự host bạn chạy tay một lần là xong
# (DEPLOY.md §7). Bật lên khi deploy lên nền tảng không cho chạy lệnh một lần như Render free
# — ở đó đây là cách duy nhất để từ điển không rỗng.
#
# An toàn khi chạy lại: seed_dictionary.py bỏ qua entry đã tồn tại, không tạo trùng, không ghi
# đè. Nên để nguyên ON cũng được, mỗi lần khởi động chỉ tốn thêm chưa tới một giây.
if [ "${VIETREADER_SEED_ON_START:-0}" = "1" ]; then
  echo "==> seed từ điển mẫu (VIETREADER_SEED_ON_START=1)"
  python scripts/seed_dictionary.py
fi

# PORT do nền tảng cấp (Render, Railway…) hoặc lấy mặc định 8000 khi chạy bằng docker compose.
echo "==> uvicorn trên cổng ${PORT:-8000}"
exec uvicorn vietreader.api.app:app --host 0.0.0.0 --port "${PORT:-8000}"

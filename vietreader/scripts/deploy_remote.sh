#!/usr/bin/env bash
# Chạy TRÊN MÁY CHỦ, được GitHub Actions đẩy qua SSH (xem .github/workflows/deploy.yml).
#
# Chạy tay cũng được, khi muốn deploy mà không qua GitHub:
#   ssh ubuntu@<ip> 'bash -s' < vietreader/scripts/deploy_remote.sh
#
# Đường dẫn mặc định là ~/vietreader/vietreader (repo clone vào ~/vietreader, app nằm trong
# thư mục con). Clone chỗ khác thì khai secret DEPLOY_DIR trên GitHub — deploy.yml truyền nó
# vào đây thành VIETREADER_DIR.
#
# Đừng đặt biến này trong ~/.bashrc: SSH không tương tác (đúng cái mà GitHub Actions dùng) thoát
# khỏi ~/.bashrc ngay ở mấy dòng đầu, nên khai ở đó sẽ không bao giờ có tác dụng.
set -euo pipefail

APP_DIR="${VIETREADER_DIR:-$HOME/vietreader/vietreader}"

if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
  echo "LỖI: không thấy docker-compose.yml trong $APP_DIR" >&2
  echo "      Clone repo vào ~/vietreader, hoặc khai secret DEPLOY_DIR trỏ đúng chỗ." >&2
  exit 1
fi

cd "$APP_DIR"

echo "==> Sao lưu database trước khi đổi bất cứ thứ gì"
# Thất bại ở đây (app chưa từng chạy, lần deploy đầu tiên) không phải lý do để dừng.
docker compose exec -T app ./scripts/backup_db.sh \
  || echo "    bỏ qua: chưa có container đang chạy để sao lưu"

echo "==> Lấy mã nguồn mới từ origin/main"
# reset --hard để máy chủ luôn khớp đúng origin/main, không tích luỹ thay đổi lạ qua thời gian.
# File chưa track KHÔNG bị đụng tới, nên .env và docker-compose.override.yml vẫn nguyên.
git fetch --prune origin
git reset --hard origin/main

echo "==> Dựng lại ảnh và khởi động"
docker compose up -d --build

echo "==> Chờ app trả lời healthcheck"
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "    OK sau $((i * 5)) giây"
    # Ảnh cũ sau mỗi lần --build sẽ chất đống và làm đầy đĩa máy nhỏ.
    docker image prune -f >/dev/null
    echo "==> Deploy xong: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 5
done

echo "LỖI: app không trả lời /api/health sau 200 giây" >&2
docker compose logs --tail 80 app >&2
exit 1

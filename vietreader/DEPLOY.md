# Đưa VietReader lên máy chủ

Viết cho **Oracle Cloud Always Free** — máy ảo chạy 24/7, miễn phí vĩnh viễn, không ngủ nên
không có cảnh mở app phải chờ. Các bước dưới cũng dùng được cho bất kỳ máy chủ Linux nào.

Deployment nằm ngoài phạm vi work order gốc (§5). Tài liệu này bổ sung sau, theo yêu cầu.

---

## Trước khi bắt đầu

App chạy **không có lớp đăng nhập** — đây là lựa chọn có chủ đích cho một ứng dụng cá nhân.
Hệ quả cần biết: ai có địa chỉ máy chủ đều dùng được app, kể cả bot quét IP. Vì vậy khuyến nghị
**để trống `VIETREADER_LLM_API_KEY` trên máy chủ** — mất tính năng ASK (vài từ mơ hồ giữ nguyên
thay vì hỏi LLM), nhưng đổi lại không có nguy cơ ai đó gọi API bằng khoá của bạn.

Muốn chắn lại về sau thì không phải sửa code: đặt Cloudflare Access phía trước, hoặc giới hạn
IP ở tầng firewall.

Hai điều về Oracle nên biết trước:
- Đăng ký **cần thẻ để xác minh danh tính** (gói Always Free không trừ tiền, nhưng không có thẻ
  thì không mở được tài khoản).
- Máy ARM (Ampere A1) hay báo hết chỗ tuỳ khu vực. Vướng thì thử khu vực khác, hoặc dùng máy
  AMD micro — nhỏ hơn nhưng đủ cho một người đọc.

---

## 1. Tạo máy ảo

Chọn Ubuntu LTS. Mở cổng 80 và 443 trong Security List của VCN. Trên máy:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git sqlite3
sudo usermod -aG docker $USER && newgrp docker
```

Oracle mặc định chặn hết ở firewall trong máy, phải mở thêm:

```bash
sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 2. Lấy mã nguồn và cấu hình

```bash
git clone <repo-cua-ban> && cd vietreader
cp config/settings.example.env .env
```

Sửa `.env`, tối thiểu:

```
VIETREADER_READER_NAME=Ngân Giang
VIETREADER_LLM_API_KEY=          # nên để trống, xem ghi chú ở trên
```

Không cần đặt `VIETREADER_DATABASE_URL` — `docker-compose.yml` tự trỏ vào volume.

## 3. Chạy

```bash
docker compose up -d --build
curl http://localhost:8000/api/health     # {"status":"ok"}
```

Container tự chạy `alembic upgrade head` trước khi lên server, nên lần đầu là có sẵn bảng.

Nạp từ điển mẫu (65 entry) một lần:

```bash
docker compose exec app python scripts/seed_dictionary.py
```

## 4. HTTPS

Nên có HTTPS để nội dung đọc không đi qua mạng dạng thô. Cách gọn nhất là Caddy — tự xin và tự gia hạn chứng chỉ:

```bash
sudo apt install -y caddy
echo 'doc.ten-mien-cua-ban.com {
    reverse_proxy 127.0.0.1:8000
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

Cần một tên miền trỏ về IP máy. Chưa có tên miền thì dùng dịch vụ DNS động miễn phí.

## 5. Sao lưu

Đây là toàn bộ thư viện, vị trí đọc, từ điển và ghi chú — mất là mất hết.

```bash
docker compose exec app ./scripts/backup_db.sh /data/vietreader.db /data/backups
```

Đặt lịch hằng ngày lúc 3 giờ sáng, giữ 14 bản gần nhất:

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * cd $PWD && docker compose exec -T app ./scripts/backup_db.sh") | crontab -
```

Thỉnh thoảng chép một bản về máy bạn — backup nằm cùng máy chủ thì máy chết là mất cả hai:

```bash
scp ubuntu@<ip>:/var/lib/docker/volumes/vietreader_vietreader-data/_data/backups/*.gz .
```

## 6. Nâng cấp

```bash
git pull && docker compose up -d --build
```

Volume dữ liệu không bị đụng tới. Migration tự chạy khi container khởi động.

---

## Ghi chú

**Vì sao không dùng Render/Vercel/Cloud Run.** Render free ngủ sau 15 phút, đánh thức mất khoảng
một phút — mỗi tối mở app là một lần chờ. Cloud Run co về 0, muốn giữ luôn chạy phải bật
min-instance và cái đó tính tiền. Vercel không chạy tiến trình thường trú và không có đĩa bền,
mà app này lại không có frontend tách rời để tận dụng thế mạnh của Vercel.

**Vì sao giữ SQLite.** Máy ảo có đĩa bền thật nên không cần dời DB. Giữ SQLite là không phải
thêm dependency, không phải viết lại migration, và toàn bộ test hiện có vẫn còn nguyên giá trị.
Với một người đọc thì SQLite thừa sức.

**Điều khoản free tier đổi thường xuyên** — nên kiểm tra lại trang giá của Oracle trước khi
dựa hẳn vào, vì "Always Free" chính là điểm mấu chốt của lựa chọn này.

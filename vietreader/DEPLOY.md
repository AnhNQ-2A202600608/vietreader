# Đưa VietReader lên máy chủ — miễn phí, có tự động deploy

Viết cho **Oracle Cloud Always Free**: máy ảo chạy 24/7, **miễn phí vĩnh viễn**, không ngủ nên
không có cảnh mở app phải chờ. Cộng thêm **GitHub Actions** để mỗi lần bạn merge code vào `main`
thì máy chủ tự cập nhật — không phải SSH vào gõ lệnh gì.

Tổng chi phí: **$0/tháng.** Oracle Always Free không hết hạn, GitHub Actions miễn phí trong hạn
mức thừa sức cho một dự án (repo public: không giới hạn; repo private: 2.000 phút/tháng, mà một
lần deploy tốn khoảng 1 phút).

Từ §4 trở đi dùng được cho bất kỳ máy chủ Linux nào (VPS thuê, máy cũ ở nhà, Raspberry Pi).

Deployment nằm ngoài phạm vi work order gốc (§5). Tài liệu này bổ sung sau, theo yêu cầu.

**Thời gian:** khoảng 60–75 phút lần đầu, trong đó 10–25 phút là ngồi chờ build ảnh Docker.
Sau đó mỗi lần deploy là `git push` và chờ ~1 phút.

> **Oracle Always Free cần thẻ để đăng ký** (không trừ tiền, chỉ để xác minh danh tính). Không
> có thẻ thì dùng [DEPLOY_RENDER.md](DEPLOY_RENDER.md) — Render + Neon, $0/tháng, không hỏi thẻ,
> cũng có CI/CD. Đánh đổi là app ngủ sau 15 phút và dữ liệu chuyển sang Postgres.
>
> Tài liệu này vẫn dùng được nguyên vẹn cho **bất kỳ máy Linux nào bạn có sẵn** — VPS thuê, máy
> cũ ở nhà, Raspberry Pi — từ §3 trở đi. Đó là cách duy nhất giữ được SQLite và không có cold
> start. Còn [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) là phương án trả phí (~$5/tháng, cần thẻ).

---

## Mục lục

| | |
|---|---|
| [0. Trước khi bắt đầu](#0-trước-khi-bắt-đầu) | Ba quyết định phải chốt trước |
| [1. Tạo máy ảo](#1-tạo-máy-ảo) | Oracle Cloud |
| [2. Mở cổng](#2-mở-cổng-hai-tầng-firewall) | Hai tầng firewall, hay quên tầng thứ hai |
| [3. Cài Docker](#3-cài-docker) | + swap nếu máy 1GB RAM |
| [4. Lấy mã nguồn và cấu hình](#4-lấy-mã-nguồn-và-cấu-hình) | `.env` |
| [5. Build và chạy](#5-build-và-chạy) | |
| [6. Kiểm tra](#6-kiểm-tra) | Trước khi đi tiếp |
| [7. Nạp từ điển mẫu](#7-nạp-từ-điển-mẫu) | 65 entry |
| [8. HTTPS](#8-https) | Caddy, chứng chỉ tự gia hạn |
| [9. Chắn truy cập](#9-chắn-truy-cập-nên-làm-nếu-mở-ra-internet) | Không cần sửa code |
| [10. Tự động deploy khi push main](#10-tự-động-deploy-khi-push-main) | **CI/CD — phần bạn cần** |
| [11. Sao lưu và khôi phục](#11-sao-lưu-và-khôi-phục) | Có cả quy trình restore |
| [12. Nâng cấp](#12-nâng-cấp) | Sau §10 chỉ còn `git push` |
| [13. Vận hành hằng ngày](#13-vận-hành-hằng-ngày) | Log, restart, dọn đĩa |
| [14. Khắc phục sự cố](#14-khắc-phục-sự-cố) | |
| [15. Ghi chú thiết kế](#15-ghi-chú-thiết-kế) | Vì sao chọn cách này |

---

## 0. Trước khi bắt đầu

Ba quyết định nên chốt trước khi gõ lệnh — chúng ảnh hưởng tới các bước sau.

### 0.1 App không có lớp đăng nhập

Đây là lựa chọn có chủ đích cho một ứng dụng cá nhân, và **không có biến môi trường nào bật
đăng nhập lên được** — trong code không tồn tại tính năng đó. Hệ quả: ai biết địa chỉ máy chủ
đều dùng được app, kể cả bot quét IP (chúng quét liên tục và sẽ tìm ra IP của bạn trong vòng
vài giờ, không cần ai đi rêu rao).

Hai cách xử lý, chọn một:

- **Cách A — để trống `VIETREADER_LLM_API_KEY`.** Mất tính năng ASK (span mơ hồ giữ nguyên
  thay vì hỏi LLM, có ghi WARN vào `run_log`); REPLACE, KEEP, extraction, reader, từ điển,
  ghi chú vẫn chạy đủ. Đổi lại không ai gọi được API bằng khoá của bạn.
- **Cách B — đặt khoá, nhưng chắn bằng basic auth ở §9.** Giữ đủ tính năng. Bắt buộc phải làm
  §9 **đầy đủ**, gồm cả việc đóng cổng 8000 — chắn Caddy mà quên đóng 8000 thì coi như không chắn.

Nếu chưa chắc: đi Cách A trước, mọi thứ khác vẫn hoạt động, thêm khoá sau lúc nào cũng được
(sửa `.env` rồi `docker compose up -d`).

### 0.2 Tên miền

HTTPS (§8) cần một tên miền trỏ về IP máy chủ. Chuẩn bị trước một trong hai:

- Tên miền của bạn — thêm một bản ghi `A` trỏ về IP máy (ví dụ `doc.ten-mien.com → 152.x.x.x`).
- Hoặc DNS động miễn phí (DuckDNS, No-IP…) nếu không muốn mua tên miền.

Chưa có gì cả thì vẫn deploy được tới hết §7 và dùng qua đường hầm SSH (§6) — chỉ là chưa mở
được từ điện thoại hay máy khác. Bổ sung §8 sau lúc nào cũng được.

### 0.3 Hai điều về Oracle nên biết trước

- Đăng ký **cần thẻ để xác minh danh tính**. Gói Always Free không trừ tiền, nhưng không có
  thẻ thì không mở được tài khoản.
- Máy ARM (Ampere A1) hay báo **"Out of host capacity"** tuỳ khu vực. Vướng thì thử khu vực
  khác, hoặc dùng máy AMD micro — nhỏ hơn nhưng đủ cho một người đọc (xem lưu ý swap ở §3.3).

---

## 1. Tạo máy ảo

Trong Oracle Cloud Console: **Compute → Instances → Create instance**.

| Mục | Chọn |
|---|---|
| Image | **Ubuntu 24.04 LTS** (quan trọng — xem ghi chú dưới) |
| Shape | Ampere A1 (ARM), 1–2 OCPU / 6–12 GB RAM. Không có chỗ thì VM.Standard.E2.1.Micro |
| SSH keys | Tải file private key về, hoặc dán public key sẵn có của bạn |
| Networking | Assign a public IPv4 address: **có** |

> **Vì sao Ubuntu 24.04:** §3 cài Docker bằng gói `docker-compose-v2` có sẵn trong kho Ubuntu.
> Gói này có từ 23.10 trở đi. Trên 22.04 nó không tồn tại và bạn sẽ phải thêm kho của Docker —
> làm được, chỉ là dài hơn không cần thiết.

Ghi lại **IP public** và đăng nhập thử:

```bash
ssh -i duong-dan-toi-key ubuntu@<ip>
```

Từ đây mọi lệnh đều chạy trên máy chủ, trừ khi ghi rõ "trên máy bạn".

Đặt múi giờ luôn, để lịch backup 3 giờ sáng ở §11 đúng nghĩa 3 giờ sáng:

```bash
sudo timedatectl set-timezone Asia/Ho_Chi_Minh
```

---

## 2. Mở cổng (hai tầng firewall)

Oracle chặn ở **hai** nơi. Mở một nơi rồi tưởng xong là lỗi phổ biến nhất khi deploy trên
Oracle — biểu hiện: `curl` trên chính máy chủ thì được, mà trình duyệt ở nhà thì treo cho tới
khi timeout.

### 2.1 Tầng ngoài — Security List của VCN

Console: **Networking → Virtual Cloud Networks → (VCN của bạn) → Subnets → (subnet) →
Security Lists → Default Security List → Add Ingress Rules.**

Thêm hai luật:

| Source CIDR | IP Protocol | Destination Port Range |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

**Chỉ hai luật này, đừng mở thêm cổng 8000.** App không có lớp đăng nhập nên không bao giờ được
phơi thẳng ra Internet; `docker-compose.yml` đã cố ý ràng nó vào `127.0.0.1`, và Caddy ở §8 mới
là cửa vào duy nhất. Muốn xem app trước khi dựng Caddy thì dùng đường hầm SSH ở §6.

Cổng 22 (SSH) đã mở sẵn trong luật mặc định của Oracle — giữ nguyên, §10 cần nó để GitHub
Actions vào deploy.

### 2.2 Tầng trong — iptables trên máy

Ảnh Ubuntu của Oracle có sẵn bộ luật iptables chặn gần hết. Xem bộ luật hiện tại trước, đừng
chèn mù:

```bash
sudo iptables -L INPUT --line-numbers -n
```

Bạn sẽ thấy cuối chuỗi INPUT có một luật `REJECT ... all -- 0.0.0.0/0`. Ghi lại **số thứ tự**
của nó — mọi luật ACCEPT phải nằm **trước** dòng đó, vì iptables xét từ trên xuống và dừng ở
luật khớp đầu tiên. Thường nó là dòng 6, nên hai lệnh dưới dùng số 6; nếu máy bạn hiện số khác
thì thay vào.

```bash
sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
```

Kiểm tra lại rằng hai dòng mới thật sự nằm trên dòng REJECT, rồi mới lưu:

```bash
sudo iptables -L INPUT --line-numbers -n
sudo netfilter-persistent save
```

Không lưu thì reboot là mất, và app sẽ "tự nhiên không vào được" sau lần khởi động lại đầu tiên.

---

## 3. Cài Docker

### 3.1 Cài gói

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git curl
```

`curl` thường có sẵn nhưng `scripts/deploy_remote.sh` ở §10 dựa vào nó để kiểm tra healthcheck,
nên cứ cài cho chắc.

`sqlite3` không cần cài trên máy chủ — nó nằm sẵn trong ảnh Docker và script backup chạy bên
trong container.

### 3.2 Chạy docker không cần sudo

```bash
sudo usermod -aG docker $USER
```

Đăng xuất rồi đăng nhập lại SSH (`exit`, rồi `ssh` vào lại). Đây là cách chắc chắn nhất —
`newgrp docker` chỉ đổi group cho shell hiện tại, còn cron (§11) và phiên SSH mà GitHub Actions
mở ra (§10) đều không thừa hưởng nó.

Kiểm tra:

```bash
docker run --rm hello-world
```

Ra "Hello from Docker!" là xong. Còn báo `permission denied ... docker.sock` nghĩa là bạn chưa
đăng nhập lại.

### 3.3 Swap — chỉ khi máy có 1 GB RAM (AMD micro)

Ảnh Docker được build từ nguồn cho `lxml`/`selectolax`, việc này ngốn RAM. Trên máy 1 GB,
build hay chết giữa chừng với `Killed` hoặc `gcc: fatal error: Killed signal terminated`. Cấp
2 GB swap trước cho đỡ mất công:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h        # cột Swap phải hiện 2.0Gi
```

Dòng `/etc/fstab` là để swap còn sau khi reboot.

Máy Ampere A1 (6 GB RAM trở lên) bỏ qua bước này.

---

## 4. Lấy mã nguồn và cấu hình

**Clone đúng vào `~/vietreader`** — script tự động deploy ở §10 mặc định tìm app ở đó:

```bash
cd ~
git clone <dia-chi-repo-cua-ban> vietreader
cd ~/vietreader/vietreader
pwd        # phải in ra: /home/ubuntu/vietreader/vietreader
```

> Không nhầm: `~/vietreader` là repo, còn `~/vietreader/vietreader` là thư mục con chứa
> `Dockerfile` và `docker-compose.yml`. Đường dẫn lặp lại hai lần là đúng, vì repo để app trong
> một thư mục con. Muốn đặt chỗ khác thì được, chỉ cần thêm
> `export VIETREADER_DIR=/duong/dan/that` vào `~/.bashrc` trên máy chủ để §10 tìm ra.

```bash
cp config/settings.example.env .env
nano .env
```

Tối thiểu cần xem lại hai dòng:

```ini
VIETREADER_READER_NAME=Ngân Giang     # tên hiện trong lời chào và các màn hình trống
VIETREADER_LLM_API_KEY=               # theo quyết định ở §0.1
```

Vài điều về `.env`:

- **Không cần đặt `VIETREADER_DATABASE_URL`.** `docker-compose.yml` ghi đè nó thành
  `sqlite:////data/vietreader.db` để database luôn nằm trong volume, dù `.env` có ghi gì.
  Dòng `sqlite:///./vietreader.db` trong file mẫu là cho chạy local, cứ để nguyên.
- `.env` đã nằm trong `.gitignore` — nó ở lại máy chủ, không bao giờ bị commit lên repo.
- Các dòng còn lại (model, temperature, batch size, user agent, log level) có mặc định hợp lý,
  chưa cần đụng tới.

---

## 5. Build và chạy

```bash
docker compose up -d --build
```

Lần đầu mất **10–25 phút trên ARM** — chủ yếu là compile `lxml` và `selectolax`, vốn không có
wheel dựng sẵn cho kiến trúc đó. (Để so sánh: trên x86 đo được 3 phút 40.) Cứ để chạy; lần sau
nhanh hơn hẳn nhờ cache — xem §10.5.

Xem tiến trình khởi động:

```bash
docker compose logs -f
```

Chờ tới khi thấy `Uvicorn running on http://0.0.0.0:8000`, rồi `Ctrl+C` để thoát khỏi log
(app vẫn chạy — `Ctrl+C` chỉ ngắt việc xem log, không tắt container).

Trước dòng đó bạn sẽ thấy alembic chạy migration. Container luôn `alembic upgrade head` trước
khi lên server, nên lần đầu là có sẵn đủ bảng, không phải làm gì thêm.

---

## 6. Kiểm tra

Chạy đủ ba lệnh này trước khi đi tiếp — mỗi lệnh loại trừ một tầng khác nhau:

```bash
# 1. App sống trong container
docker compose exec app python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read())"

# 2. Cổng đã publish ra máy chủ
curl http://localhost:8000/api/health          # {"status":"ok"}

# 3. Container ở trạng thái healthy
docker compose ps
```

Ở lệnh 3, cột `STATUS` phải là `Up ... (healthy)`. Healthcheck chạy mỗi 60 giây nên ngay sau
khi khởi động nó có thể còn ghi `(health: starting)` — chờ một phút rồi xem lại.

**Chưa vào được từ trình duyệt ở nhà là đúng, chưa phải lỗi.** `docker-compose.yml` cố ý chỉ mở
cổng 8000 ra `127.0.0.1` — app không có lớp đăng nhập nên không được phép phơi thẳng ra Internet.
Cửa vào từ ngoài sẽ là Caddy ở §8. Muốn xem trước bằng trình duyệt thì mở một đường hầm SSH
**trên máy bạn**:

```bash
ssh -i duong-dan-toi-key -L 8000:127.0.0.1:8000 ubuntu@<ip>
```

Giữ cửa sổ đó mở rồi vào `http://localhost:8000` — trang chủ VietReader hiện ra với lời chào
theo tên bạn đặt ở `.env`.

---

## 7. Nạp từ điển mẫu

65 entry tiên hiệp/kiếm hiệp (35 REPLACE, 15 KEEP, 15 ASK) để từ điển không rỗng lúc đọc
chương đầu tiên:

```bash
docker compose exec app python scripts/seed_dictionary.py
```

Kết quả: `Seeded 65 entries into sqlite:////data/vietreader.db (0 already existed).`

Chạy lại nhiều lần vô hại — script bỏ qua entry đã tồn tại, không tạo trùng, không ghi đè.
Sau này bạn tự thêm từ khi đọc, qua popup bôi đen văn bản hoặc trang `/dictionary`.

---

## 8. HTTPS

Nên có, để nội dung bạn đọc không đi qua mạng dạng thô. Caddy tự xin chứng chỉ Let's Encrypt và
tự gia hạn, không cần cron, không cần certbot.

**Điều kiện:** tên miền ở §0.2 đã trỏ về IP máy. Kiểm tra trước, đừng đoán:

```bash
dig +short doc.ten-mien-cua-ban.com     # phải in ra đúng IP máy chủ
```

DNS chưa kịp lan thì Caddy xin chứng chỉ sẽ thất bại. Đợi vài phút rồi thử lại.

### 8.1 Cài Caddy

Caddy không có trong kho mặc định của Ubuntu, phải thêm kho chính thức của họ:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

### 8.2 Cấu hình

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
doc.ten-mien-cua-ban.com {
    reverse_proxy 127.0.0.1:8000
}
EOF

sudo systemctl restart caddy
sudo systemctl status caddy --no-pager
```

Nhớ thay `doc.ten-mien-cua-ban.com` bằng tên miền thật — đây là dòng quyết định Caddy xin
chứng chỉ cho tên nào.

Mở `https://doc.ten-mien-cua-ban.com` từ trình duyệt. Lần đầu có thể mất 10–30 giây trong lúc
Caddy xin chứng chỉ. Lỗi thì xem `sudo journalctl -u caddy -n 50 --no-pager`.

---

## 9. Chắn truy cập (nên làm nếu mở ra Internet)

Chỉ cần thiết khi bạn chọn **Cách B** ở §0.1 (có đặt `VIETREADER_LLM_API_KEY`) hoặc đơn giản là
không muốn ai lạ đọc thư viện và ghi chú của mình. Không phải sửa một dòng code nào.

Việc chính là §9.1. §9.2 chỉ là xác nhận lại rằng cổng 8000 vẫn kín — mật khẩu ở Caddy chẳng
có nghĩa gì nếu người ta gõ thẳng `http://<ip>:8000` vào được, vòng qua Caddy.

### 9.1 Basic auth ở Caddy

Tạo hash mật khẩu (thay `mat-khau-cua-ban`):

```bash
caddy hash-password --plaintext 'mat-khau-cua-ban'
```

Chép chuỗi `$2a$14$...` in ra, dán vào Caddyfile:

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
doc.ten-mien-cua-ban.com {
    basic_auth {
        ngangiang $2a$14$dan-hash-vao-day
    }
    reverse_proxy 127.0.0.1:8000
}
EOF

sudo systemctl restart caddy
```

> Caddy dưới 2.8 dùng tên directive `basicauth` (không gạch dưới). `caddy version` để biết bạn
> đang ở bản nào; báo lỗi `unrecognized directive` thì đổi sang dạng còn lại.

### 9.2 Kiểm chứng cổng 8000 đã kín

Việc này `docker-compose.yml` làm sẵn rồi (`ports: "127.0.0.1:8000:8000"`), nhưng vẫn nên xác
nhận bằng mắt vì đây là chỗ mà sai thì basic auth ở §9.1 trở thành vô nghĩa — ai cũng vào thẳng
`http://<ip>:8000` vòng qua Caddy được.

```bash
docker compose ps        # cột PORTS phải là 127.0.0.1:8000->8000/tcp, KHÔNG phải 0.0.0.0:8000->8000/tcp
```

Rồi **trên máy bạn**, thử vào thẳng `http://<ip>:8000` — phải treo hoặc bị từ chối. Vào được thì
kiểm tra lại xem có ai lỡ tạo `docker-compose.override.yml` mở cổng ra không, và Security List
ở §2.1 có luật 8000 thừa không.

---

## 10. Tự động deploy khi push main

Từ đây trở đi bạn không cần SSH vào máy chủ để cập nhật code nữa: merge vào `main` → GitHub chạy
test → test xanh thì tự SSH vào máy chủ, kéo code mới, dựng lại và kiểm tra app sống.

Ba file lo việc này, đã có sẵn trong repo:

| File | Việc |
|---|---|
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | Chạy lint + typecheck + test trên mọi push |
| [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) | Chỉ khi CI **xanh** và nhánh là `main` → SSH vào máy chủ |
| [`scripts/deploy_remote.sh`](scripts/deploy_remote.sh) | Phần chạy trên máy chủ: sao lưu → kéo code → dựng lại → chờ healthcheck |

> **Deploy không chạy nếu test đỏ.** `deploy.yml` móc vào sự kiện `workflow_run` của CI và chỉ
> chạy khi `conclusion == 'success'`. Code hỏng test sẽ dừng ở GitHub, không lên tới máy chủ.

### 10.1 Tạo khoá SSH riêng cho việc deploy

Đừng dùng lại khoá cá nhân bạn đang dùng để SSH. Khoá này sẽ nằm trong GitHub Secrets, nên nó
cần là một khoá riêng, chỉ làm đúng việc deploy, thu hồi được mà không ảnh hưởng gì khác.

**Trên máy bạn:**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/vietreader_deploy -N "" -C "github-actions-deploy"
```

Ra hai file: `vietreader_deploy` (khoá riêng) và `vietreader_deploy.pub` (khoá công khai).

Nạp khoá công khai lên máy chủ:

```bash
ssh-copy-id -i ~/.ssh/vietreader_deploy.pub ubuntu@<ip>
```

Không có `ssh-copy-id` thì làm tay: mở `~/.ssh/vietreader_deploy.pub`, chép nội dung, rồi trên
máy chủ dán thêm một dòng vào `~/.ssh/authorized_keys`.

Thử ngay, phải vào được mà không hỏi mật khẩu:

```bash
ssh -i ~/.ssh/vietreader_deploy ubuntu@<ip> "echo khoa-deploy-chay-duoc"
```

### 10.2 Lấy known_hosts

Đây là bước ghim danh tính máy chủ. Không có nó thì phải tắt kiểm tra host, và bất kỳ ai chiếm
được DNS hoặc IP đều nhận được khoá deploy của bạn.

**Trên máy bạn:**

```bash
ssh-keyscan -H <ip> 2>/dev/null
```

Chép **toàn bộ** output (nhiều dòng, mỗi dòng một loại khoá).

### 10.3 Khai bốn secret trên GitHub

Repo trên GitHub → **Settings → Secrets and variables → Actions → New repository secret.**
Tạo đúng bốn cái, tên phải khớp chính xác:

| Tên secret | Giá trị |
|---|---|
| `DEPLOY_SSH_KEY` | Toàn bộ nội dung file `~/.ssh/vietreader_deploy` (khoá **riêng**) |
| `DEPLOY_KNOWN_HOSTS` | Output của `ssh-keyscan` ở §10.2 |
| `DEPLOY_HOST` | IP public của máy chủ |
| `DEPLOY_USER` | `ubuntu` |

Lấy nội dung khoá riêng để chép:

```bash
cat ~/.ssh/vietreader_deploy
```

Dán **cả** dòng `-----BEGIN OPENSSH PRIVATE KEY-----` và `-----END OPENSSH PRIVATE KEY-----`,
kèm dòng trắng ở cuối nếu có. Thiếu một dòng là GitHub Actions báo `invalid format`.

> Secret chỉ ghi vào được, không đọc lại được. Dán nhầm thì tạo lại secret đó, không sửa được
> tại chỗ.

### 10.4 Chạy thử

Đẩy các file này lên GitHub trước (nếu chưa):

```bash
git add .github/workflows/ vietreader/scripts/deploy_remote.sh
git commit -m "CI/CD: tu dong deploy khi push main"
git push origin main
```

Vào tab **Actions** trên GitHub. Bạn sẽ thấy **CI** chạy trước; xong và xanh thì **Deploy** tự
khởi động sau đó. Mở job Deploy ra xem log — nó in ra từng bước của `deploy_remote.sh`, kết thúc
bằng `==> Deploy xong: <mã commit>`.

Muốn deploy lại mà không sửa code: tab **Actions → Deploy → Run workflow**.

### 10.5 Vì sao deploy chỉ mất ~1 phút

`Dockerfile` chia làm hai bước: bước một cài dependency (chỉ dựng lại khi `pyproject.toml` đổi),
bước hai copy mã nguồn. Nhờ vậy sửa code không phải compile lại `lxml`/`selectolax` — thứ ngốn
10–25 phút ở lần build đầu.

Đo thật trên x86: build đầy đủ **3 phút 40**, còn build lại sau khi chỉ sửa một file trong
`src/` là **2,7 giây**. Trên ARM con số tuyệt đối lớn hơn nhưng tỉ lệ tương tự.

Hệ quả cần nhớ: **lần deploy nào có sửa `pyproject.toml` sẽ chậm như lần đầu.** Đó là bình
thường, đừng tưởng treo.

### 10.6 Những gì `deploy_remote.sh` bảo vệ cho bạn

- **Sao lưu trước khi đụng vào gì.** Nếu bản mới làm hỏng dữ liệu, bạn có bản ngay trước đó.
- **`git reset --hard origin/main`** — máy chủ luôn khớp đúng `origin/main`, không tích luỹ
  thay đổi lạ qua thời gian. File chưa track thì không bị đụng, nên `.env` của bạn vẫn nguyên.
- **Chờ healthcheck tới 200 giây.** App không lên thì job đỏ và log 80 dòng cuối được in ra
  ngay trong GitHub Actions — bạn biết hỏng mà không phải SSH vào tìm.
- **`docker image prune`** sau mỗi lần thành công, để ảnh cũ không làm đầy đĩa máy nhỏ.

---

## 11. Sao lưu và khôi phục

Database này là **toàn bộ** thư viện, vị trí đọc, từ điển và ghi chú của bạn. Mất là mất hết,
không dựng lại được từ đâu cả.

### 11.1 Sao lưu thủ công

```bash
docker compose exec app ./scripts/backup_db.sh
```

In ra `da sao luu: /data/backups/vietreader-20260814-030000.db.gz`.

Script dùng lệnh `.backup` của SQLite chứ không copy file — copy trong lúc app đang ghi có thể
ra bản hỏng, vì WAL còn dữ liệu chưa dồn vào file chính. Nó cũng tự xoá bản cũ, giữ 14 bản gần
nhất (đổi bằng biến `KEEP`).

### 11.2 Đặt lịch hằng ngày

```bash
crontab -e
```

Thêm dòng sau, dùng nguyên nếu bạn clone đúng chỗ ở §4:

```cron
0 3 * * * cd /home/ubuntu/vietreader/vietreader && /usr/bin/docker compose exec -T app ./scripts/backup_db.sh >> /home/ubuntu/backup.log 2>&1
```

Ba chi tiết dễ sai:

- **`-T`** — bắt buộc. Không có nó, `exec` đòi TTY, mà cron không có TTY, và job fail mỗi đêm
  trong im lặng.
- **`/usr/bin/docker`** — cron chạy với `PATH` tối giản, gọi trần `docker` có thể không thấy.
- **`>> backup.log`** — để còn chỗ mà xem khi nghi ngờ. Vài ngày sau kiểm tra:
  `cat ~/backup.log` và `docker compose exec app ls -lh /data/backups`.

### 11.3 Chép backup về máy bạn

Backup nằm cùng máy chủ thì máy chết là mất cả hai. Chép định kỳ về máy bạn.

Backup nằm trong Docker volume, mà thư mục volume trên máy chủ (`/var/lib/docker/volumes/...`)
chỉ root đọc được — `scp` thẳng vào đó sẽ báo permission denied. Đi vòng qua `docker compose cp`:

```bash
# trên máy chủ — lấy backup ra thư mục home
cd ~/vietreader/vietreader
docker compose cp app:/data/backups ~/backups
```

```bash
# trên máy bạn
scp -i duong-dan-toi-key -r ubuntu@<ip>:~/backups ./vietreader-backups
```

### 11.4 Khôi phục

Chưa thử khôi phục thì chưa gọi là có backup. Nên chạy thử một lần cho biết đường.

```bash
cd ~/vietreader/vietreader

# 1. Dừng app. Volume dữ liệu KHÔNG bị xoá — `down` không đụng tới volume có tên.
docker compose down

# 2. Giải nén bản muốn khôi phục ra thư mục hiện tại
docker compose cp app:/data/backups ~/backups 2>/dev/null || true
gunzip -c ~/backups/vietreader-20260814-030000.db.gz > ~/vietreader-restore.db

# 3. Tìm tên volume thật
docker volume ls | grep vietreader-data       # ví dụ: vietreader_vietreader-data

# 4. Ghi đè database trong volume
docker run --rm \
  -v vietreader_vietreader-data:/data \
  -v "$HOME:/in" \
  alpine sh -c '
    rm -f /data/vietreader.db-wal /data/vietreader.db-shm &&
    cp /in/vietreader-restore.db /data/vietreader.db &&
    chown 10001:10001 /data/vietreader.db'

# 5. Bật lại
docker compose up -d
curl http://localhost:8000/api/health
```

Hai dòng trong bước 4 quan trọng hơn vẻ ngoài của chúng:

- **Xoá `-wal` và `-shm`.** Đó là WAL của database *cũ*. Để lại thì SQLite sẽ áp WAL cũ lên
  file vừa khôi phục và bạn được một database hỏng.
- **`chown 10001:10001`.** Container chạy bằng user `vietreader` (uid 10001). File do `docker run`
  tạo thuộc về root, app sẽ mở được để đọc nhưng không ghi được — biểu hiện là mọi thao tác lưu
  đều lỗi `attempt to write a readonly database`.

Nếu tên volume ở bước 3 khác `vietreader_vietreader-data`, thay vào bước 4. Tên đó là
`<tên-thư-mục>_vietreader-data` nên nó phụ thuộc bạn clone repo ra thư mục tên gì.

---

## 12. Nâng cấp

Làm §10 rồi thì nâng cấp chỉ còn:

```bash
git push origin main
```

GitHub chạy test, test xanh thì tự deploy. Xem tiến trình ở tab **Actions**. Không phải SSH vào
máy chủ, không phải nhớ lệnh nào.

**Deploy tay** khi cần — GitHub hỏng, hoặc bạn muốn thử một nhánh chưa merge:

```bash
# trên máy bạn, từ gốc repo
ssh ubuntu@<ip> 'bash -s' < vietreader/scripts/deploy_remote.sh
```

Đây đúng là kịch bản mà GitHub Actions chạy, nên kết quả giống hệt.

### Quay về bản cũ

Cách sạch nhất là revert trên git rồi để CI/CD làm phần còn lại — máy chủ vẫn khớp `origin/main`,
không lệch trạng thái:

```bash
git revert <commit-hong>
git push origin main
```

Cần nhanh hơn thì vào thẳng máy chủ:

```bash
cd ~/vietreader/vietreader
git log --oneline -5
git checkout <commit-cu>
docker compose up -d --build
```

Nhưng nhớ rằng lần deploy tự động kế tiếp sẽ `git reset --hard origin/main` và xoá mất trạng
thái tạm này — nên nó chỉ là băng dán, phải revert trên git sau đó.

Lưu ý chung: quay lại code cũ **không** tự quay lại schema database. Nếu bản mới có migration,
bạn cần khôi phục database từ backup ở §11.4. `deploy_remote.sh` luôn sao lưu ngay trước khi
đổi code, nên bản bạn cần nằm sẵn ở đó.

---

## 13. Vận hành hằng ngày

```bash
cd ~/vietreader/vietreader

docker compose logs -f              # xem log trực tiếp
docker compose logs --tail 100      # 100 dòng cuối
docker compose ps                   # trạng thái + healthcheck
docker compose restart              # khởi động lại app
docker compose down                 # tắt hẳn (dữ liệu vẫn còn trong volume)
docker compose up -d                # bật lại
```

App có `restart: unless-stopped`, nên nó tự lên lại sau khi reboot máy chủ hoặc sau khi crash.
Không cần systemd unit riêng.

**Dọn đĩa** — mỗi lần `--build` để lại ảnh cũ, vài lần nâng cấp là đầy đĩa máy nhỏ:

```bash
df -h /                             # xem còn bao nhiêu
docker image prune -f               # xoá ảnh không còn ai dùng
docker system prune -f              # mạnh tay hơn (KHÔNG đụng volume có tên)
```

Cả hai lệnh prune trên đều an toàn với dữ liệu. Chỉ có `docker system prune --volumes` là xoá
volume — **đừng bao giờ chạy** kèm cờ đó trên máy này.

---

## 14. Khắc phục sự cố

**Build chết với `Killed` hoặc `gcc: fatal error`** — hết RAM lúc compile. Làm §3.3 (swap) rồi
build lại.

**`env file /home/ubuntu/.../.env not found` (thoát với mã 14)** — chưa tạo `.env`. Mọi lệnh
`docker compose` đều chết ngay ở bước đọc cấu hình, kể cả `docker compose ps`. Làm §4:
`cp config/settings.example.env .env`. Compose cố ý báo lỗi thay vì chạy với cấu hình rỗng.

**`ModuleNotFoundError: No module named 'vietreader.llm.prompts'`, hoặc app chết lúc mount
static/templates** — ảnh được build từ một `Dockerfile` cũ có `pip install .`. Cách đóng gói của
dự án không đưa `llm/prompts/`, `web/templates/` và `web/static/` vào wheel, nên bản cài thiếu
file. `Dockerfile` hiện tại chạy thẳng từ cây mã nguồn qua `PYTHONPATH` nên không dính; nếu gặp
lỗi này thì bạn đang ở bản cũ, `git pull` rồi build lại.

**Trình duyệt ở nhà không vào được qua tên miền, nhưng `curl http://localhost:8000` trên máy chủ
thì được** — firewall hoặc Caddy. Rà lại §2 (hay gặp nhất là thiếu tầng iptables ở §2.2, hoặc
quên `netfilter-persistent save`), rồi tới §8. Lưu ý `http://<ip>:8000` **cố ý** không vào được
từ ngoài, đó không phải lỗi — xem §2.1.

### Nhóm lỗi CI/CD (§10)

**Tab Actions không thấy workflow nào** — file workflow phải nằm ở `.github/workflows/` tại
**gốc repo**, không phải trong thư mục con `vietreader/`. GitHub chỉ đọc ở gốc.

**Deploy không tự chạy sau khi CI xanh** — ba nguyên nhân theo thứ tự hay gặp: (1) push vào
nhánh khác `main`, (2) tên workflow trong `deploy.yml` (`workflows: ["CI"]`) không khớp đúng
dòng `name:` của `ci.yml`, (3) CI thật ra đỏ — mở tab Actions xem lại.

**`Permission denied (publickey)`** — khoá công khai chưa nằm trong `~/.ssh/authorized_keys`
trên máy chủ, hoặc secret `DEPLOY_SSH_KEY` dán thiếu dòng BEGIN/END. Thử tay để tách bạch:
`ssh -i ~/.ssh/vietreader_deploy ubuntu@<ip> "echo ok"`.

**`Host key verification failed`** — `DEPLOY_KNOWN_HOSTS` sai hoặc thiếu. Chạy lại
`ssh-keyscan -H <ip>` và dán lại **toàn bộ** output. IP máy chủ đổi thì cũng phải cập nhật lại
secret này.

**`docker: permission denied ... docker.sock` trong log Actions** — user `ubuntu` chưa vào nhóm
docker, hoặc đã thêm mà chưa mở phiên mới. Làm lại §3.2. Phiên SSH của Actions là phiên mới nên
nó phải thấy nhóm docker; kiểm tra bằng `ssh ubuntu@<ip> "id -nG"`, phải có chữ `docker`.

**`cd: no such file or directory` trong log Actions** — repo không nằm ở `~/vietreader`. Hoặc
clone lại đúng chỗ (§4), hoặc thêm `export VIETREADER_DIR=/duong/dan/that` vào `~/.bashrc` trên
máy chủ.

**Deploy đỏ ở bước chờ healthcheck** — 80 dòng log cuối đã được in ngay trong job Actions, đọc
ở đó. App vẫn đang chạy bản cũ hay không thì `docker compose ps` trên máy chủ sẽ nói.

**`docker compose ps` hiện `unhealthy` hoặc container restart liên tục** — xem log:
`docker compose logs --tail 100`. Hay gặp nhất là migration fail; khi đó dòng lỗi alembic nằm
ngay đầu log của lần khởi động cuối.

**Trang chủ mở được nhưng lưu gì cũng lỗi** — `attempt to write a readonly database` trong log.
Quyền file trong volume sai, thường sau một lần khôi phục thủ công thiếu bước `chown`. Sửa:

```bash
docker compose down
docker run --rm -v vietreader_vietreader-data:/data alpine chown -R 10001:10001 /data
docker compose up -d
```

**Đọc chương nào cũng thấy từ mơ hồ giữ nguyên, log có WARN về ASK** — không có
`VIETREADER_LLM_API_KEY`. Đúng như thiết kế nếu bạn chọn Cách A ở §0.1. Muốn bật thì thêm khoá
vào `.env`, chạy §9 trước, rồi `docker compose up -d`.

**Caddy không xin được chứng chỉ** — `sudo journalctl -u caddy -n 50 --no-pager`. Ba nguyên nhân
thường gặp: DNS chưa trỏ đúng (`dig +short <tên-miền>`), cổng 80 chưa mở ở §2.1 (Let's Encrypt
cần vào được cổng 80 để xác minh), hoặc tên miền trong Caddyfile gõ sai.

**Backup không thấy chạy** — `cat ~/backup.log`. Không có file nào nghĩa là cron chưa từng chạy
lệnh (sai đường dẫn trong crontab); có log mà báo lỗi `the input device is not a TTY` nghĩa là
thiếu cờ `-T` (§11.2).

**Đĩa đầy** — `df -h /` rồi làm phần dọn đĩa ở §13.

---

## 15. Ghi chú thiết kế

**Vì sao không dùng PaaS, khi yêu cầu là miễn phí.** Điểm chết chung của các free tier là **đĩa
bền**, thứ app này bắt buộc phải có vì dữ liệu nằm trong một file SQLite.

| | Vướng ở đâu |
|---|---|
| Render free | Không có persistent disk. Dữ liệu mất sạch mỗi lần restart. Còn ngủ sau 15 phút, đánh thức mất ~1 phút. |
| Railway | Có volume và rất dễ dùng, nhưng $5/tháng — credit dùng thử hết là dừng. Xem [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md). |
| Fly.io | Từng có free allowance, nay đã bỏ với tài khoản mới. |
| Vercel | Serverless: không có tiến trình thường trú, không có đĩa bền. Phải đổi SQLite sang Postgres, và việc fetch chương (có retry + delay) cộng gọi LLM dễ chạm trần thời gian. |
| Cloud Run | Co về 0; muốn luôn chạy phải bật min-instance và cái đó tính tiền. Đĩa cũng phải đi thuê ngoài. |

Oracle Always Free là chỗ duy nhất cho **máy thật, đĩa thật, chạy 24/7, miễn phí không hết hạn**.
Cái giá là phải tự dựng — và §10 chính là để trả cái giá đó một lần rồi thôi: sau khi CI/CD chạy,
việc cập nhật app nhẹ ngang một PaaS.

**Vì sao deploy bằng SSH chứ không phải registry + webhook.** Đẩy ảnh lên ghcr.io rồi cho máy
chủ kéo về thì "đúng bài" hơn, nhưng thêm một registry phải quản, thêm quota, và build ARM trên
runner của GitHub lại là chuyện khác nữa. Với một máy chủ và một người dùng, `ssh + docker compose
up --build` ít bộ phận chuyển động hơn hẳn, mà vẫn có đủ thứ cần: gác bằng test, sao lưu trước
khi đổi, kiểm tra healthcheck sau khi đổi, tự lùi lại được.

**Vì sao giữ SQLite.** Máy ảo có đĩa bền thật nên không cần dời DB. Giữ SQLite là không phải
thêm dependency, không phải viết lại migration, và toàn bộ test hiện có vẫn còn nguyên giá trị.
Với một người đọc thì SQLite thừa sức.

**Vì sao database nằm trong volume chứ không phải bind mount.** Volume tách hẳn khỏi vòng đời
container: `docker compose down`, `--build`, đổi ảnh — dữ liệu không suy suyển. Đổi lại là
đường dẫn thật khó với tới (§11.3), nên mọi thao tác dữ liệu trong tài liệu này đều đi qua
`docker compose exec` hoặc một container tạm.

**Vì sao ảnh chạy từ cây mã nguồn (`PYTHONPATH=/app/src`) thay vì `pip install .`.** Cấu hình
đóng gói của dự án dùng `[tool.setuptools.packages.find]`, vốn chỉ nhận thư mục có `__init__.py`.
`src/vietreader/llm/prompts/` và `src/vietreader/web/` đều không có, nên wheel dựng ra thiếu
`disambiguate.v1.txt`, thiếu toàn bộ `templates/` và `static/`. Thêm nữa `extraction/registry.py`
dò `config/sites` bằng `parents[3]`, mà trong layout `site-packages` đường dẫn đó trỏ ra ngoài
cây dự án. Ba thứ này cộng lại làm ảnh production chết ngay lúc import — chỉ bản dev sống được,
vì `pip install -e` giữ `__file__` trỏ về cây nguồn thật.

Chạy từ cây nguồn xoá cả ba vấn đề cùng lúc và làm production khớp đúng bản dev. Cái giá là
`pip install .` vẫn cho ra một package thiếu file — không ảnh hưởng gì tới việc deploy, nhưng
nếu sau này bạn muốn phát hành VietReader như một thư viện thì phải sửa `pyproject.toml` trước.

**Vì sao migration chạy trong `CMD` chứ không phải bước riêng.** Nâng cấp chỉ còn một lệnh, và
không có cửa sổ nào mà code mới chạy trên schema cũ. `migrations/env.py` đọc
`VIETREADER_DATABASE_URL` — cùng biến app dùng — nên alembic migrate đúng file mà app sẽ mở.
Trước đây env.py chỉ đọc `alembic.ini` và hai bên trỏ vào hai file khác nhau; lỗi đó im lặng và
rất khó đoán.

**Điều khoản free tier đổi thường xuyên** — nên kiểm tra lại trang giá của Oracle trước khi
dựa hẳn vào, vì "Always Free" chính là điểm mấu chốt của lựa chọn này.

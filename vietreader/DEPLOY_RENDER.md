# Đưa VietReader lên Render + Neon — miễn phí, không cần thẻ

Cách deploy **không cần thẻ tín dụng, không cần máy chủ riêng, không tốn tiền**. Cả Render lẫn
Neon đều cho đăng ký bằng tài khoản GitHub và không hỏi thẻ.

Có sẵn CI/CD: push vào `main` → GitHub chạy test → test xanh thì Render tự deploy. Không phải
khai SSH key hay secret nào cho việc deploy.

**Thời gian:** khoảng 30 phút.

---

## Mục lục

| | |
|---|---|
| [0. Đánh đổi phải biết trước](#0-đánh-đổi-phải-biết-trước) | Đọc trước khi bắt đầu |
| [1. Đẩy mã nguồn lên GitHub](#1-đẩy-mã-nguồn-lên-github) | |
| [2. Tạo database trên Neon](#2-tạo-database-trên-neon) | Miễn phí, không thẻ, không hết hạn |
| [3. Tạo service trên Render](#3-tạo-service-trên-render) | Đọc `render.yaml` sẵn trong repo |
| [4. Khai biến môi trường](#4-khai-biến-môi-trường) | Chỗ dễ mất dữ liệu nhất |
| [5. Kiểm tra](#5-kiểm-tra) | Gồm bài test dữ liệu có bền không |
| [6. Chắn truy cập](#6-chắn-truy-cập) | App không có lớp đăng nhập |
| [7. CI/CD](#7-cicd-push-main-là-tự-deploy) | Đã bật sẵn |
| [8. Đỡ phải chờ app ngủ dậy](#8-đỡ-phải-chờ-app-ngủ-dậy) | Đánh thức tự động |
| [9. Sao lưu](#9-sao-lưu) | Neon lo phần lớn |
| [10. Khắc phục sự cố](#10-khắc-phục-sự-cố) | |
| [11. Vì sao là Postgres chứ không SQLite](#11-vì-sao-là-postgres-chứ-không-sqlite) | |

---

## 0. Đánh đổi phải biết trước

Miễn phí thật, nhưng có ba cái giá:

**App ngủ sau 15 phút không ai dùng.** Mở lại phải chờ **khoảng một phút**. Đây là cơ chế của
gói free Render, không sửa code trong app mà tránh được. Nhưng **§8 cho bạn cách tự động đánh
thức nó trong khung giờ bạn hay đọc**, nên thực tế bạn sẽ hiếm khi phải chờ.

**Dữ liệu nằm ở Neon, giới hạn 0,5 GB.** Đủ cho hàng nghìn chương. Chạm trần thì database bị
tạm dừng cho tới chu kỳ sau — không mất dữ liệu, nhưng app sẽ lỗi cho tới lúc đó.

**Không có SSH và không chạy được lệnh một lần.** Nên việc nạp từ điển mẫu phải làm tự động lúc
khởi động (đã cấu hình sẵn, §4).

Nếu sau này bạn có một máy bật được 24/7, [DEPLOY.md](DEPLOY.md) cho bạn SQLite, không ngủ,
không cold start — đổi lại phải tự dựng.

---

## 1. Đẩy mã nguồn lên GitHub

Render deploy từ repo GitHub (private cũng được).

```bash
cd /duong-dan-toi/vietreader        # thư mục gốc repo
git push -u origin main
```

Chưa có repo trên GitHub thì tạo một cái rồi:

```bash
git remote add origin git@github.com:<ten-cua-ban>/vietreader.git
git push -u origin main
```

Repo cần có hai file này ở **gốc** (đã có sẵn): `render.yaml` và `.github/workflows/ci.yml`.

---

## 2. Tạo database trên Neon

1. Vào [neon.com](https://neon.com), **Sign up with GitHub**. Không hỏi thẻ.
2. **Create project** — đặt tên `vietreader`, chọn region gần bạn nhất
   (`Asia Pacific (Singapore)` nếu có).
3. Xong là Neon hiện ngay **Connection string**, dạng:

```
postgresql://vietreader_owner:npg_xxxxxxxx@ep-abc-123.ap-southeast-1.aws.neon.tech/vietreader?sslmode=require
```

**Chép nguyên chuỗi đó, giữ nguyên cả `?sslmode=require`.** Lát nữa dán vào Render.

> Không phải sửa gì cho khớp driver. Code đã tự chuẩn hoá `postgresql://` sang dạng driver mà
> dự án cài (`postgresql+psycopg://`) — xem `src/vietreader/db/base.py`. Đây là lỗi kinh điển
> khi deploy Postgres (`ModuleNotFoundError: psycopg2`) và nó đã được xử lý sẵn.

Gói free của Neon: **0,5 GB, không hết hạn, không cần thẻ.** Compute co về 0 sau 5 phút rảnh và
tự thức lại khi có truy vấn — app đã bật `pool_pre_ping` để không vỡ vì chuyện đó.

---

## 3. Tạo service trên Render

1. Vào [render.com](https://render.com), **Get Started with GitHub**. Không hỏi thẻ.
2. **New → Blueprint**.
3. Chọn repo `vietreader`.

Render đọc [`render.yaml`](../render.yaml) ở gốc repo và tự cấu hình mọi thứ: build từ
`Dockerfile`, `rootDir` là `vietreader`, healthcheck ở `/api/health`, và chỉ deploy khi CI xanh.
Bạn không phải điền tay mấy ô đó.

Nó sẽ dừng lại hỏi bạn hai biến — sang §4.

> **Nếu Render báo không dùng được Docker trên gói free:** đây là điều tôi không kiểm chứng
> được trước (tài liệu của Render không nói rõ). Gặp thì báo tôi, chuyển sang runtime Python
> gốc của Render là được, không cần đổi code — chỉ thay `render.yaml`.

---

## 4. Khai biến môi trường

Render hỏi hai biến vì `render.yaml` đánh dấu chúng `sync: false` (không lưu trong repo):

| Biến | Điền gì |
|---|---|
| `VIETREADER_DATABASE_URL` | Chuỗi Neon ở §2, dán nguyên |
| `VIETREADER_LLM_API_KEY` | **Đọc §6 trước.** Để trống cũng chạy được đủ mọi thứ trừ ASK |

> ### Đây là chỗ dễ mất dữ liệu nhất
>
> Nếu `VIETREADER_DATABASE_URL` để trống, app **không báo lỗi** — nó lặng lẽ quay về SQLite,
> ghi vào đĩa tạm của Render, và **mất sạch mọi thứ mỗi lần app ngủ dậy hoặc deploy lại**.
>
> Để chuyện này không âm thầm, app in ra dòng đầu tiên trong log lúc khởi động:
>
> ```
> ==> database: postgresql://***@ep-abc-123.ap-southeast-1.aws.neon.tech/vietreader
> ```
>
> Thấy `sqlite` hoặc `(không đặt)` ở đó là sai, sửa ngay trước khi dùng thật.

Hai biến còn lại `render.yaml` đã đặt sẵn, không phải làm gì:

- `VIETREADER_READER_NAME=Ngân Giang` — tên trong lời chào. Đổi ở tab Environment.
- `VIETREADER_SEED_ON_START=1` — nạp 65 entry từ điển mẫu lúc khởi động. Cần thiết vì Render
  free không cho chạy lệnh một lần. Chạy lại vô hại: script bỏ qua entry đã có, không tạo trùng.

Bấm **Apply**. Lần build đầu mất **10–20 phút** (compile `lxml`, `selectolax`). Xem log ở tab
**Logs**. Các lần sau nhanh hơn nhiều nhờ cache layer.

---

## 5. Kiểm tra

Render cấp địa chỉ dạng `https://vietreader-xxxx.onrender.com`, HTTPS tự động.

```bash
curl https://<ten-cua-ban>.onrender.com/api/health     # {"status":"ok"}
```

Mở trên trình duyệt — phải ra trang chủ với lời chào đúng tên bạn.

Trong log lúc khởi động phải thấy đủ bốn dòng này:

```
==> database: postgresql://***@ep-....neon.tech/vietreader
==> alembic upgrade head
==> seed từ điển mẫu (VIETREADER_SEED_ON_START=1)
==> uvicorn trên cổng 10000
```

### Bài test quan trọng nhất: dữ liệu có bền không

Đừng bỏ qua bước này — nó là toàn bộ lý do phải dùng Postgres.

1. Mở `/dictionary`, thêm một entry bất kỳ.
2. Trên Render bấm **Manual Deploy → Deploy latest commit** (hoặc chỉ cần đợi app ngủ rồi mở lại).
3. Mở lại `/dictionary`.

Entry còn nguyên là đúng. Entry biến mất nghĩa là app đang chạy trên SQlite — quay lại §4 xem
dòng `==> database:` trong log.

---

## 6. Chắn truy cập

**App không có lớp đăng nhập** — lựa chọn có chủ đích cho ứng dụng cá nhân, và không có biến
môi trường nào bật nó lên vì trong code không tồn tại tính năng đó.

Địa chỉ `*.onrender.com` nằm công khai trên Internet, và trên Render **không có reverse proxy
của bạn đứng trước** để gắn mật khẩu vào.

**Cách A — để trống `VIETREADER_LLM_API_KEY`** (khuyến nghị). Mất tính năng ASK: span mơ hồ giữ
nguyên thay vì hỏi LLM, có ghi WARN vào `run_log`. REPLACE, KEEP, extraction, reader, từ điển,
ghi chú vẫn chạy đủ. Đổi lại: người lạ mò ra địa chỉ cũng không tiêu được tiền API của bạn.

**Cách B — Cloudflare Access.** Cần tên miền riêng (Render cho gắn Custom Domain miễn phí).
Cloudflare Access miễn phí tới 50 người, chỉ cho email của bạn vào. Không phải sửa code.

**Cách C — thêm basic auth vào app**, khoảng 20 dòng middleware. **Bảo tôi nếu bạn muốn.**

---

## 7. CI/CD: push main là tự deploy

Đã bật sẵn, không phải cấu hình gì thêm.

```bash
git push origin main
```

Rồi chuyện xảy ra theo thứ tự:

1. GitHub Actions chạy [`ci.yml`](../.github/workflows/ci.yml): ruff + mypy + 185 test.
2. CI xanh → Render thấy checks pass và tự build, tự deploy.
3. CI đỏ → Render **không** deploy. Code hỏng test không lên được máy chủ.

Điều khiển hành vi này bằng `autoDeployTrigger` trong [`render.yaml`](../render.yaml):

| Giá trị | Nghĩa |
|---|---|
| `checksPass` | (đang dùng) chỉ deploy khi CI xanh |
| `commit` | deploy ngay khi push, không chờ test |
| `off` | tắt tự động, chỉ deploy tay |

Quay về bản cũ: Render → tab **Deploys** → tìm bản trước → **Redeploy**. Nhớ rằng quay lại code
cũ không tự quay lại schema database; có migration thì phải khôi phục cả DB theo §9.

> Repo còn một workflow `deploy.yml` — nó dành cho đường tự host ở [DEPLOY.md](DEPLOY.md) và
> **tự bỏ qua** khi không có secret `DEPLOY_HOST`. Dùng Render thì cứ kệ nó, job sẽ xanh và
> không làm gì.

---

## 8. Đỡ phải chờ app ngủ dậy

**Không có cách nào sửa code để app tự không ngủ.** Render quyết định dựa trên *lưu lượng đi
vào*; app tự gọi chính nó không tính. Tín hiệu phải đến từ bên ngoài.

Nhưng làm tự động được: cho một dịch vụ bên ngoài gõ cửa `/api/health` vài phút một lần trong
khung giờ bạn hay đọc. App không bao giờ ngủ trong khung đó, mở ra là dùng ngay.

### 8.1 Vì sao chỉ đánh thức buổi tối, không phải 24/7

Render cho **750 giờ/tháng cho cả workspace**. Làm phép tính:

| Cách | Giờ dùng/tháng (31 ngày) | Còn dư |
|---|---|---|
| Đánh thức 24/7 | 744 | **6 giờ** |
| Đánh thức 17–24h | 217 | 533 giờ |

Đánh thức 24/7 chỉ dư 6 giờ. Một lần deploy lại, một lần restart, hoặc bạn lỡ tạo thêm một
service free nào khác — là vượt, và Render **treo toàn bộ service free tới đầu tháng sau**.
Đánh thức theo giờ đọc vừa an toàn vừa đủ dùng.

### 8.2 Cách làm — chọn một

**Cách A — cron-job.org (khuyến nghị).** Miễn phí, không cần thẻ, giờ giấc chính xác.

1. Đăng ký ở [cron-job.org](https://cron-job.org).
2. **Create cronjob**, URL: `https://<ten-cua-ban>.onrender.com/api/health`
3. Schedule: mỗi **10 phút**, và giới hạn khung giờ 17:00–23:59 (nhớ đặt timezone
   `Asia/Ho_Chi_Minh` trong phần cài đặt tài khoản).

**Cách B — GitHub Actions**, dùng [`keepalive.yml`](../.github/workflows/keepalive.yml) đã có
sẵn trong repo. Không phải đăng ký thêm dịch vụ nào. Khai một secret:

| Secret | Giá trị |
|---|---|
| `KEEPALIVE_URL` | `https://<ten-cua-ban>.onrender.com` (không có `/` ở cuối) |

Chưa khai thì workflow tự bỏ qua, không báo đỏ.

> **Hai nhược điểm của Cách B, cân nhắc trước khi chọn:**
>
> - **Cron của GitHub hay trễ.** Đây là hạn mức chia sẻ miễn phí, lịch chạy có thể chậm 5–15
>   phút so với giờ hẹn. Ping đặt 10 phút mà trễ thành 20 phút thì app đã kịp ngủ. Nó vẫn đỡ
>   hơn không có gì, nhưng không chắc chắn bằng Cách A.
> - **Repo private tốn phút Actions.** GitHub tính tròn lên 1 phút mỗi lần chạy dù chỉ tốn 5
>   giây. Ping 10 phút/lần trong 7 giờ mỗi ngày = **1.302 phút/tháng**, trong khi repo private
>   chỉ có 2.000 phút — cộng thêm CI là gần hết. Repo public thì không giới hạn, dùng thoải mái.

### 8.3 Còn lại thì cold start nhanh cỡ nào

Ngoài khung giờ đánh thức, app vẫn ngủ và lần mở đầu vẫn chờ. Phần chờ đó gồm Render khởi động
container, Python nạp `lxml`/`trafilatura`, rồi `alembic upgrade head`.

Việc nạp từ điển thì đã được xử lý: `seed_dictionary.py` đếm một câu rồi thoát ngay nếu từ điển
đã có dữ liệu, thay vì thử insert 65 entry — tức 65 lượt đi về tới Neon qua mạng — ở **mỗi** lần
ngủ dậy.

---

## 9. Sao lưu

Database này là toàn bộ thư viện, vị trí đọc, từ điển và ghi chú của bạn.

**Neon có sẵn khôi phục theo thời điểm.** Gói free giữ lịch sử 24 giờ: vào project trên Neon →
**Restore**, chọn mốc thời gian. Cứu được các sai sót vừa xảy ra (lỡ xoá nhầm, migration hỏng).

**24 giờ là ngắn**, nên thỉnh thoảng nên tự kéo một bản về máy. Cần `pg_dump` (cài kèm Postgres
client: `brew install libpq` trên macOS):

```bash
pg_dump "postgresql://...chuoi-neon-cua-ban..." -Fc -f vietreader-$(date +%Y%m%d).dump
```

Khôi phục từ bản đó:

```bash
pg_restore -d "postgresql://...chuoi-neon-cua-ban..." --clean --if-exists vietreader-20260814.dump
```

Kiểm tra bản vừa kéo trước khi yên tâm:

```bash
pg_restore -l vietreader-20260814.dump | grep -c TABLE     # phải ra một con số > 0
```

---

## 10. Khắc phục sự cố

**Mở app lần đầu trong ngày phải chờ ~1 phút** — đúng như thiết kế của gói free, app ngủ sau 15
phút. Không phải lỗi. Xem §0.

**`ModuleNotFoundError: No module named 'psycopg2'`** — không nên gặp vì code đã tự chuẩn hoá
URL. Nếu vẫn gặp, kiểm tra `VIETREADER_DATABASE_URL` có bị dán nhầm thành dạng lạ không
(`postgresql+psycopg2://` chẳng hạn). Dạng đúng là dán nguyên chuỗi Neon cho.

**Dữ liệu biến mất sau mỗi lần deploy** — app đang chạy trên SQLite. Xem dòng `==> database:`
đầu log, rồi sửa `VIETREADER_DATABASE_URL` theo §4.

**Log có lỗi kết nối ở request đầu tiên sau lúc rảnh** — Neon co compute về 0 sau 5 phút. App
đã bật `pool_pre_ping` để xử lý; còn gặp thì báo tôi, có thể phải tăng timeout.

**Build fail vì hết RAM (`Killed`, `gcc: fatal error`)** — `lxml`/`selectolax` compile nặng. Nếu
builder của Render không kham nổi, báo tôi để chuyển sang cài từ wheel dựng sẵn.

**Từ điển rỗng** — thiếu `VIETREADER_SEED_ON_START=1`, hoặc log seed báo lỗi. Xem log tìm dòng
`==> seed từ điển mẫu`.

**CI xanh nhưng Render không deploy** — kiểm tra `autoDeployTrigger` trong `render.yaml` (§7),
và trên Render xem repo đã nối đúng nhánh `main` chưa.

**Neon báo hết dung lượng** — 0,5 GB đầy. Chủ yếu do bảng `chapter_cache` (lưu văn bản chương)
và `llm_cache`. Xoá bớt chương cũ trong `/library` là giải phóng được.

---

## 11. Vì sao là Postgres chứ không SQLite

Không phải vì SQLite yếu — với một người đọc thì SQLite thừa sức, và bản tự host ở
[DEPLOY.md](DEPLOY.md) vẫn dùng SQLite.

Lý do là **Render free có hệ thống file tạm**: mọi file app ghi ra đều mất mỗi lần service
redeploy, restart, hoặc ngủ dậy. Đĩa bền là tính năng trả phí. SQLite là một file, nên trên nền
tảng đó nó không sống được.

Đổi lại, việc chuyển sang Postgres hoá ra rất nhỏ, vì dự án vốn đã viết bằng SQLAlchemy/Alembic
thuần, không có SQL riêng cho dialect nào:

- Mọi giá trị mặc định của cột đều tính ở phía Python (`default=`), không dùng `server_default=`
  với SQL riêng của SQLite.
- `sa.JSON()` chạy trên cả hai.
- `batch_alter_table` trong migration `47f8` là để lách hạn chế của SQLite; trên Postgres
  Alembic tự chuyển thành `ALTER TABLE` thường.

Thay đổi thực tế chỉ gồm: tách `connect_args={"check_same_thread": False}` (chỉ SQLite hiểu)
sang nhánh riêng, thêm driver `psycopg`, bật `pool_pre_ping` cho Neon, và chuẩn hoá URL. Toàn bộ
model, repository, route, template giữ nguyên; 185 test vẫn chạy trên SQLite như cũ.

Nghĩa là bạn **đổi qua lại được**: cùng mã nguồn này chạy trên Render+Postgres hay trên máy ảo
với SQLite, chỉ khác một biến môi trường.

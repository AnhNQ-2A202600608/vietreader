# Đưa VietReader lên Railway (phương án trả phí)

> **Cách này tốn khoảng $5/tháng.** Muốn miễn phí hoàn toàn thì dùng
> [DEPLOY.md](DEPLOY.md) — Oracle Cloud Always Free, $0/tháng, và cũng có tự động deploy khi push
> `main` bằng GitHub Actions. Đổi lại là phải tự dựng máy chủ một lần (~60 phút).
>
> Railway **không có gói miễn phí dùng lâu dài**: gói dùng thử cho $5 credit một lần, hết là
> service dừng. Giữ tài liệu này cho trường hợp bạn thấy $5/tháng đáng để khỏi phải quản máy chủ.

Cách deploy **không cần đụng tới máy chủ**: không SSH, không iptables, không Caddy, không cron.
Nối GitHub một lần, từ đó `git push` là tự deploy.

**Không phải đổi tech gì cả.** Railway build thẳng từ `Dockerfile` có sẵn trong repo. SQLite giữ
nguyên, migration giữ nguyên, toàn bộ test giữ nguyên. Không sửa một dòng code nào — chỉ thêm
`railway.json` (4 dòng) và bấm vài nút trên giao diện.

Muốn tự host trên máy ảo thay vì dùng Railway thì xem [DEPLOY.md](DEPLOY.md) — cùng một app,
nhiều quyền kiểm soát hơn, đổi lại nhiều việc phải làm hơn.

**Thời gian:** khoảng 20 phút, phần lớn là ngồi chờ build.

---

## Mục lục

| | |
|---|---|
| [0. Chi phí và giới hạn](#0-chi-phí-và-giới-hạn) | Biết trước, không bất ngờ |
| [1. Đẩy mã nguồn lên GitHub](#1-đẩy-mã-nguồn-lên-github) | |
| [2. Tạo project trên Railway](#2-tạo-project-trên-railway) | |
| [3. Đặt Root Directory](#3-đặt-root-directory-bước-hay-quên-nhất) | Hay quên nhất |
| [4. Gắn volume cho database](#4-gắn-volume-cho-database) | + biến `RAILWAY_RUN_UID` |
| [5. Đặt biến môi trường](#5-đặt-biến-môi-trường) | |
| [6. Deploy và mở tên miền](#6-deploy-và-mở-tên-miền) | HTTPS tự động |
| [7. Kiểm tra](#7-kiểm-tra) | |
| [8. Nạp từ điển mẫu](#8-nạp-từ-điển-mẫu) | Qua `railway ssh` |
| [9. Chắn truy cập](#9-chắn-truy-cập-đọc-kỹ-mục-này) | Đọc kỹ — khác hẳn bản tự host |
| [10. Sao lưu](#10-sao-lưu) | Railway làm hộ |
| [11. Nâng cấp](#11-nâng-cấp) | `git push` |
| [12. Khắc phục sự cố](#12-khắc-phục-sự-cố) | |

---

## 0. Chi phí và giới hạn

Railway tính tiền theo mức dùng thật (CPU/RAM/đĩa), không theo gói cố định.

| | Trial / Free | Hobby |
|---|---|---|
| Giá | $0, kèm $5 credit dùng thử | $5/tháng, **đã gồm $5 credit** |
| Volume tối đa | 0,5 GB | 5 GB |
| Giá volume | $0,15/GB/tháng | $0,15/GB/tháng |

VietReader là app một người dùng, gần như luôn rảnh — mức tiêu thụ thực tế thường nằm gọn
trong $5 credit của gói Hobby, nên chi phí thường là **$5/tháng, không phát sinh thêm**.

Về dung lượng: DB lưu văn bản chương đã xử lý, mỗi chương cỡ vài chục KB. 0,5 GB của gói Free
đã chứa được hàng nghìn chương — bạn hoàn toàn có thể chạy thử miễn phí trước rồi mới nâng lên
Hobby khi thấy ưng.

> Giá và hạn mức có thể đổi. Số ở trên kiểm tra vào tháng 8/2026 — xem lại
> [trang giá của Railway](https://railway.com/pricing) trước khi dựa hẳn vào.

---

## 1. Đẩy mã nguồn lên GitHub

Railway deploy từ một repo GitHub, nên repo cần nằm trên GitHub (private cũng được).

```bash
cd /duong-dan-toi/vietreader           # thư mục gốc repo, không phải thư mục con
git remote -v                          # đã có origin trỏ về GitHub thì bỏ qua bước này
git push -u origin main
```

Chưa có repo trên GitHub thì tạo một cái rồi:

```bash
git remote add origin git@github.com:<ten-cua-ban>/vietreader.git
git push -u origin main
```

`.env` đã nằm trong `.gitignore` nên khoá API của bạn không bị đẩy lên. Trên Railway, cấu hình
đi qua biến môi trường ở §5 chứ không qua file `.env`.

---

## 2. Tạo project trên Railway

1. Đăng nhập [railway.com](https://railway.com) bằng tài khoản GitHub.
2. **New Project → Deploy from GitHub repo**.
3. Cho Railway quyền đọc repo `vietreader`, rồi chọn nó.

Railway sẽ lập tức thử build và **lần đầu này gần như chắc chắn thất bại** — vì nó đang tìm
`Dockerfile` ở gốc repo, mà file đó nằm trong thư mục con. Đó là chuyện bình thường, §3 sửa ngay.

---

## 3. Đặt Root Directory (bước hay quên nhất)

Mã nguồn nằm ở thư mục con `vietreader/` của repo, không phải ở gốc. Phải nói cho Railway biết:

**Service → tab Settings → mục Source → Root Directory** → điền:

```
vietreader
```

Bấm **Deploy** (hoặc chờ Railway tự deploy lại).

Kiểm tra ngay bên dưới, mục **Build**: builder phải là **Dockerfile**. Railway tự nhận ra khi
thấy `Dockerfile` trong root directory. Nếu nó vẫn hiện Railpack/Nixpacks nghĩa là root
directory chưa đúng — quay lại sửa, đừng đi tiếp.

`railway.json` (nằm sẵn trong repo cùng chỗ với `Dockerfile`) lo phần healthcheck, bạn không
phải cấu hình gì thêm.

Lần build đầu mất **10–25 phút** vì phải compile `lxml` và `selectolax`. Xem tiến trình ở tab
**Deployments**. Các lần sau nhanh hơn nhiều nhờ cache.

---

## 4. Gắn volume cho database

Không có volume thì database nằm trong hệ thống file tạm của container, và **mất sạch mỗi lần
deploy lại** — thư viện, từ điển, ghi chú, vị trí đọc, mất hết. Bước này bắt buộc.

### 4.1 Tạo volume

Chuột phải vào service → **Attach Volume** (hoặc **New → Volume**). Mount path:

```
/data
```

Đúng `/data`, không phải `/app/data`. `Dockerfile` đã đặt sẵn
`VIETREADER_DATABASE_URL=sqlite:////data/vietreader.db`, nên gắn đúng chỗ là mọi thứ tự khớp,
không phải khai báo thêm biến nào.

> **Đừng đặt `VIETREADER_DATABASE_URL` trong biến môi trường của Railway.** Giá trị trong
> `Dockerfile` đã đúng rồi; đặt đè lên bằng một đường dẫn khác là database rơi ra ngoài volume
> và bạn mất dữ liệu ở lần deploy kế tiếp mà không có cảnh báo nào.

### 4.2 Biến `RAILWAY_RUN_UID` — bắt buộc

Thêm biến môi trường này cho service (tab **Variables**):

```
RAILWAY_RUN_UID = 0
```

**Vì sao cần:** `Dockerfile` cho app chạy bằng user thường `vietreader` (uid 10001) thay vì
root — một lựa chọn về bảo mật. Ở local việc này không sao, vì Docker named volume thừa hưởng
quyền sở hữu từ thư mục `/data` đã `chown` sẵn trong ảnh. Railway thì khác: volume được mount
là một hệ thống file trống **thuộc root**, nên uid 10001 không ghi vào được.

Không đặt biến này thì app khởi động lên trông có vẻ ổn, nhưng mọi thao tác lưu đều hỏng với
`attempt to write a readonly database` — hoặc alembic chết ngay từ lúc migrate. Railway ghi rõ
điều này trong [tài liệu về volume](https://docs.railway.com/volumes/reference) của họ.

Đây là cái giá phải trả khi dùng volume của PaaS: app chạy bằng root **bên trong container**.
Với một app cá nhân trên hạ tầng được cách ly thì đánh đổi này chấp nhận được — bản tự host ở
[DEPLOY.md](DEPLOY.md) không phải nhượng bộ chỗ này.

---

## 5. Đặt biến môi trường

Tab **Variables** của service, thêm:

```
VIETREADER_READER_NAME = Ngân Giang
VIETREADER_LLM_API_KEY =
```

- `VIETREADER_READER_NAME` — tên hiện trong lời chào và các màn hình trống.
- `VIETREADER_LLM_API_KEY` — **đọc §9 trước khi điền khoá vào đây.**

Các giá trị còn lại (model, temperature, batch size, user agent, log level) đều có mặc định hợp
lý trong code, chưa cần khai báo. Muốn đổi thì tra tên biến trong
[`config/settings.example.env`](config/settings.example.env) và thêm vào đây với cùng tên.

Trên Railway **không có file `.env`** — app đọc thẳng biến môi trường, nên khai ở đây là đủ.

---

## 6. Deploy và mở tên miền

**Settings → Networking → Generate Domain.**

Railway cấp một địa chỉ dạng `vietreader-production-xxxx.up.railway.app` kèm HTTPS tự động —
không cần Caddy, không cần certbot, không cần mua tên miền.

Có tên miền riêng thì **Custom Domain**, Railway sẽ chỉ bạn thêm bản ghi CNAME.

Mỗi lần đổi biến hay volume, Railway deploy lại. Chờ tab **Deployments** hiện **Active**.

---

## 7. Kiểm tra

```bash
curl https://<ten-mien-cua-ban>.up.railway.app/api/health     # {"status":"ok"}
```

Rồi mở địa chỉ đó trên trình duyệt — phải ra trang chủ VietReader với lời chào đúng tên bạn
đặt ở §5.

Kiểm tra thêm rằng volume thật sự hoạt động, đây là chỗ dễ tưởng xong mà chưa xong:

1. Mở `/dictionary`, thêm một entry bất kỳ.
2. Vào Railway bấm **Redeploy**.
3. Mở lại `/dictionary`.

Entry còn nguyên là volume đã gắn đúng. Entry biến mất nghĩa là §4 có gì đó sai — quay lại kiểm
tra mount path đúng `/data` và biến `RAILWAY_RUN_UID` đã có chưa.

---

## 8. Nạp từ điển mẫu

65 entry tiên hiệp/kiếm hiệp (35 REPLACE, 15 KEEP, 15 ASK) để từ điển không rỗng lúc đọc chương
đầu tiên. Cần [Railway CLI](https://docs.railway.com/cli):

```bash
npm i -g @railway/cli        # hoặc: brew install railway
railway login
railway link                 # chọn project và service vừa tạo
railway ssh -- python scripts/seed_dictionary.py
```

Kết quả: `Seeded 65 entries into sqlite:////data/vietreader.db (0 already existed).`

Chạy lại nhiều lần vô hại — script bỏ qua entry đã tồn tại, không tạo trùng, không ghi đè.

Không muốn cài CLI thì bỏ qua bước này cũng được: từ điển bắt đầu rỗng, và bạn tự thêm từ khi
đọc bằng popup bôi đen văn bản. Chỉ là chương đầu tiên sẽ chưa thay được từ nào.

---

## 9. Chắn truy cập (đọc kỹ mục này)

**App không có lớp đăng nhập** — đây là lựa chọn có chủ đích cho một ứng dụng cá nhân, và không
có biến môi trường nào bật nó lên được vì trong code không tồn tại tính năng đó.

Trên Railway điều này đáng lưu tâm hơn bản tự host: địa chỉ `*.up.railway.app` nằm công khai
trên Internet, và **không có reverse proxy nào của bạn đứng trước để gắn mật khẩu vào** — mẹo
basic auth bằng Caddy ở [DEPLOY.md §9](DEPLOY.md) không dùng được ở đây.

Ba cách xử lý:

**Cách A — để trống `VIETREADER_LLM_API_KEY`** (đơn giản nhất, khuyến nghị nếu bạn chỉ muốn xong việc).
Mất tính năng ASK: span mơ hồ giữ nguyên thay vì hỏi LLM, có ghi WARN vào `run_log`. REPLACE,
KEEP, extraction, reader, từ điển, ghi chú vẫn chạy đủ. Đổi lại: người lạ có mò ra địa chỉ cũng
không tiêu được tiền API của bạn. Địa chỉ Railway sinh ra có chuỗi ngẫu nhiên nên bot khó đoán,
nhưng đừng coi đó là bảo mật — nó chỉ là chưa ai để ý.

**Cách B — Cloudflare Access.** Cần tên miền riêng trỏ qua Cloudflare (§6, Custom Domain). Đặt
Cloudflare Access phía trước, chỉ cho email của bạn vào. Miễn phí tới 50 người dùng, không phải
sửa code. Đây là cách chắc chắn nhất mà vẫn giữ đủ tính năng.

**Cách C — thêm basic auth vào chính app.** Khoảng 20 dòng middleware trong
`src/vietreader/api/app.py`, đọc mật khẩu từ một biến môi trường mới. Đây là thay đổi code duy
nhất trong toàn bộ tài liệu này. **Bảo tôi nếu bạn muốn, tôi viết cho.**

Chưa quyết được thì đi Cách A trước — thêm khoá sau lúc nào cũng được, chỉ là sửa một biến rồi
Railway tự deploy lại.

---

## 10. Sao lưu

Database này là **toàn bộ** thư viện, vị trí đọc, từ điển và ghi chú của bạn. Mất là mất hết.

### 10.1 Bật sao lưu tự động

Đây là phần Railway làm hộ, thay cho toàn bộ mục cron + `scp` của bản tự host.

Service → tab **Backups** → bật lịch. Có thể bật nhiều lịch cùng lúc:

| Lịch | Tần suất | Giữ lại |
|---|---|---|
| Daily | 24 giờ/lần | 6 ngày |
| Weekly | 7 ngày/lần | 1 tháng |
| Monthly | 30 ngày/lần | 3 tháng |

Bật cả Daily và Weekly là hợp lý: Daily để cứu sai sót vừa xảy ra, Weekly để cứu thứ hỏng từ
lâu mà giờ mới phát hiện.

### 10.2 Khôi phục

Tab **Backups** → chọn bản theo ngày → **Restore**. Railway tạo một volume mới mang tên ngày của
bản sao lưu và **stage** thay đổi để bạn xem lại; volume cũ vẫn còn nhưng ở trạng thái không
mount. Xem xong bấm **Deploy** là xong.

> Railway ghi rõ: *"Restoring a backup will remove any newer backups you may have created after
> the backup you are restoring."* Khôi phục về một mốc xa là mất các bản sao lưu mới hơn mốc đó
> — cân nhắc trước khi bấm.

### 10.3 Giữ một bản ngoài Railway

Sao lưu của Railway nằm trên Railway. Tài khoản có chuyện, hoặc bạn lỡ xoá project, là mất cả
cụm. Thỉnh thoảng kéo một bản về máy:

```bash
railway ssh -- sh -c 'sqlite3 /data/vietreader.db ".backup /tmp/b.db" && gzip -c /tmp/b.db | base64' \
  | base64 -d > vietreader-$(date +%Y%m%d).db.gz
```

Lệnh này dùng `.backup` của SQLite chứ không copy file — copy trong lúc app đang ghi có thể ra
bản hỏng vì WAL còn dữ liệu chưa dồn vào file chính. Chỗ `base64` là để đưa dữ liệu nhị phân
qua đường SSH an toàn; `railway ssh` tự tắt PTY khi output bị pipe nên không lẫn ký tự lạ.

Kiểm tra bản vừa tải trước khi yên tâm:

```bash
gunzip -c vietreader-20260814.db.gz > /tmp/kiemtra.db
sqlite3 /tmp/kiemtra.db "PRAGMA integrity_check; SELECT count(*) FROM dictionary_entry;"
```

Ra `ok` và một con số hợp lý là bản sao lưu dùng được.

---

## 11. Nâng cấp

```bash
git push
```

Hết. Railway thấy commit mới trên nhánh đã nối, tự build và tự deploy. Volume không bị đụng tới,
migration tự chạy khi container khởi động (`Dockerfile` chạy `alembic upgrade head` trước
uvicorn).

Muốn chắc chắn thì tạo một backup thủ công ở tab **Backups** trước khi push một thay đổi lớn.

Bản mới hỏng thì vào tab **Deployments**, tìm bản deploy trước đó, bấm **Redeploy**. Lưu ý: quay
lại code cũ **không** tự quay lại schema database — nếu bản mới có migration thì phải khôi phục
cả backup theo §10.2.

---

## 12. Khắc phục sự cố

**Build fail, log ghi `Dockerfile does not exist` hoặc Railway dùng Railpack/Nixpacks** — Root
Directory chưa đặt. Quay lại §3, điền `vietreader`.

**Build chạy rất lâu rồi fail** — lần đầu compile `lxml`/`selectolax` mất 10–25 phút, đó là bình
thường. Fail thật thì xem log ở tab Deployments; nếu thấy `Killed` là hết RAM lúc build, nâng
gói hoặc mở issue để tôi chuyển sang cài từ wheel dựng sẵn.

**App chạy nhưng lưu gì cũng lỗi `attempt to write a readonly database`** — thiếu
`RAILWAY_RUN_UID=0`. Xem §4.2.

**Deploy lại là mất sạch dữ liệu** — chưa gắn volume, hoặc mount path sai. Phải đúng `/data`
(§4.1). Cũng kiểm tra xem có ai lỡ đặt `VIETREADER_DATABASE_URL` trong Variables không.

**Healthcheck fail, deploy không bao giờ lên Active** — xem log. Hay gặp nhất là alembic chết
lúc migrate, dòng lỗi nằm ngay đầu log của lần khởi động cuối. Thứ nhì là quyền volume (§4.2).

**Trang chủ mở được nhưng đọc chương nào cũng thấy từ mơ hồ giữ nguyên** — không có
`VIETREADER_LLM_API_KEY`. Đúng như thiết kế nếu bạn chọn Cách A ở §9.

**`railway ssh` báo không tìm thấy service** — chạy `railway link` lại và chọn đúng project +
service + environment.

**Hết credit giữa tháng** — vào tab Usage xem cái gì ngốn. App này chủ yếu tính tiền theo RAM
và thời gian chạy; nếu vượt bất thường thì thường là service bị restart lặp (crash loop), xem
log để tìm nguyên nhân thật.

---

## So với bản tự host

| | Railway | Oracle Cloud ([DEPLOY.md](DEPLOY.md)) |
|---|---|---|
| Công sức lần đầu | ~20 phút, bấm nút | ~60 phút, gõ lệnh |
| Chi phí | ~$5/tháng | $0 (Always Free) |
| HTTPS | Tự động | Tự cài Caddy |
| Sao lưu | Có sẵn, bật là chạy | Tự viết cron + tự chép về |
| Nâng cấp | `git push` | SSH vào, `git pull && docker compose up -d --build` |
| Chắn mật khẩu | Cần Cloudflare Access hoặc sửa code | Basic auth ở Caddy, không sửa code |
| App chạy bằng | root trong container (bắt buộc, §4.2) | user thường uid 10001 |
| Kiểm soát | Chỉ những gì Railway cho | Toàn quyền |

Cả hai dùng chung `Dockerfile`, chung SQLite, chung migration. Đổi qua lại được: khôi phục
database ở bên này từ bản sao lưu của bên kia là chuyện chép một file `.db`.

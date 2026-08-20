# Đưa VietReader lên Render + Neon

Đây là đường triển khai chính của dự án: Render chạy container, Neon giữ dữ liệu PostgreSQL.
`render.yaml` đã cấu hình migration, readiness check, auth bắt buộc và chỉ deploy sau khi CI
GitHub xanh.

> Gói Free phù hợp để dùng cá nhân/thử nghiệm, không phải production có cam kết. Render ghi rõ
> Free Web Service sẽ ngủ sau 15 phút không có traffic, mất khoảng một phút để thức lại, dùng
> filesystem tạm và không nên dùng cho ứng dụng production. Nếu cần truy cập ổn định, chọn ít
> nhất gói Starter của Render.

## 1. Bạn cần chuẩn bị

- Repo GitHub chứa toàn bộ thư mục gốc, gồm `render.yaml` và `.github/workflows/ci.yml`.
- Một project Neon, nên đặt cùng khu vực Singapore với service Render.
- Một mật khẩu riêng, dài cho VietReader.
- API key Anthropic chỉ khi muốn dùng mục từ điển có policy `ASK`.

Không gửi connection string, password hoặc API key vào chat, issue hay commit Git.

## 2. Tạo database Neon

1. Tạo project `vietreader` và chọn region Singapore nếu dashboard có lựa chọn này.
2. Mở **Connect**.
3. Bật **Pooled connection** rồi copy toàn bộ connection string.
4. Kiểm tra hostname có `-pooler` và giữ nguyên các query parameter bảo mật Neon cấp, thường là
   `sslmode=require&channel_binding=require`.

Ví dụ (không dùng chuỗi này):

```text
postgresql://owner:password@ep-example-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

VietReader tự chuẩn hoá scheme sang driver `psycopg`, bật `pool_pre_ping` và timeout cho pool.
Không tự đổi chuỗi thành `postgresql+psycopg2://`.

Gói Neon Free hiện có 0,5 GB storage, 100 CU-hour mỗi project mỗi tháng, scale-to-zero sau 5 phút
không hoạt động và lịch sử khôi phục 6 giờ. Nếu dữ liệu có giá trị, vẫn phải có bản `pg_dump`
riêng; 6 giờ không thay thế backup.

## 3. Tạo service Render

1. Vào **New → Blueprint** và kết nối repo GitHub.
2. Chọn nhánh `main` và để Render đọc `render.yaml` ở gốc repo.
3. Khi Blueprint hỏi giá trị bí mật, điền ba biến sau.

| Biến | Bắt buộc | Giá trị |
|---|---:|---|
| `VIETREADER_DATABASE_URL` | Có | Pooled connection string từ Neon |
| `VIETREADER_AUTH_PASSWORD` | Có | Mật khẩu dài, riêng cho ứng dụng |
| `VIETREADER_LLM_API_KEY` | Không | Để trống nếu chưa dùng policy `ASK` |

Các giá trị an toàn đã nằm trong Blueprint:

```text
VIETREADER_REQUIRE_POSTGRES=1
VIETREADER_AUTO_CREATE_SCHEMA=0
VIETREADER_REQUIRE_AUTH=1
VIETREADER_AUTH_USERNAME=vietreader
VIETREADER_READER_NAME=Ngân Giang
VIETREADER_SEED_ON_START=1
```

Bạn có thể đổi username và tên người đọc trong tab **Environment**. Không tắt ba cờ
`REQUIRE_POSTGRES`, `AUTO_CREATE_SCHEMA=0`, `REQUIRE_AUTH` trên service công khai.

## 4. Quá trình khởi động production

Render Free không hỗ trợ pre-deploy command. Vì vậy `scripts/start.sh` chạy đúng thứ tự trong
container:

1. `alembic upgrade head`;
2. seed từ điển idempotent nếu `VIETREADER_SEED_ON_START=1`;
3. khởi động Uvicorn bằng cổng do Render cấp.

Production không gọi `Base.metadata.create_all`. Nếu migration lỗi, container dừng thay vì tự
tạo một schema nửa đúng. Nếu thiếu/nhầm URL Neon, `VIETREADER_REQUIRE_POSTGRES=1` cũng khiến app
dừng ngay thay vì âm thầm ghi SQLite trên đĩa tạm.

Log khởi động đúng có dạng:

```text
==> database: postgresql://***@ep-....neon.tech/neondb
==> alembic upgrade head
==> seed từ điển mẫu (VIETREADER_SEED_ON_START=1)
==> uvicorn trên cổng 10000
```

URL trong log đã che cả username và password.

## 5. Health check và kiểm tra sau deploy

Blueprint dùng `/api/ready`. Endpoint này chạy `SELECT 1`; Render chỉ chuyển traffic cho phiên
bản mới khi ứng dụng và Neon đều sẵn sàng. `/api/health` chỉ là liveness nhẹ cho monitor ngoài.
Cả hai endpoint đều công khai; các trang và API dữ liệu yêu cầu Basic Auth.

Kiểm tra theo thứ tự:

```bash
curl https://<service>.onrender.com/api/health
curl https://<service>.onrender.com/api/ready
```

Kết quả mong đợi:

```json
{"status":"ok"}
{"status":"ready"}
```

Sau đó mở URL bằng trình duyệt:

1. đăng nhập bằng `VIETREADER_AUTH_USERNAME` và password đã đặt;
2. mở trang chủ, dán một chương có tiêu đề và kiểm tra tiêu đề/body;
3. thử một link chương thật;
4. thêm một entry ở `/dictionary`;
5. **Manual Deploy → Deploy latest commit**;
6. xác nhận entry và thư viện vẫn còn sau deploy.

Nếu dữ liệu biến mất, dừng sử dụng và kiểm tra ngay `VIETREADER_DATABASE_URL` cùng dòng
`==> database:` trong log.

## 6. CI/CD

`render.yaml` dùng `autoDeployTrigger: checksPass`. Luồng deploy là:

1. push `main`;
2. GitHub Actions chạy Ruff, mypy, toàn bộ pytest, build và smoke-test image production;
3. commit chỉ được Render deploy khi checks của commit đó xanh;
4. readiness thất bại thì phiên bản mới không nhận traffic.

Không cần tạo Render Deploy Hook và không cần secret `RENDER_DEPLOY_HOOK_URL`. Workflow
`.github/workflows/deploy.yml` chỉ còn phục vụ đường tự host qua SSH.

Sau khi đổi `render.yaml`, mở Blueprint trên Render và bấm **Sync** để áp dụng thay đổi cấu hình.

## 7. Backup và khôi phục

Neon Free chỉ có cửa sổ restore 6 giờ. Tạo backup định kỳ từ máy có PostgreSQL client:

```bash
pg_dump "<NEON_CONNECTION_STRING>" -Fc -f vietreader-YYYYMMDD.dump
pg_restore -l vietreader-YYYYMMDD.dump
```

Khôi phục là thao tác ghi đè có rủi ro; luôn tạo branch/database đích riêng để kiểm tra bản dump
trước khi phục hồi vào production.

## 8. Sự cố thường gặp

- **App mở đầu ngày chậm:** hành vi bình thường của Render Free sau khi ngủ. Nâng lên Starter nếu
  cần phản hồi ổn định; không coi keepalive miễn phí là SLA production.
- **`/api/ready` trả 503:** kiểm tra Neon còn hoạt động, URL/SSL đúng và xem log migration.
- **Service không khởi động, báo cần PostgreSQL:** chưa nhập hoặc nhập sai
  `VIETREADER_DATABASE_URL`; đây là fail-safe chủ ý.
- **Service không khởi động, báo thiếu auth:** nhập `VIETREADER_AUTH_PASSWORD` và giữ username.
- **Migration lỗi:** không bật lại tự tạo schema. Giữ log, kiểm tra revision bằng `alembic current`
  trên môi trường có quyền kết nối Neon.
- **CI xanh nhưng chưa deploy:** Sync Blueprint, kiểm tra repo/nhánh `main`, và xác nhận
  `autoDeployTrigger` là `checksPass`.
- **Link truyện không đọc được:** site nguồn có thể chặn bot. UI sẽ hướng dẫn dán nội dung; gửi
  URL cụ thể để bổ sung adapter, không tắt TLS hay cho phép private network trên production.

## 9. Cấu hình tối thiểu nên chọn

| Mức sử dụng | Render | Neon | Ghi chú |
|---|---|---|---|
| Cá nhân/thử nghiệm | Free | Free | Có cold start, không có SLA |
| Dùng hằng ngày ổn định | Starter hoặc cao hơn | Free/Launch theo tải | Không ngủ phía web |
| Dữ liệu quan trọng | Paid phù hợp tải | Paid + backup ngoài | Theo dõi usage và diễn tập restore |

Cùng code vẫn chạy local bằng SQLite vì `AUTO_CREATE_SCHEMA` mặc định bật và
`REQUIRE_POSTGRES` mặc định tắt. Các cờ fail-safe chỉ được Blueprint bật cho production.

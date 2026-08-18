# Ảnh chạy thật. Khác docker-compose.dev.yml ở chỗ: cài sẵn dependency vào ảnh (không cài lúc
# khởi động), không mount mã nguồn, không --reload, và chạy bằng user thường.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Bước 1 — CHỈ dependency, chưa có mã nguồn. Layer này chỉ dựng lại khi pyproject.toml đổi.
# Cài bằng một package rỗng để pip đọc được danh sách dependency mà không cần src thật.
#
# Đừng gộp bước này với bước 2: nếu `COPY src` nằm trước `pip install`, mọi thay đổi mã nguồn
# đều làm hỏng cache và bắt compile lại lxml/selectolax — 15-25 phút mỗi lần deploy trên ARM.
# Tách ra thì deploy thường chỉ mất ~30 giây.
#
# build-essential chỉ cần lúc build (ARM không có wheel dựng sẵn), gỡ đi sau để ảnh nhẹ.
# Riêng `sqlite3` (CLI) cài SAU khi purge và giữ luôn: scripts/backup_db.sh gọi `sqlite3 .backup`,
# mà python:*-slim chỉ có thư viện libsqlite3 chứ không có lệnh sqlite3.
COPY pyproject.toml README.md ./
RUN mkdir -p src/vietreader && touch src/vietreader/__init__.py \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && pip install --upgrade pip \
 && pip install . \
 && pip uninstall -y vietreader \
 && apt-get purge -y --auto-remove build-essential \
 && apt-get install -y --no-install-recommends sqlite3 \
 && rm -rf /var/lib/apt/lists/* src

# Bước 2 — mã nguồn chạy THẲNG từ cây nguồn qua PYTHONPATH, không `pip install`.
#
# Vì sao không cài: `[tool.setuptools.packages.find]` chỉ nhận thư mục có __init__.py, mà
# `llm/prompts/` và `web/` đều không có. Cài xong thì wheel thiếu disambiguate.v1.txt, thiếu
# toàn bộ templates và static — app chết ngay lúc import. Ngoài ra registry.py dò config/sites
# bằng `parents[3]`, trong layout site-packages thì đường dẫn đó trỏ ra ngoài trời.
#
# Chạy từ cây nguồn làm production khớp đúng bản dev (docker-compose.dev.yml dùng `pip install -e`,
# cũng là chạy từ cây nguồn) — nên thứ gì chạy được lúc dev thì chạy được ở đây.
COPY src ./src
ENV PYTHONPATH=/app/src

COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
COPY scripts ./scripts

# Dữ liệu nằm ở volume riêng để nâng cấp ảnh không mất thư viện, từ điển, ghi chú.
RUN mkdir -p /data && useradd --create-home --uid 10001 vietreader && chown -R vietreader /data /app
USER vietreader

ENV VIETREADER_DATABASE_URL=sqlite:////data/vietreader.db \
    PORT=8000

EXPOSE 8000

CMD ["./scripts/start.sh"]

# Ảnh chạy thật. Khác docker-compose.dev.yml ở chỗ: cài sẵn dependency vào ảnh (không cài lúc
# khởi động), không mount mã nguồn, không --reload, và chạy bằng user thường.
FROM python:3.12-slim

# lxml/selectolax cần toolchain lúc build; gỡ đi sau để ảnh nhẹ.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && pip install --upgrade pip \
 && pip install . \
 && apt-get purge -y --auto-remove build-essential \
 && rm -rf /var/lib/apt/lists/*

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

# Chạy migration trước rồi mới lên server: alembic nay đọc VIETREADER_DATABASE_URL nên nó
# migrate ĐÚNG file mà app sẽ mở.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn vietreader.api.app:app --host 0.0.0.0 --port ${PORT}"]

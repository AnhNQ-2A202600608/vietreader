from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from vietreader.db.models import Base
from vietreader.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ưu tiên VIETREADER_DATABASE_URL — cùng biến mà app dùng.
#
# Trước đây env.py chỉ đọc alembic.ini, nên trên máy chủ (nơi đường dẫn DB đến từ biến môi
# trường) `alembic upgrade head` tạo bảng ở MỘT file, còn app lại đọc file khác: app khởi động
# thấy DB trống, hoặc thiếu bảng. Lỗi này im lặng và rất khó đoán, nên phải sửa trước khi deploy.
_env_url = get_settings().database_url
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

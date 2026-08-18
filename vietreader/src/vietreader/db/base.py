"""SQLAlchemy engine/session setup.

Hai dialect được hỗ trợ, chọn theo `VIETREADER_DATABASE_URL`:

- **SQLite (WAL)** — mặc định, dùng khi chạy local và khi tự host trên máy có đĩa bền
  (spec §1.1: "SQLite (WAL)").
- **PostgreSQL** — dùng khi deploy lên nền tảng có hệ thống file tạm, không giữ được file
  giữa hai lần khởi động (Render free + Neon). Xem DEPLOY_RENDER.md.

Toàn bộ phần còn lại của ứng dụng không biết nó đang chạy trên dialect nào: model, repository
và migration đều là SQLAlchemy/Alembic thuần, không có SQL riêng cho dialect nào.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def normalize_database_url(url: str) -> str:
    """Đưa URL Postgres về dạng driver mà dự án này thực sự cài.

    Neon, Render và Heroku đều phát chuỗi kết nối dạng `postgres://` hoặc `postgresql://`.
    Cả hai dạng đó khiến SQLAlchemy đi tìm **psycopg2**, thứ không có trong dependency —
    kết quả là `ModuleNotFoundError: No module named 'psycopg2'` ngay lúc khởi động, một
    thông báo chẳng liên quan gì tới việc người dùng vừa dán nhầm URL.

    Chuẩn hoá ở đây để người deploy dán thẳng chuỗi Neon cho sẵn, không phải sửa tay.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def create_db_engine(database_url: str) -> Engine:
    url = normalize_database_url(database_url)

    if url.startswith("sqlite"):
        # check_same_thread chỉ tồn tại ở driver sqlite3; truyền nó cho psycopg là lỗi.
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    # Postgres. pool_pre_ping là bắt buộc chứ không phải tối ưu: Neon co compute về 0 sau
    # 5 phút không ai dùng, nên connection nằm sẵn trong pool sẽ chết lặng lẽ. Không có
    # pre_ping thì request đầu tiên sau lúc rảnh sẽ ném lỗi kết nối vào mặt người đọc.
    return create_engine(url, pool_pre_ping=True, pool_recycle=300)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

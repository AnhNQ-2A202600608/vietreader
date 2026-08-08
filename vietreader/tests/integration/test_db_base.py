"""Phase 5: exercise db/base.py engine/session helpers directly (not just via the fixture)."""

from __future__ import annotations

from sqlalchemy import text

from vietreader.db.base import create_db_engine, create_session_factory, session_scope
from vietreader.db.models import Base


def test_create_db_engine_enables_wal_mode(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert mode is not None
    assert mode.lower() == "wal"
    engine.dispose()


def test_session_scope_commits_on_success(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from vietreader.db.models import RunLogRow

    engine = create_db_engine(f"sqlite:///{tmp_path / 'test2.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        session.add(RunLogRow(stage="s", level="INFO", message="m"))

    with factory() as session:
        count = session.query(RunLogRow).count()
    assert count == 1
    engine.dispose()


def test_session_scope_rolls_back_on_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from vietreader.db.models import RunLogRow

    engine = create_db_engine(f"sqlite:///{tmp_path / 'test3.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with session_scope(factory) as session:
            session.add(RunLogRow(stage="s", level="INFO", message="m"))
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with factory() as session:
        count = session.query(RunLogRow).count()
    assert count == 0
    engine.dispose()

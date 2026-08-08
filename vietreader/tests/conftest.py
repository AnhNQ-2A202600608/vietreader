"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from vietreader.db.models import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A fresh in-memory SQLite DB per test, schema created directly from the ORM models
    (not via Alembic -- migration correctness is verified separately, see PHASE_REPORTS.md)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()

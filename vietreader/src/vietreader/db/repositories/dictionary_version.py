"""Persistence for dictionary version hashes used by chapter cache keys."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vietreader.db.models import DictionaryVersionRow


class DictionaryVersionRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure(self, version_hash: str, entry_count: int) -> DictionaryVersionRow:
        row = self._session.execute(
            select(DictionaryVersionRow).where(DictionaryVersionRow.hash == version_hash)
        ).scalar_one_or_none()
        if row is None:
            row = DictionaryVersionRow(hash=version_hash, entry_count=entry_count)
            self._session.add(row)
            self._session.flush()
        return row

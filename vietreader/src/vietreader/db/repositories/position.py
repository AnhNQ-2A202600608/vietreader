"""PositionRepo: reading position per series_key (throttled writes happen at the API layer)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from vietreader.db.models import ReadingPositionRow


@dataclass(frozen=True, slots=True)
class ReadingPosition:
    series_key: str
    url: str
    para_index: int
    updated_at: dt.datetime


def _row_to_position(row: ReadingPositionRow) -> ReadingPosition:
    return ReadingPosition(
        series_key=row.series_key, url=row.url, para_index=row.para_index, updated_at=row.updated_at
    )


class PositionRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, series_key: str) -> ReadingPosition | None:
        stmt = select(ReadingPositionRow).where(ReadingPositionRow.series_key == series_key)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _row_to_position(row) if row else None

    def upsert(self, series_key: str, url: str, para_index: int) -> ReadingPosition:
        stmt = select(ReadingPositionRow).where(ReadingPositionRow.series_key == series_key)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = ReadingPositionRow(series_key=series_key, url=url, para_index=para_index)
            self._session.add(row)
        else:
            row.url = url
            row.para_index = para_index
        self._session.flush()
        return _row_to_position(row)

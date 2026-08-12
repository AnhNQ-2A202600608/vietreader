"""SeriesRepo: stories that group chapters, plus the wiring that attaches a chapter to one."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vietreader.core.series import derive_series_key, series_title_from_key
from vietreader.db.models import ChapterCacheRow, SeriesRow


@dataclass(frozen=True, slots=True)
class Series:
    id: int
    series_key: str
    title: str
    followed: bool
    created_at: dt.datetime | None = None
    last_read_at: dt.datetime | None = None
    chapter_count: int = 0


def _row_to_series(row: SeriesRow, chapter_count: int = 0) -> Series:
    return Series(
        id=row.id,
        series_key=row.series_key,
        title=row.title,
        followed=row.followed,
        created_at=row.created_at,
        last_read_at=row.last_read_at,
        chapter_count=chapter_count,
    )


class SeriesRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, series_id: int) -> Series | None:
        row = self._session.get(SeriesRow, series_id)
        return _row_to_series(row, self.chapter_count(series_id)) if row else None

    def get_by_key(self, series_key: str) -> Series | None:
        stmt = select(SeriesRow).where(SeriesRow.series_key == series_key)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _row_to_series(row, self.chapter_count(row.id)) if row else None

    def get_or_create(self, series_key: str, title: str | None = None) -> Series:
        existing = self._session.execute(
            select(SeriesRow).where(SeriesRow.series_key == series_key)
        ).scalar_one_or_none()
        if existing is not None:
            return _row_to_series(existing, self.chapter_count(existing.id))

        row = SeriesRow(series_key=series_key, title=title or series_title_from_key(series_key))
        self._session.add(row)
        self._session.flush()
        return _row_to_series(row)

    def chapter_count(self, series_id: int) -> int:
        """Distinct chapters, not cache rows: reprocessing a chapter after a dictionary edit
        adds another row for the same text and must not inflate the count."""
        stmt = select(func.count(func.distinct(ChapterCacheRow.raw_hash))).where(
            ChapterCacheRow.series_id == series_id
        )
        return int(self._session.execute(stmt).scalar_one())

    def list_recent(self, limit: int = 50) -> list[Series]:
        recency = func.coalesce(SeriesRow.last_read_at, SeriesRow.created_at)
        stmt = select(SeriesRow).order_by(recency.desc(), SeriesRow.id.desc()).limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_series(row, self.chapter_count(row.id)) for row in rows]

    def touch(self, series_id: int) -> None:
        row = self._session.get(SeriesRow, series_id)
        if row is not None:
            row.last_read_at = dt.datetime.now(dt.UTC)
            self._session.flush()

    def rename(self, series_id: int, title: str) -> Series | None:
        row = self._session.get(SeriesRow, series_id)
        if row is None:
            return None
        cleaned = title.strip()
        if cleaned:
            row.title = cleaned
            self._session.flush()
        return _row_to_series(row, self.chapter_count(series_id))

    def set_followed(self, series_id: int, followed: bool) -> Series | None:
        row = self._session.get(SeriesRow, series_id)
        if row is None:
            return None
        row.followed = followed
        self._session.flush()
        return _row_to_series(row, self.chapter_count(series_id))


def link_chapter_to_series(
    session: Session, *, chapter_cache_id: int | None, url: str | None, title: str | None
) -> Series | None:
    """Attach a freshly processed chapter to its story, creating the story on first sight.

    Returns None for chapters that cannot belong to a series (pasted text, or a URL too
    shallow to identify one) -- those stay standalone rather than being forced into a group.

    Linking never MOVES a chapter. chapter_cache is keyed by content, so two URLs holding
    byte-identical text share one row; without this guard, opening the second URL would drag
    the first URL's chapter into a different story and leave the original story short a
    chapter. First URL to store the row wins, and no phantom empty story is created.
    """
    if chapter_cache_id is None:
        return None

    repo = SeriesRepo(session)
    chapter = session.get(ChapterCacheRow, chapter_cache_id)

    if chapter is not None and chapter.series_id is not None:
        existing = repo.get(chapter.series_id)
        if existing is not None:
            repo.touch(existing.id)
            session.flush()
            return existing

    series_key = derive_series_key(url)
    if series_key is None:
        return None

    series = repo.get_or_create(series_key)
    if chapter is not None:
        chapter.series_id = series.id
    repo.touch(series.id)
    session.flush()
    return series

"""ChapterCacheRepo. Cache key per spec §2.4: sha256(raw_text) + dict_version_hash +
prompt_version + model -- changing any component is a cache miss."""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from vietreader.core.series import chapter_number, infer_chapter_title
from vietreader.db.models import ChapterCacheRow


def _recency(row: ChapterCacheRow) -> dt.datetime:
    return row.last_read_at or row.created_at


def compute_raw_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def compute_source_key(
    raw_hash: str, dict_version_hash: str, prompt_version: str, model: str
) -> str:
    return "|".join((raw_hash, dict_version_hash, prompt_version, model))


@dataclass(frozen=True, slots=True)
class ChapterCacheEntry:
    id: int
    source_key: str
    url: str | None
    title: str
    raw_hash: str
    raw_text: str
    output_text: str
    changelog_json: str
    dict_version_hash: str
    prompt_version: str
    model: str
    next_url: str | None = None
    prev_url: str | None = None
    series_id: int | None = None
    created_at: dt.datetime | None = None
    last_read_at: dt.datetime | None = None


def _row_to_entry(row: ChapterCacheRow) -> ChapterCacheEntry:
    return ChapterCacheEntry(
        id=row.id,
        source_key=row.source_key,
        url=row.url,
        # Apply on reads too so legacy rows with an empty/stale title immediately recover from
        # their opening paragraph or URL without requiring a production DB backfill first.
        title=infer_chapter_title(row.title, row.url, row.raw_text.split("\n\n")),
        raw_hash=row.raw_hash,
        raw_text=row.raw_text,
        output_text=row.output_text,
        changelog_json=row.changelog_json,
        dict_version_hash=row.dict_version_hash,
        prompt_version=row.prompt_version,
        model=row.model,
        next_url=row.next_url,
        prev_url=row.prev_url,
        series_id=row.series_id,
        created_at=row.created_at,
        last_read_at=row.last_read_at,
    )


class ChapterCacheRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, source_key: str) -> ChapterCacheEntry | None:
        stmt = select(ChapterCacheRow).where(ChapterCacheRow.source_key == source_key)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _row_to_entry(row) if row else None

    def put(
        self,
        *,
        source_key: str,
        url: str | None,
        title: str,
        raw_hash: str,
        raw_text: str,
        output_text: str,
        changelog_json: str,
        dict_version_hash: str,
        prompt_version: str,
        model: str,
        next_url: str | None = None,
        prev_url: str | None = None,
    ) -> ChapterCacheEntry:
        row = ChapterCacheRow(
            source_key=source_key,
            url=url,
            title=title,
            raw_hash=raw_hash,
            raw_text=raw_text,
            output_text=output_text,
            changelog_json=changelog_json,
            dict_version_hash=dict_version_hash,
            prompt_version=prompt_version,
            model=model,
            next_url=next_url,
            prev_url=prev_url,
        )
        self._session.add(row)
        self._session.flush()
        return _row_to_entry(row)

    def get_by_id(self, chapter_cache_id: int) -> ChapterCacheEntry | None:
        row = self._session.get(ChapterCacheRow, chapter_cache_id)
        return _row_to_entry(row) if row else None

    def touch(self, chapter_cache_id: int) -> None:
        """Mark a chapter as just-read so the library and 'continue reading' stay ordered
        by actual reading activity rather than by when the chapter was first processed."""
        row = self._session.get(ChapterCacheRow, chapter_cache_id)
        if row is not None:
            row.last_read_at = dt.datetime.now(dt.UTC)
            self._session.flush()

    def list_by_series(self, series_id: int) -> list[ChapterCacheEntry]:
        """Chapters of one story in reading order.

        Ordered by the chapter number parsed out of the URL/title where there is one, so a
        story reads 1, 2, 3 even when the chapters were opened out of order; chapters with no
        detectable number keep insertion order at the end. Duplicate cache rows for the same
        chapter (one per dictionary version) collapse to the most recently read.
        """
        stmt = select(ChapterCacheRow).where(ChapterCacheRow.series_id == series_id)
        rows = self._session.execute(stmt).scalars().all()

        best: dict[str, ChapterCacheRow] = {}
        for row in rows:
            current = best.get(row.raw_hash)
            if current is None or _recency(row) > _recency(current):
                best[row.raw_hash] = row

        def sort_key(row: ChapterCacheRow) -> tuple[int, float, int]:
            number = chapter_number(row.url, row.title)
            return (0, number, row.id) if number is not None else (1, 0.0, row.id)

        return [_row_to_entry(row) for row in sorted(best.values(), key=sort_key)]

    def set_title(self, chapter_cache_id: int, title: str) -> None:
        row = self._session.get(ChapterCacheRow, chapter_cache_id)
        if row is not None:
            # A dictionary edit creates a new cache variant for the same raw chapter. Rename
            # every variant so an older row cannot bring the stale/empty title back later.
            self._session.execute(
                update(ChapterCacheRow)
                .where(ChapterCacheRow.raw_hash == row.raw_hash)
                .values(title=title)
            )
            self._session.flush()

    def set_series(self, chapter_cache_id: int, series_id: int | None) -> None:
        row = self._session.get(ChapterCacheRow, chapter_cache_id)
        if row is not None:
            row.series_id = series_id
            self._session.flush()

    def set_navigation(
        self, chapter_cache_id: int, *, next_url: str | None, prev_url: str | None
    ) -> None:
        """Carry chapter navigation onto a row that was rebuilt from stored raw text (a
        dictionary-triggered reprocess), which has no page to re-read the links from."""
        row = self._session.get(ChapterCacheRow, chapter_cache_id)
        if row is not None:
            row.next_url = next_url
            row.prev_url = prev_url
            self._session.flush()

    def list_recent(self, limit: int = 50) -> list[ChapterCacheEntry]:
        """Most recently read chapters first, one entry per chapter.

        The cache is keyed by (raw_text, dictionary, prompt, model), so editing the dictionary
        leaves several rows describing the SAME chapter. A library that listed every row would
        fill up with duplicates of one chapter, so collapse them by raw_hash and keep the row
        that was read most recently. Rows migrated from the pre-library schema have a NULL
        last_read_at, so fall back to created_at to keep them in a sensible order.
        """
        recency = func.coalesce(ChapterCacheRow.last_read_at, ChapterCacheRow.created_at)
        stmt = (
            select(ChapterCacheRow)
            .order_by(recency.desc(), ChapterCacheRow.id.desc())
            .execution_options(yield_per=100)
        )

        seen: set[str] = set()
        entries: list[ChapterCacheEntry] = []
        for row in self._session.execute(stmt).scalars():
            if row.raw_hash in seen:
                continue
            seen.add(row.raw_hash)
            entries.append(_row_to_entry(row))
            if len(entries) >= limit:
                break
        return entries

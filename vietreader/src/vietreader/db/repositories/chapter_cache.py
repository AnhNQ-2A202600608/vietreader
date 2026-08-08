"""ChapterCacheRepo. Cache key per spec §2.4: sha256(raw_text) + dict_version_hash +
prompt_version + model -- changing any component is a cache miss."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from vietreader.db.models import ChapterCacheRow


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


def _row_to_entry(row: ChapterCacheRow) -> ChapterCacheEntry:
    return ChapterCacheEntry(
        id=row.id,
        source_key=row.source_key,
        url=row.url,
        title=row.title,
        raw_hash=row.raw_hash,
        raw_text=row.raw_text,
        output_text=row.output_text,
        changelog_json=row.changelog_json,
        dict_version_hash=row.dict_version_hash,
        prompt_version=row.prompt_version,
        model=row.model,
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
        )
        self._session.add(row)
        self._session.flush()
        return _row_to_entry(row)

    def get_by_id(self, chapter_cache_id: int) -> ChapterCacheEntry | None:
        row = self._session.get(ChapterCacheRow, chapter_cache_id)
        return _row_to_entry(row) if row else None

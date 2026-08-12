"""SQLAlchemy ORM models for the tables in spec §2.4."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class DictionaryEntryRow(Base):
    __tablename__ = "dictionary_entry"
    __table_args__ = (UniqueConstraint("surface", name="uq_dictionary_entry_surface"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    surface: Mapped[str] = mapped_column(String, nullable=False)
    display: Mapped[str] = mapped_column(String, nullable=False)
    policy: Mapped[str] = mapped_column(String, nullable=False)
    replacement: Mapped[str | None] = mapped_column(String, nullable=True)
    candidates: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str] = mapped_column(String, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class DictionaryVersionRow(Base):
    __tablename__ = "dictionary_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SeriesRow(Base):
    """A story: the thing a reader actually follows, grouping many chapters.

    `series_key` is derived from chapter URLs (see core/series.py). Pasted chapters have no
    URL to derive one from, so they stay unattached (chapter_cache.series_id is NULL).
    """

    __tablename__ = "series"
    __table_args__ = (UniqueConstraint("series_key", name="uq_series_series_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_key: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    followed: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_read_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=True, index=True
    )


class ChapterCacheRow(Base):
    __tablename__ = "chapter_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id"), nullable=True, index=True
    )
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    raw_hash: Mapped[str] = mapped_column(String, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    changelog_json: Mapped[str] = mapped_column(Text, nullable=False)
    dict_version_hash: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # Navigation is captured at extraction time so reopening a cached chapter from the library
    # still knows where "next chapter" goes without re-fetching the source page.
    next_url: Mapped[str | None] = mapped_column(String, nullable=True)
    prev_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Nullable so the migration can add it to existing rows (SQLite forbids a CURRENT_TIMESTAMP
    # default on a NOT NULL ADD COLUMN). NULL means "never reopened" -> fall back to created_at.
    last_read_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=True, index=True
    )


class LLMCacheRow(Base):
    __tablename__ = "llm_cache"

    cache_key: Mapped[str] = mapped_column(String, primary_key=True)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReadingPositionRow(Base):
    __tablename__ = "reading_position"
    __table_args__ = (UniqueConstraint("series_key", name="uq_reading_position_series_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_key: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    para_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class FeedbackRow(Base):
    """A note the reader jots down while reading, e.g. "this word was replaced wrongly".

    Anchored to the chapter and paragraph that were on screen, so a note can be acted on later
    without having to remember where it came from. Purely local: nothing is ever sent anywhere.
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_cache_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapter_cache.id"), nullable=True, index=True
    )
    chapter_title: Mapped[str] = mapped_column(String, nullable=False, default="")
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    para_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RunLogRow(Base):
    __tablename__ = "run_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_cache_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapter_cache.id"), nullable=True
    )
    stage: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

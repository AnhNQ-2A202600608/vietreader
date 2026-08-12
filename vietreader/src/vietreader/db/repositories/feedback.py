"""FeedbackRepo: reading notes anchored to a chapter. Local only, nothing is ever sent out."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from vietreader.db.models import FeedbackRow

QUOTE_MAX_CHARS = 300
MESSAGE_MAX_CHARS = 2000


class FeedbackError(ValueError):
    """Raised when a note carries no message."""


@dataclass(frozen=True, slots=True)
class Feedback:
    id: int
    chapter_cache_id: int | None
    chapter_title: str
    url: str | None
    para_index: int | None
    quote: str
    message: str
    resolved: bool
    created_at: dt.datetime | None = None


def _row_to_feedback(row: FeedbackRow) -> Feedback:
    return Feedback(
        id=row.id,
        chapter_cache_id=row.chapter_cache_id,
        chapter_title=row.chapter_title,
        url=row.url,
        para_index=row.para_index,
        quote=row.quote,
        message=row.message,
        resolved=row.resolved,
        created_at=row.created_at,
    )


class FeedbackRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        message: str,
        chapter_cache_id: int | None = None,
        chapter_title: str = "",
        url: str | None = None,
        para_index: int | None = None,
        quote: str = "",
    ) -> Feedback:
        cleaned = message.strip()
        if not cleaned:
            raise FeedbackError("nội dung góp ý không được để trống")

        row = FeedbackRow(
            chapter_cache_id=chapter_cache_id,
            chapter_title=chapter_title[:200],
            url=url,
            para_index=para_index,
            quote=quote.strip()[:QUOTE_MAX_CHARS],
            message=cleaned[:MESSAGE_MAX_CHARS],
        )
        self._session.add(row)
        self._session.flush()
        return _row_to_feedback(row)

    def list(self, *, resolved: bool | None = None, limit: int = 200) -> list[Feedback]:
        stmt = select(FeedbackRow).order_by(FeedbackRow.id.desc()).limit(limit)
        if resolved is not None:
            stmt = stmt.where(FeedbackRow.resolved == resolved)
        return [_row_to_feedback(row) for row in self._session.execute(stmt).scalars()]

    def count_open(self) -> int:
        stmt = select(FeedbackRow).where(FeedbackRow.resolved.is_(False))
        return len(self._session.execute(stmt).scalars().all())

    def set_resolved(self, feedback_id: int, resolved: bool) -> Feedback | None:
        row = self._session.get(FeedbackRow, feedback_id)
        if row is None:
            return None
        row.resolved = resolved
        self._session.flush()
        return _row_to_feedback(row)

    def delete(self, feedback_id: int) -> bool:
        row = self._session.get(FeedbackRow, feedback_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

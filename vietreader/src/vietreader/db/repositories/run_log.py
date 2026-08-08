"""RunLogRepo: structured run_log entries (WARN/ERROR/...) tied to a chapter_cache row."""

from __future__ import annotations

from sqlalchemy.orm import Session

from vietreader.db.models import RunLogRow


class RunLogRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def log(
        self,
        *,
        stage: str,
        level: str,
        message: str,
        chapter_cache_id: int | None = None,
        payload_json: str | None = None,
    ) -> None:
        row = RunLogRow(
            chapter_cache_id=chapter_cache_id,
            stage=stage,
            level=level,
            message=message,
            payload_json=payload_json,
        )
        self._session.add(row)
        self._session.flush()

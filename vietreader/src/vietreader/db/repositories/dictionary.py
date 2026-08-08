"""DictionaryRepo: CRUD over dictionary_entry rows, translating to/from core.DictionaryEntry."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vietreader.core.dictionary import DictionaryEntry, DictionaryEntryError
from vietreader.core.models import Policy
from vietreader.db.models import DictionaryEntryRow


def _row_to_entry(row: DictionaryEntryRow) -> DictionaryEntry:
    return DictionaryEntry(
        id=row.id,
        surface=row.surface,
        display=row.display,
        policy=Policy(row.policy),
        replacement=row.replacement,
        candidates=list(row.candidates or []),
        priority=row.priority,
        note=row.note,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class DictionaryRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self, *, policy: Policy | None = None, search: str | None = None
    ) -> list[DictionaryEntry]:
        stmt = select(DictionaryEntryRow)
        if policy is not None:
            stmt = stmt.where(DictionaryEntryRow.policy == policy.value)
        if search:
            stmt = stmt.where(DictionaryEntryRow.surface.like(f"%{search.lower()}%"))
        stmt = stmt.order_by(DictionaryEntryRow.surface)
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_entry(r) for r in rows]

    def list_enabled(self) -> list[DictionaryEntry]:
        stmt = select(DictionaryEntryRow).where(DictionaryEntryRow.enabled.is_(True))
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_entry(r) for r in rows]

    def get(self, entry_id: int) -> DictionaryEntry | None:
        row = self._session.get(DictionaryEntryRow, entry_id)
        return _row_to_entry(row) if row else None

    def create(
        self,
        *,
        surface: str,
        display: str,
        policy: Policy,
        replacement: str | None = None,
        candidates: list[str] | None = None,
        priority: int = 0,
        note: str = "",
        enabled: bool = True,
    ) -> DictionaryEntry:
        # Validate invariants via the pure core type before touching the DB (id is a placeholder).
        DictionaryEntry(
            id=0,
            surface=surface,
            display=display,
            policy=policy,
            replacement=replacement,
            candidates=candidates or [],
            priority=priority,
            note=note,
            enabled=enabled,
        )
        row = DictionaryEntryRow(
            surface=surface,
            display=display,
            policy=policy.value,
            replacement=replacement,
            candidates=candidates or [],
            priority=priority,
            note=note,
            enabled=enabled,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise DictionaryEntryError(f"surface already exists: {surface!r}") from exc
        return _row_to_entry(row)

    def update(self, entry_id: int, **fields: object) -> DictionaryEntry | None:
        row = self._session.get(DictionaryEntryRow, entry_id)
        if row is None:
            return None
        current = _row_to_entry(row)

        surface = fields.get("surface", current.surface)
        display = fields.get("display", current.display)
        policy = fields.get("policy", current.policy)
        replacement = fields.get("replacement", current.replacement)
        candidates = fields.get("candidates", current.candidates)
        priority = fields.get("priority", current.priority)
        note = fields.get("note", current.note)
        enabled = fields.get("enabled", current.enabled)

        # Validate invariants via the pure core type before touching the DB.
        DictionaryEntry(
            id=entry_id,
            surface=surface,  # type: ignore[arg-type]
            display=display,  # type: ignore[arg-type]
            policy=policy,  # type: ignore[arg-type]
            replacement=replacement,  # type: ignore[arg-type]
            candidates=candidates,  # type: ignore[arg-type]
            priority=priority,  # type: ignore[arg-type]
            note=note,  # type: ignore[arg-type]
            enabled=enabled,  # type: ignore[arg-type]
        )

        row.surface = surface  # type: ignore[assignment]
        row.display = display  # type: ignore[assignment]
        row.policy = policy.value if isinstance(policy, Policy) else policy  # type: ignore[assignment]
        row.replacement = replacement  # type: ignore[assignment]
        row.candidates = candidates  # type: ignore[assignment]
        row.priority = priority  # type: ignore[assignment]
        row.note = note  # type: ignore[assignment]
        row.enabled = enabled  # type: ignore[assignment]

        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise DictionaryEntryError(f"surface already exists: {surface!r}") from exc
        return _row_to_entry(row)

    def delete(self, entry_id: int) -> bool:
        row = self._session.get(DictionaryEntryRow, entry_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

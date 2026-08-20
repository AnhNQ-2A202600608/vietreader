"""Dictionary CRUD + import/export + quick-add (spec §Phase 6)."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from vietreader.api.deps import get_session
from vietreader.core.dictionary import DictionaryEntry, normalize_surface
from vietreader.core.models import Policy
from vietreader.db.repositories.dictionary import DictionaryRepo

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])


class DictionaryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surface: str
    display: str
    policy: Policy
    replacement: str | None
    candidates: list[str]
    priority: int
    note: str
    enabled: bool


class DictionaryEntryCreate(BaseModel):
    surface: str
    display: str
    policy: Policy
    replacement: str | None = None
    candidates: list[str] = []
    priority: int = 0
    note: str = ""
    enabled: bool = True


class DictionaryEntryUpdate(BaseModel):
    surface: str | None = None
    display: str | None = None
    policy: Policy | None = None
    replacement: str | None = None
    candidates: list[str] | None = None
    priority: int | None = None
    note: str | None = None
    enabled: bool | None = None


class QuickAddRequest(BaseModel):
    surface: str
    display: str | None = None
    policy: Policy
    replacement: str | None = None
    candidates: list[str] = []


class ImportRequest(BaseModel):
    entries: list[DictionaryEntryCreate] = []
    csv: str | None = None


class ImportError_(BaseModel):
    surface: str
    error: str


class ImportResponse(BaseModel):
    created: int
    errors: list[ImportError_]


def _to_out(entry: DictionaryEntry) -> DictionaryEntryOut:
    return DictionaryEntryOut(
        id=entry.id,
        surface=entry.surface,
        display=entry.display,
        policy=entry.policy,
        replacement=entry.replacement,
        candidates=entry.candidates,
        priority=entry.priority,
        note=entry.note,
        enabled=entry.enabled,
    )


def _parse_csv(raw: str) -> list[DictionaryEntryCreate]:
    reader = csv.DictReader(io.StringIO(raw))
    parsed: list[DictionaryEntryCreate] = []
    for row in reader:
        candidates_raw = row.get("candidates") or ""
        parsed.append(
            DictionaryEntryCreate(
                surface=row["surface"],
                display=row.get("display") or row["surface"],
                policy=Policy(row["policy"]),
                replacement=row.get("replacement") or None,
                candidates=[c for c in candidates_raw.split("|") if c],
                priority=int(row.get("priority") or 0),
                note=row.get("note") or "",
                enabled=(row.get("enabled") or "true").lower() != "false",
            )
        )
    return parsed


@router.get("", response_model=list[DictionaryEntryOut])
async def list_dictionary(
    policy: Policy | None = None,
    search: str | None = None,
    session: Session = Depends(get_session),
) -> list[DictionaryEntryOut]:
    repo = DictionaryRepo(session)
    return [_to_out(e) for e in repo.list(policy=policy, search=search)]


@router.post("", response_model=DictionaryEntryOut, status_code=201)
async def create_dictionary_entry(
    body: DictionaryEntryCreate, session: Session = Depends(get_session)
) -> DictionaryEntryOut:
    repo = DictionaryRepo(session)
    entry = repo.create(**body.model_dump())
    session.commit()
    return _to_out(entry)


@router.patch("/{entry_id}", response_model=DictionaryEntryOut)
async def update_dictionary_entry(
    entry_id: int, body: DictionaryEntryUpdate, session: Session = Depends(get_session)
) -> DictionaryEntryOut:
    repo = DictionaryRepo(session)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = repo.update(entry_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"dictionary entry {entry_id} not found")
    session.commit()
    return _to_out(updated)


@router.delete("/{entry_id}", status_code=204, response_model=None)
async def delete_dictionary_entry(entry_id: int, session: Session = Depends(get_session)) -> None:
    repo = DictionaryRepo(session)
    if not repo.delete(entry_id):
        raise HTTPException(status_code=404, detail=f"dictionary entry {entry_id} not found")
    session.commit()


@router.post("/quick-add", response_model=DictionaryEntryOut, status_code=201)
async def quick_add(
    body: QuickAddRequest, session: Session = Depends(get_session)
) -> DictionaryEntryOut:
    repo = DictionaryRepo(session)
    display = (body.display or body.surface).strip()
    entry = repo.create(
        surface=normalize_surface(body.surface.strip()),
        display=display,
        policy=body.policy,
        replacement=body.replacement,
        candidates=body.candidates,
    )
    session.commit()
    return _to_out(entry)


@router.post("/import", response_model=ImportResponse)
async def import_dictionary(
    body: ImportRequest, session: Session = Depends(get_session)
) -> ImportResponse:
    repo = DictionaryRepo(session)
    entries_in = list(body.entries)
    if body.csv:
        entries_in += _parse_csv(body.csv)

    created = 0
    errors: list[ImportError_] = []
    for item in entries_in:
        try:
            repo.create(**item.model_dump())
            session.commit()  # commit per row so one bad row can't roll back earlier successes
            created += 1
        except Exception as exc:  # collect per-row errors instead of aborting the whole batch
            session.rollback()
            errors.append(ImportError_(surface=item.surface, error=str(exc)))
    return ImportResponse(created=created, errors=errors)


@router.get("/export", response_model=list[DictionaryEntryOut])
async def export_dictionary(session: Session = Depends(get_session)) -> list[DictionaryEntryOut]:
    repo = DictionaryRepo(session)
    return [_to_out(e) for e in repo.list()]

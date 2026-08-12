"""GET/PUT /api/position/{series_key} -- reading position."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from vietreader.api.deps import get_session
from vietreader.db.repositories.position import PositionRepo

router = APIRouter(prefix="/api/position", tags=["position"])


class PositionOut(BaseModel):
    series_key: str
    url: str
    para_index: int


class PositionUpdate(BaseModel):
    url: str
    para_index: int


def _to_out(position) -> PositionOut:  # type: ignore[no-untyped-def]
    return PositionOut(
        series_key=position.series_key, url=position.url, para_index=position.para_index
    )


# `:path` because a series_key is a URL and therefore contains slashes. Without it the route
# never matches for any chapter read from a URL -- percent-encoding does not help, since the
# path is decoded before matching -- and reading positions silently fail to save or restore.
@router.get("/{series_key:path}", response_model=PositionOut)
async def get_position(series_key: str, session: Session = Depends(get_session)) -> PositionOut:
    repo = PositionRepo(session)
    position = repo.get(series_key)
    if position is None:
        raise HTTPException(status_code=404, detail=f"no reading position for {series_key!r}")
    return _to_out(position)


@router.put("/{series_key:path}", response_model=PositionOut)
async def put_position(
    series_key: str, body: PositionUpdate, session: Session = Depends(get_session)
) -> PositionOut:
    repo = PositionRepo(session)
    position = repo.upsert(series_key, body.url, body.para_index)
    session.commit()
    return _to_out(position)

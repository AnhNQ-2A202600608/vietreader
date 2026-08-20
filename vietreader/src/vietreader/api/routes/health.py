"""Cheap liveness plus database-backed readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from vietreader.api.deps import get_session

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.head("/health", include_in_schema=False)
async def health_head() -> None:
    return None


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def ready(session: Session = Depends(get_session)) -> HealthResponse | JSONResponse:
    """Only report ready when the database accepts a trivial query within pool timeouts."""
    try:
        session.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return HealthResponse(status="ready")

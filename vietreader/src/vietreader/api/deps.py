"""FastAPI dependencies: DB session per request + shared app state (settings/provider/etc.)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from vietreader.extraction.fetcher import Fetcher
from vietreader.extraction.registry import Registry
from vietreader.llm.provider import LLMProvider
from vietreader.settings import Settings


@dataclass
class AppState:
    settings: Settings
    session_factory: sessionmaker[Session]
    provider: LLMProvider
    registry: Registry
    fetcher: Fetcher


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state  # type: ignore[no-any-return]


def get_session(request: Request) -> Iterator[Session]:
    state: AppState = request.app.state.app_state
    session = state.session_factory()
    try:
        yield session
    finally:
        session.close()

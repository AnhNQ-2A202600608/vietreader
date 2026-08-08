"""FastAPI app factory + route registration."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from vietreader.api.deps import AppState
from vietreader.api.errors import register_exception_handlers
from vietreader.api.routes import chapters, dictionary, health, position, web
from vietreader.db.base import create_db_engine, create_session_factory
from vietreader.db.models import Base
from vietreader.extraction.fetcher import Fetcher
from vietreader.extraction.registry import Registry
from vietreader.llm.anthropic import AnthropicProvider
from vietreader.llm.provider import LLMProvider
from vietreader.settings import Settings, get_settings


def create_app(settings: Settings | None = None, provider: LLMProvider | None = None) -> FastAPI:
    settings = settings or get_settings()

    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)  # dev convenience; production runs `alembic upgrade head`
    session_factory = create_session_factory(engine)

    app_state = AppState(
        settings=settings,
        session_factory=session_factory,
        provider=provider
        or AnthropicProvider(api_key=settings.llm_api_key, model=settings.llm_model),
        registry=Registry(),
        fetcher=Fetcher(
            user_agent=settings.fetch_user_agent,
            timeout=settings.fetch_timeout_seconds,
            max_retries=settings.fetch_max_retries,
            delay_seconds=settings.fetch_delay_seconds,
        ),
    )

    app = FastAPI(title="VietReader API", version="0.1.0")
    app.state.app_state = app_state

    static_dir = Path(__file__).resolve().parents[1] / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(health.router)
    app.include_router(chapters.router)
    app.include_router(dictionary.router)
    app.include_router(position.router)
    app.include_router(web.router)

    register_exception_handlers(app)
    return app


app = create_app()

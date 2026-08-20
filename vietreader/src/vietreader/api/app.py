"""FastAPI app factory + route registration."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from vietreader.api.deps import AppState
from vietreader.api.errors import register_exception_handlers
from vietreader.api.routes import chapters, dictionary, health, position, web
from vietreader.api.security import register_security_middleware
from vietreader.db.base import create_db_engine, create_session_factory
from vietreader.db.models import Base
from vietreader.extraction.fetcher import Fetcher
from vietreader.extraction.registry import Registry
from vietreader.llm.anthropic import AnthropicProvider
from vietreader.llm.provider import LLMProvider
from vietreader.settings import Settings, get_settings


def create_app(settings: Settings | None = None, provider: LLMProvider | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    engine = create_db_engine(settings.database_url)
    if settings.auto_create_schema:
        Base.metadata.create_all(engine)  # local/test convenience
    session_factory = create_session_factory(engine)

    app_state = AppState(
        settings=settings,
        session_factory=session_factory,
        provider=provider
        or AnthropicProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            prompt_version=settings.llm_prompt_version,
        ),
        registry=Registry(),
        fetcher=Fetcher(
            user_agent=settings.fetch_user_agent,
            timeout=settings.fetch_timeout_seconds,
            max_retries=settings.fetch_max_retries,
            delay_seconds=settings.fetch_delay_seconds,
            verify_tls=settings.fetch_verify_tls,
            allow_private_networks=settings.fetch_allow_private_networks,
        ),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="VietReader API", version="0.1.0", lifespan=lifespan)
    app.state.app_state = app_state
    register_security_middleware(app, settings)

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

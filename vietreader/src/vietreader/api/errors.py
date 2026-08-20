"""Unified error envelope: {"error": {"code", "message", "hint"}}."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from vietreader.core.dictionary import DictionaryEntryError
from vietreader.extraction.base import ExtractionError
from vietreader.extraction.fetcher import FetchError
from vietreader.extraction.urls import SourceURLError

PASTE_HINT = "Thử dán trực tiếp nội dung chương"


def _envelope(code: str, message: str, hint: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "hint": hint}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ExtractionError)
    async def _extraction_error(request: Request, exc: ExtractionError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content=_envelope("extraction_error", str(exc), PASTE_HINT)
        )

    @app.exception_handler(FetchError)
    async def _fetch_error(request: Request, exc: FetchError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content=_envelope(exc.code, str(exc), PASTE_HINT)
        )

    @app.exception_handler(SourceURLError)
    async def _source_url_error(request: Request, exc: SourceURLError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("invalid_url", str(exc), "Kiểm tra lại địa chỉ chương"),
        )

    @app.exception_handler(DictionaryEntryError)
    async def _dictionary_error(request: Request, exc: DictionaryEntryError) -> JSONResponse:
        return JSONResponse(status_code=400, content=_envelope("dictionary_error", str(exc)))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("invalid_request", str(exc.errors())),
        )

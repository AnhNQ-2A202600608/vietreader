"""Small security boundary for the single-user web application.

Authentication is optional for local development and mandatory when ``require_auth`` is set.
Unsafe browser requests are also restricted to the same origin to prevent cross-site form
submissions from mutating the dictionary, notes, or reading state.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vietreader.settings import Settings

_PUBLIC_PATHS = {"/api/health", "/api/ready"}
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _error(status_code: int, code: str, message: str, **headers: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "hint": None}},
        headers=headers,
    )


def _valid_basic_auth(request: Request, username: str, password: str) -> bool:
    header = request.headers.get("authorization", "")
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    supplied_username, separator, supplied_password = decoded.partition(":")
    return bool(separator) and secrets.compare_digest(
        supplied_username, username
    ) and secrets.compare_digest(supplied_password, password)


def _same_origin(request: Request) -> bool:
    fetch_site = request.headers.get("sec-fetch-site", "").lower()
    if fetch_site == "cross-site":
        return False

    origin = request.headers.get("origin")
    if not origin:
        # CLI/API clients do not normally send Origin. Browser cross-site navigations are
        # caught by Sec-Fetch-Site on modern browsers.
        return True
    if origin == "null":
        return False
    return urlsplit(origin).netloc.lower() == request.headers.get("host", "").lower()


def register_security_middleware(app: FastAPI, settings: Settings) -> None:
    auth_enabled = bool(settings.auth_username and settings.auth_password)

    @app.middleware("http")
    async def _security_boundary(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in _UNSAFE_METHODS and not _same_origin(request):
            return _error(403, "csrf_rejected", "cross-site state-changing request rejected")

        path_is_public = request.url.path in _PUBLIC_PATHS or request.url.path.startswith(
            "/static/"
        )
        if not path_is_public and auth_enabled and not _valid_basic_auth(
            request, settings.auth_username, settings.auth_password
        ):
            return _error(
                401,
                "authentication_required",
                "authentication required",
                **{"WWW-Authenticate": 'Basic realm="VietReader", charset="UTF-8"'},
            )

        response = await call_next(request)
        if not path_is_public:
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

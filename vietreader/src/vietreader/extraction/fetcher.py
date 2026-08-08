"""httpx-based fetcher: timeout, retry, configurable User-Agent, polite delay between requests."""

from __future__ import annotations

import asyncio
import time

import httpx


class FetchError(RuntimeError):
    """Raised when a chapter page cannot be fetched. Callers should offer the paste fallback."""


class Fetcher:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 15.0,
        max_retries: int = 2,
        delay_seconds: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._timeout = timeout
        self._max_retries = max_retries
        self._delay_seconds = delay_seconds
        self._default_transport = transport
        self._last_request_at: float | None = None

    async def fetch(self, url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> str:
        await self._respect_delay()
        headers = {"User-Agent": self._user_agent}
        last_error: Exception | None = None
        transport = transport or self._default_transport

        async with httpx.AsyncClient(timeout=self._timeout, transport=transport) as client:
            for _attempt in range(self._max_retries + 1):
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPError as exc:
                    last_error = exc
                    continue

        raise FetchError(
            f"failed to fetch {url!r} after {self._max_retries + 1} attempt(s): {last_error}. "
            "Thử dán trực tiếp nội dung chương (paste fallback)."
        ) from last_error

    async def _respect_delay(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self._delay_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request_at = time.monotonic()

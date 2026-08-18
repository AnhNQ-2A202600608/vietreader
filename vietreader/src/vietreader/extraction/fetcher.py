"""httpx-based fetcher: timeout, retry, configurable User-Agent, polite delay between requests."""

from __future__ import annotations

import asyncio
import time

import httpx

DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class FetchError(RuntimeError):
    """Raised when a chapter page cannot be fetched. Callers should offer the paste fallback."""


class Fetcher:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_BROWSER_UA,
        timeout: float = 20.0,
        max_retries: int = 2,
        delay_seconds: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._user_agent = (
            user_agent
            if ("Mozilla" in user_agent or "Chrome" in user_agent)
            else DEFAULT_BROWSER_UA
        )
        self._timeout = timeout
        self._max_retries = max_retries
        self._delay_seconds = delay_seconds
        self._default_transport = transport
        self._last_request_at: float | None = None

    async def fetch(self, url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> str:
        await self._respect_delay()
        headers = {**DEFAULT_HEADERS, "User-Agent": self._user_agent}
        last_error: Exception | None = None
        transport = transport or self._default_transport

        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=transport,
            follow_redirects=True,
            verify=False,
        ) as client:
            for _attempt in range(self._max_retries + 1):
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPError as exc:
                    last_error = exc
                    continue

        raise FetchError(
            f"Không thể tải trang {url!r}: {last_error}. "
            "Bạn có thể sao chép và dán trực tiếp nội dung chương vào ô bên dưới."
        ) from last_error

    async def _respect_delay(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self._delay_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request_at = time.monotonic()

"""httpx-based fetcher: timeout, retry, configurable User-Agent, polite delay between requests."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

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

MAX_REDIRECTS = 5


class FetchError(RuntimeError):
    """Raised when a chapter page cannot be fetched. Callers should offer the paste fallback."""

    def __init__(self, message: str, *, code: str = "fetch_failed") -> None:
        super().__init__(message)
        self.code = code


_NO_RETRY_STATUSES = {400, 401, 403, 404, 405, 410, 451}


def _status_error(response: httpx.Response) -> FetchError | None:
    status = response.status_code
    if status not in _NO_RETRY_STATUSES:
        return None
    if status in {401, 403}:
        return FetchError(
            f"Trang nguồn từ chối truy cập tự động (HTTP {status}).",
            code="blocked_by_site",
        )
    if status == 404:
        return FetchError("Không tìm thấy trang ở địa chỉ này (HTTP 404).", code="not_found")
    if status == 410:
        return FetchError("Trang nguồn đã bị gỡ (HTTP 410).", code="not_found")
    return FetchError(f"Trang nguồn trả về HTTP {status}.", code="request_rejected")


def _looks_like_challenge(html: str) -> bool:
    sample = html[:50_000].lower()
    signals = ("cf-chl-", "just a moment...", "captcha", "challenge-platform")
    return sum(signal in sample for signal in signals) >= 2


class Fetcher:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_BROWSER_UA,
        timeout: float = 20.0,
        max_retries: int = 2,
        delay_seconds: float = 0.5,
        verify_tls: bool = True,
        allow_private_networks: bool = False,
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
        self._verify_tls = verify_tls
        self._allow_private_networks = allow_private_networks
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
            follow_redirects=False,
            verify=self._verify_tls,
        ) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    current_url = url
                    for redirect_count in range(MAX_REDIRECTS + 1):
                        await self._validate_target(
                            current_url, resolve_dns=transport is None
                        )
                        response = await client.get(current_url, headers=headers)
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location or redirect_count == MAX_REDIRECTS:
                                raise FetchError(
                                    "trang chuyển hướng quá nhiều lần hoặc thiếu Location"
                                )
                            current_url = urljoin(str(response.url), location)
                            continue
                        immediate_error = _status_error(response)
                        if immediate_error is not None:
                            raise immediate_error
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").lower()
                        if content_type and not any(
                            allowed in content_type
                            for allowed in ("text/html", "application/xhtml+xml", "text/plain")
                        ):
                            raise FetchError(
                                "Liên kết không trỏ tới một trang văn bản có thể đọc.",
                                code="unsupported_content",
                            )
                        html = response.text
                        if _looks_like_challenge(html):
                            raise FetchError(
                                "Trang nguồn đang yêu cầu xác minh trình duyệt hoặc CAPTCHA.",
                                code="blocked_by_site",
                            )
                        return html
                    raise FetchError("trang chuyển hướng quá nhiều lần")
                except FetchError:
                    # Invalid/private URLs, definite 4xx responses and browser challenges do
                    # not improve on retry. Returning immediately avoids a long fake loading.
                    raise
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt < self._max_retries:
                        await asyncio.sleep(min(0.35 * (attempt + 1), 1.0))
                    continue

        if isinstance(last_error, httpx.TimeoutException):
            raise FetchError(
                "Trang nguồn phản hồi quá chậm và đã hết thời gian chờ.", code="timeout"
            ) from last_error
        if isinstance(last_error, httpx.HTTPStatusError) and last_error.response.status_code == 429:
            raise FetchError(
                "Trang nguồn đang giới hạn số lần truy cập (HTTP 429).",
                code="rate_limited",
            ) from last_error
        raise FetchError(
            "Không thể kết nối tới trang nguồn sau nhiều lần thử.", code="connection_failed"
        ) from last_error

    async def _validate_target(self, url: str, *, resolve_dns: bool) -> None:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise FetchError("chỉ hỗ trợ URL http/https hợp lệ", code="invalid_url")
        if parts.username or parts.password:
            raise FetchError("URL không được chứa thông tin đăng nhập", code="invalid_url")
        if self._allow_private_networks:
            return

        hostname = parts.hostname.lower().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"}:
            raise FetchError("không cho phép tải địa chỉ nội bộ", code="blocked_url")

        addresses: set[str] = set()
        try:
            addresses.add(str(ipaddress.ip_address(hostname)))
        except ValueError:
            if resolve_dns:
                try:
                    port = parts.port or (443 if parts.scheme == "https" else 80)
                    infos = await asyncio.to_thread(socket.getaddrinfo, hostname, port)
                except socket.gaierror as exc:
                    raise FetchError(
                        f"không phân giải được tên miền {hostname!r}", code="dns_failed"
                    ) from exc
                addresses.update(str(info[4][0]) for info in infos)

        for raw_address in addresses:
            address = ipaddress.ip_address(raw_address)
            if not address.is_global:
                raise FetchError(
                    "không cho phép tải địa chỉ nội bộ hoặc không công khai",
                    code="blocked_url",
                )

    async def _respect_delay(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self._delay_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request_at = time.monotonic()

"""Small, conservative cleanup for source URLs pasted by a reader."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


class SourceURLError(ValueError):
    """Raised when a pasted value cannot safely be interpreted as a web URL."""


_INVISIBLE = str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff")
_MARKDOWN_LINK = re.compile(r"^\[[^\]]+\]\((https?://[^\s)]+)\)$", re.IGNORECASE)


def normalize_source_url(raw: str) -> str:
    """Accept the common URL shapes people paste without guessing beyond the hostname.

    We intentionally do not remove query parameters or trailing punctuation: both can be a
    meaningful part of a chapter URL.  The cleanup only removes invisible copy/paste marks,
    unwraps Markdown/angle brackets and supplies ``https://`` for a domain-like value.
    """
    value = raw.translate(_INVISIBLE).strip()
    markdown = _MARKDOWN_LINK.fullmatch(value)
    if markdown:
        value = markdown.group(1)
    elif value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()

    if value.startswith("//"):
        value = f"https:{value}"
    elif "://" not in value:
        first_part = value.split("/", 1)[0]
        if "." in first_part and " " not in first_part:
            value = f"https://{value}"

    try:
        parts = urlsplit(value)
        port = parts.port  # Force validation of malformed ports while the error is friendly.
    except ValueError as exc:
        raise SourceURLError("Địa chỉ web không hợp lệ.") from exc

    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise SourceURLError("Hãy nhập một địa chỉ web bắt đầu bằng http:// hoặc https://.")
    if any(char.isspace() for char in parts.netloc):
        raise SourceURLError("Tên miền không được chứa khoảng trắng.")

    host = parts.hostname.encode("idna").decode("ascii")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    auth = ""
    if parts.username is not None:
        auth = parts.username
        if parts.password is not None:
            auth += f":{parts.password}"
        auth += "@"
    netloc = f"{auth}{host}{f':{port}' if port is not None else ''}"
    return urlunsplit(
        (parts.scheme.lower(), netloc, parts.path or "/", parts.query, parts.fragment)
    )

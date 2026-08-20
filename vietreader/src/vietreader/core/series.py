"""Grouping chapters into a series. Pure string logic, no I/O.

A chapter URL on a Vietnamese novel site almost always looks like
``<host>/<ten-truyen>/<chuong-n>``, so the series is simply the chapter URL with its last
path segment removed. That heuristic is deliberately conservative: when a URL is too shallow
to tell a series apart from the site itself, no series is claimed and the chapter stays
standalone, rather than lumping every chapter on a host into one fake series.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# "chuong-5", "chapter 12", "chap.7", "ch-15" -- the numbering styles these sites actually use.
#
# A bare "c" is deliberately NOT accepted: URLs with Vietnamese diacritics are percent-encoded
# and contain sequences like "%C3", where "c" + "3" would be read as "chapter 3" on a page that
# has nothing to do with chapters. The lookbehind stops the keyword matching inside a longer word.
_CHAPTER_NUMBER = re.compile(
    r"(?<![a-zA-Z])(?:chuong|chương|chapter|chap|ch)[\s\-_.]*(\d+)",
    re.IGNORECASE,
)

_TITLE_LINE = re.compile(
    r"^(?:chương|chapter|chap|hồi|quyển|tập|phần|mở đầu|lời tựa|ngoại truyện)\b"
    r"|^đệ\s+.{1,30}\s+chương\b|^第.{1,16}[章节回卷]",
    re.IGNORECASE,
)


def _path_segments(url: str) -> list[str]:
    return [segment for segment in urlsplit(url).path.split("/") if segment]


def derive_series_key(url: str | None) -> str | None:
    """Return a stable key identifying the series a chapter URL belongs to, or None.

    None means "cannot tell" -- the caller should treat the chapter as standalone rather than
    guessing. Query strings and fragments are dropped so ``?page=2`` never splits a series.
    """
    if not url:
        return None

    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None

    segments = _path_segments(url)
    if len(segments) < 2:
        # e.g. https://site.com/chuong-5 -- the series would be the whole host. Too coarse.
        return None

    return f"{parts.scheme}://{parts.netloc}/" + "/".join(segments[:-1])


def series_title_from_key(series_key: str) -> str:
    """A readable default name for a series, taken from its URL slug.

    Only a starting point -- the reader can rename a series afterwards.
    """
    segments = _path_segments(series_key)
    slug = segments[-1] if segments else urlsplit(series_key).netloc
    words = re.split(r"[-_]+", slug.strip())
    pretty = " ".join(word for word in words if word).strip()
    return pretty.title() if pretty else series_key


def _looks_like_opaque_id(token: str) -> bool:
    """Đuôi sinh ngẫu nhiên trong slug, ví dụ 'ZcW3zMQsREKQ9AAh' — không phải chữ của tiêu đề."""
    return len(token) >= 8 and any(c.islower() for c in token) and any(c.isupper() for c in token)


def _slug_words_after_number(url: str) -> str:
    """Phần mô tả còn lại trong slug sau số chương: 'chuong-3-tai-ach-Xk9' -> 'tai ach'."""
    segments = _path_segments(url)
    if not segments:
        return ""

    tokens = re.split(r"[-_]+", segments[-1])
    for index, token in enumerate(tokens):
        if token.isdigit():
            rest = [t for t in tokens[index + 1 :] if t and not _looks_like_opaque_id(t)]
            return " ".join(rest)
    return ""


def chapter_display_title(title: str, url: str | None) -> str:
    """Tên chương để hiển thị.

    Nhiều site truyện đặt thẻ tiêu đề trang là TÊN BỘ TRUYỆN, nên mọi chương trích ra đều trùng
    tên nhau và danh sách chương nhìn như bị lưu trùng lặp. Khi tiêu đề không hề nhắc tới số
    chương mà URL thì có, lấy theo URL để các chương phân biệt được với nhau.
    """
    if not url:
        return title

    number = chapter_number(url)
    if number is None:
        return title

    index = int(number)
    if re.search(rf"\b{index}\b", title):
        return title  # tiêu đề đã nói rõ chương mấy -> tin nó

    words = _slug_words_after_number(url)
    return f"Chương {index} — {words.capitalize()}" if words else f"Chương {index}"


def infer_chapter_title(
    title: str | None, url: str | None, paragraphs: list[str] | tuple[str, ...]
) -> str:
    """Return a useful title even when an extractor/cache row left it blank.

    Pasted chapters commonly contain their title as the first line while the optional title
    input is left empty.  Older generic extractions can have the same shape when a site's title
    lives outside the small set of known selectors.  Prefer explicit metadata, then a strongly
    title-like opening paragraph, and finally the chapter number encoded in the URL.
    """

    def compact(value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip().lstrip("# ").strip()

    explicit = compact(title)
    if explicit:
        return chapter_display_title(explicit, url)

    opening = [compact(paragraph) for paragraph in paragraphs[:3] if compact(paragraph)]
    for candidate in opening:
        if len(candidate) <= 160 and (
            _TITLE_LINE.search(candidate) or chapter_number(candidate) is not None
        ):
            return candidate

    # Also accept a short heading followed by clearly longer prose. This recovers headings such
    # as "Gặp lại" without treating ordinary first sentences or dialogue as titles.
    if len(opening) >= 2:
        first, second = opening[0], opening[1]
        sentence_ending = (".", "!", "?", "…", ";", ":", "\"", "”")
        if (
            2 <= len(first) <= 80
            and len(second) >= max(80, len(first) * 2)
            and not first.endswith(sentence_ending)
        ):
            return first

    return chapter_display_title("", url)


def chapter_number(*sources: str | None) -> float | None:
    """Best-effort chapter number pulled from a URL slug or title, for ordering a series.

    Returns None when nothing numeric is found, letting callers fall back to insertion order
    instead of inventing an order.
    """
    for source in sources:
        if not source:
            continue
        match = _CHAPTER_NUMBER.search(source)
        if match:
            return float(match.group(1))
    return None

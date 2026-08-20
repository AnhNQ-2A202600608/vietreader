"""Server-rendered reader UI (Jinja2 + HTMX): home, reader, dictionary manager, settings."""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from vietreader.api.deps import AppState, get_app_state, get_session
from vietreader.api.routes.dictionary import _parse_csv
from vietreader.core.dictionary import CompiledDictionary
from vietreader.core.models import Change, Policy
from vietreader.db.repositories.chapter_cache import ChapterCacheRepo
from vietreader.db.repositories.dictionary import DictionaryRepo
from vietreader.db.repositories.dictionary_version import DictionaryVersionRepo
from vietreader.db.repositories.feedback import FeedbackError, FeedbackRepo
from vietreader.db.repositories.llm_cache import LLMCacheRepo
from vietreader.db.repositories.position import PositionRepo
from vietreader.db.repositories.run_log import RunLogRepo
from vietreader.db.repositories.series import SeriesRepo, link_chapter_to_series
from vietreader.extraction.base import ExtractionError
from vietreader.extraction.fetcher import FetchError
from vietreader.extraction.urls import SourceURLError, normalize_source_url
from vietreader.pipeline.process_chapter import process_chapter
from vietreader.web.rendering import render_paragraphs_html

router = APIRouter(tags=["web"])
logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "web" / "templates"


def _reader_context_processor(request: Request) -> dict:
    """Đưa tên người đọc vào MỌI template, để không phải nhắc lại ở từng route."""
    settings = request.app.state.app_state.settings
    return {"reader_name": settings.reader_name}


templates = Jinja2Templates(
    directory=str(_TEMPLATES_DIR), context_processors=[_reader_context_processor]
)


RECENT_ON_HOME = 5
LIBRARY_PAGE_SIZE = 50


def _greeting(hour: int) -> tuple[str, str, str]:
    """(lời chào, câu phụ, tâm trạng linh vật) theo giờ trên máy đang chạy app."""
    if 5 <= hour < 11:
        return ("Chào buổi sáng", "Hôm nay đọc gì đây?", "happy")
    if 11 <= hour < 14:
        return ("Buổi trưa rồi", "Nghỉ tay đọc vài chương nhé.", "reading")
    if 14 <= hour < 18:
        return ("Chào buổi chiều", "Mây chờ ở đây nãy giờ.", "reading")
    if 18 <= hour < 22:
        return ("Chào buổi tối", "Giờ đẹp nhất để đọc truyện.", "happy")
    return ("Khuya rồi", "Đọc một chương nữa thôi rồi ngủ nha.", "sleepy")


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request, session=Depends(get_session)  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    recent = ChapterCacheRepo(session).list_recent(limit=RECENT_ON_HOME)
    series_repo = SeriesRepo(session)
    latest = recent[0] if recent else None
    greeting, greeting_sub, greeting_mood = _greeting(dt.datetime.now().hour)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "greeting": greeting,
            "greeting_sub": greeting_sub,
            "greeting_mood": greeting_mood,
            "continue_chapter": latest,
            "continue_series": (
                series_repo.get(latest.series_id)
                if latest is not None and latest.series_id is not None
                else None
            ),
            "recent": recent[1:],
            "open_feedback": FeedbackRepo(session).count_open(),
        },
    )


BATCH_MAX = 40


def _parse_urls(raw: str) -> list[str]:
    """Mỗi dòng một URL. Bỏ dòng trống, bỏ trùng, giữ nguyên thứ tự người dùng dán vào."""
    seen: set[str] = set()
    urls: list[str] = []
    for line in raw.splitlines():
        try:
            url = normalize_source_url(line)
        except SourceURLError:
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls[:BATCH_MAX]


def _read_error_context(exc: Exception, url: str) -> dict[str, object]:
    """Turn low-level fetch/parser failures into useful next steps for a reader."""
    title = "Chưa mở được chương này"
    message = "VietReader chưa thể lấy nội dung từ liên kết vừa nhập."
    hint = "Bạn có thể thử lại, hoặc dán nội dung chương để đọc ngay."
    can_retry = bool(url)

    if isinstance(exc, SourceURLError):
        title = "Liên kết chưa đúng"
        message = str(exc)
        hint = "Ví dụ: truyen.example/chuong-12 — VietReader sẽ tự thêm https://."
        can_retry = False
    elif isinstance(exc, FetchError):
        if exc.code == "blocked_by_site":
            title = "Trang nguồn đang chặn đọc tự động"
            message = (
                "Liên kết vẫn có thể mở trong trình duyệt, "
                "nhưng trang không cho máy chủ lấy chữ."
            )
            hint = "Mở trang nguồn, sao chép phần nội dung chương rồi chọn “Dán nội dung”."
            can_retry = False
        elif exc.code == "not_found":
            title = "Không tìm thấy trang"
            message = "Địa chỉ này trả về 404 hoặc nội dung đã được gỡ."
            hint = "Kiểm tra lại số chương và phần cuối của liên kết."
            can_retry = False
        elif exc.code == "timeout":
            message = "Trang nguồn phản hồi quá chậm. Dữ liệu của bạn chưa bị mất."
        elif exc.code == "rate_limited":
            message = "Trang nguồn đang giới hạn truy cập. Hãy chờ một chút rồi thử lại."
        elif exc.code == "dns_failed":
            title = "Không tìm thấy tên miền"
            message = "Tên miền trong liên kết không phân giải được."
            hint = "Kiểm tra lỗi chính tả ở phần tên website."
            can_retry = False
        elif exc.code in {"blocked_url", "invalid_url", "unsupported_content"}:
            title = "Không thể dùng liên kết này"
            message = str(exc).capitalize()
            can_retry = False
    elif isinstance(exc, ExtractionError):
        title = "Đã tải trang nhưng không tìm thấy nội dung chương"
        message = "Bố cục của website này chưa được VietReader nhận diện đúng."
        hint = "Dán phần chữ của chương; không cần dán menu, quảng cáo hoặc bình luận."
        can_retry = False
    elif isinstance(exc, ValueError):
        title = "Chưa có nội dung để đọc"
        message = "Hãy nhập một liên kết hoặc dán nội dung chương."
        can_retry = False

    return {
        "error_title": title,
        "error_message": message,
        "error_hint": hint,
        "error_detail": str(exc),
        "can_retry": can_retry,
    }


@router.get("/batch", response_class=HTMLResponse)
async def batch_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "batch.html", {"max_urls": BATCH_MAX})


@router.post("/batch", response_class=HTMLResponse)
async def batch_start(request: Request, urls: str = Form("")) -> HTMLResponse:
    """Nhận danh sách URL rồi dựng hàng đợi. Việc xử lý do /batch/step làm, mỗi lần một URL."""
    queue = _parse_urls(urls)
    return templates.TemplateResponse(
        request, "_batch_queue.html", {"queue": queue, "total": len(queue)}
    )


@router.post("/batch/step", response_class=HTMLResponse)
async def batch_step(
    request: Request,
    urls: str = Form(""),
    done: int = Form(0),
    total: int = Form(0),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
    state: AppState = Depends(get_app_state),
) -> HTMLResponse:
    """Xử lý ĐÚNG MỘT url rồi trả về dòng kết quả kèm mồi cho url kế tiếp.

    Làm từng cái một thay vì gộp một request dài: fetcher có delay lịch sự giữa các trang nên
    một mẻ vài chục chương sẽ chạy cả phút — đủ để trình duyệt hoặc reverse proxy cắt ngang.
    Cách này còn cho thấy tiến độ, và một URL hỏng không kéo đổ cả mẻ.
    """
    queue = _parse_urls(urls)
    if not queue:
        return templates.TemplateResponse(request, "_batch_row.html", {"finished": True})

    current, remaining = queue[0], queue[1:]
    row: dict = {"url": current, "done": done + 1, "total": total or len(queue)}

    try:
        result = await _run_process(session, state, url=current, raw_text=None, title=None)
        series = link_chapter_to_series(
            session,
            chapter_cache_id=result.chapter_cache_id,
            url=current,
            title=result.chapter.title,
        )
        session.commit()

        row["ok"] = True
        row["title"] = result.chapter.title
        row["chapter_id"] = result.chapter_cache_id
        row["series"] = series
        # from_cache nghĩa là chương này đã xử lý trước đó rồi, chỉ gắn lại vào bộ.
        row["already_had"] = result.stats.from_cache
    except Exception as exc:  # một URL hỏng không được làm đổ cả mẻ
        session.rollback()
        row["ok"] = False
        row["error"] = str(exc).split(".")[0][:160]

    row["remaining"] = "\n".join(remaining)
    row["finished"] = not remaining
    return templates.TemplateResponse(request, "_batch_row.html", row)


@router.get("/library", response_class=HTMLResponse)
async def library(
    request: Request, session=Depends(get_session)  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    """Stories first, then the chapters that belong to no story (pasted text)."""
    series = SeriesRepo(session).list_recent(limit=LIBRARY_PAGE_SIZE)
    standalone = [
        chapter
        for chapter in ChapterCacheRepo(session).list_recent(limit=LIBRARY_PAGE_SIZE)
        if chapter.series_id is None
    ]
    return templates.TemplateResponse(
        request, "library.html", {"series": series, "standalone": standalone}
    )


@router.get("/series/{series_id}", response_class=HTMLResponse)
async def series_page(
    request: Request, series_id: int, session=Depends(get_session)  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    series = SeriesRepo(session).get(series_id)
    if series is None:
        raise HTTPException(status_code=404, detail=f"series {series_id} not found")

    chapters = ChapterCacheRepo(session).list_by_series(series_id)
    position = PositionRepo(session).get(series.series_key)
    current_url = position.url if position else None
    return templates.TemplateResponse(
        request,
        "series.html",
        {
            "series": series,
            "chapters": chapters,
            "position": position,
            "current_url": current_url,
            "continue_chapter": next(
                (c for c in chapters if current_url and c.url == current_url), None
            ),
        },
    )


@router.patch("/series/{series_id}", response_class=HTMLResponse)
async def series_rename(
    request: Request,
    series_id: int,
    title: str = Form(""),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = SeriesRepo(session)
    series = repo.rename(series_id, title)
    if series is None:
        raise HTTPException(status_code=404, detail=f"series {series_id} not found")
    session.commit()
    return templates.TemplateResponse(request, "_series_header.html", {"series": series})


@router.post("/series/{series_id}/follow", response_class=HTMLResponse)
async def series_follow(
    request: Request,
    series_id: int,
    followed: str = Form(""),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = SeriesRepo(session)
    series = repo.set_followed(series_id, followed == "true")
    if series is None:
        raise HTTPException(status_code=404, detail=f"series {series_id} not found")
    session.commit()
    return templates.TemplateResponse(request, "_series_header.html", {"series": series})


async def _run_process(
    session,  # type: ignore[no-untyped-def]
    state: AppState,
    *,
    url: str | None,
    raw_text: str | None,
    title: str | None,
):
    dict_repo = DictionaryRepo(session)
    entries = dict_repo.list_enabled()
    dict_version_hash = CompiledDictionary.from_entries(entries).version_hash
    DictionaryVersionRepo(session).ensure(dict_version_hash, len(entries))

    result = await process_chapter(
        source_url=url,
        raw_text=raw_text,
        title=title,
        dictionary_entries=entries,
        dict_version_hash=dict_version_hash,
        prompt_version=state.settings.llm_prompt_version,
        model=state.settings.llm_model,
        provider=state.provider,
        chapter_cache_repo=ChapterCacheRepo(session),
        run_log_repo=RunLogRepo(session),
        llm_cache=LLMCacheRepo(session),
        registry=state.registry,
        fetcher=state.fetcher,
        temperature=state.settings.llm_temperature,
        batch_size=state.settings.llm_batch_size,
        max_retries=state.settings.llm_max_retries,
    )
    session.commit()
    return result


def _series_key(series, url: str | None, chapter_id: int | None) -> str:  # type: ignore[no-untyped-def]
    """Key under which the reading position is stored.

    For a chapter that belongs to a story this is the STORY's key, so the position means
    "which chapter of this story, and where in it" -- that is what makes "continue reading"
    work across chapters. A standalone (pasted) chapter falls back to its own cache id so two
    pasted chapters never overwrite each other.
    """
    if series is not None:
        return str(series.series_key)
    if url:
        return url
    return f"chapter:{chapter_id}" if chapter_id is not None else "raw"


def _cached_reader_context(request: Request, cached, series=None) -> dict:  # type: ignore[no-untyped-def]
    """Dựng lại màn hình đọc từ một chương đã nằm trong cache."""
    changelog = [Change(**c) for c in json.loads(cached.changelog_json)]
    return {
        "request": request,
        "id": cached.id,
        "title": cached.title,
        "paragraphs_html": render_paragraphs_html(
            cached.output_text.split("\n\n"), changelog
        ),
        "raw_paragraphs": cached.raw_text.split("\n\n"),
        "warnings": [],
        "status": "ok",
        "violations": [],
        "next_url": cached.next_url,
        "prev_url": cached.prev_url,
        "series": series,
        "series_key": _series_key(series, cached.url, cached.id),
        "url": cached.url,
    }


def _reader_context(request: Request, result, url: str | None, series=None) -> dict:  # type: ignore[no-untyped-def]
    return {
        "request": request,
        "id": result.chapter_cache_id,
        "title": result.chapter.title,
        "paragraphs_html": render_paragraphs_html(result.output_paragraphs, result.changelog),
        "raw_paragraphs": result.chapter.paragraphs,
        "warnings": result.warnings,
        "status": result.status,
        "violations": result.violations,
        "next_url": result.chapter.next_url,
        "prev_url": result.chapter.prev_url,
        "series": series,
        "series_key": _series_key(series, url, result.chapter_cache_id),
        "url": url,
    }


@router.post("/read", response_class=HTMLResponse)
async def read(
    request: Request,
    url: str = Form(""),
    raw_text: str = Form(""),
    title: str = Form(""),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
    state: AppState = Depends(get_app_state),
) -> HTMLResponse:
    normalized_url = ""
    try:
        normalized_url = normalize_source_url(url) if url.strip() else ""
        normalized_text = raw_text.strip()
        if not normalized_url and not normalized_text:
            raise ValueError("missing URL and pasted text")
        result = await _run_process(
            session,
            state,
            url=normalized_url or None,
            raw_text=normalized_text or None,
            title=title.strip() or None,
        )
        series = link_chapter_to_series(
            session,
            chapter_cache_id=result.chapter_cache_id,
            url=normalized_url or None,
            title=result.chapter.title,
        )
        session.commit()

        context = _reader_context(request, result, normalized_url or None, series)
        response = templates.TemplateResponse(request, "_reader.html", context)
        # Give the chapter a real address: refresh, back button and bookmarking all work, and the
        # chapter survives closing the tab. Only possible when it was cached (validation passed).
        if result.chapter_cache_id is not None:
            response.headers["HX-Push-Url"] = f"/reader/{result.chapter_cache_id}"
        return response
    except Exception as exc:
        session.rollback()
        logger.info("Could not open reader source: %s", exc)
        failed_url = normalized_url or url.strip()
        return templates.TemplateResponse(
            request,
            "_reader_error.html",
            {
                "request": request,
                "url": failed_url,
                **_read_error_context(exc, failed_url),
            },
        )


@router.get("/reader/{chapter_id}", response_class=HTMLResponse)
async def reader_page(
    request: Request, chapter_id: int, session=Depends(get_session)  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = ChapterCacheRepo(session)
    cached = repo.get_by_id(chapter_id)
    if cached is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} not found in cache")
    repo.touch(chapter_id)
    series = SeriesRepo(session).get(cached.series_id) if cached.series_id else None
    if series is not None:
        SeriesRepo(session).touch(series.id)
    session.commit()

    context = _cached_reader_context(request, cached, series)
    return templates.TemplateResponse(request, "reader.html", context)


@router.post("/reader/{chapter_id}/navigation", response_class=HTMLResponse)
async def set_chapter_navigation(
    request: Request,
    chapter_id: int,
    next_url: str = Form(""),
    prev_url: str = Form(""),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    """Đặt tay liên kết chương trước/sau cho một chương.

    Việc dò tự động (`extraction/navigation.py`) chỉ là phỏng đoán, và có site điều hướng bằng
    JS nên URL không đổi — khi đó không có gì để dò. Đây là đường thoát: người đọc dán thẳng
    địa chỉ chương kế tiếp vào.
    """
    repo = ChapterCacheRepo(session)
    cached = repo.get_by_id(chapter_id)
    if cached is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} not found in cache")

    try:
        normalized_next = normalize_source_url(next_url) if next_url.strip() else None
        normalized_prev = normalize_source_url(prev_url) if prev_url.strip() else None
    except SourceURLError as exc:
        series = SeriesRepo(session).get(cached.series_id) if cached.series_id else None
        context = _cached_reader_context(request, cached, series)
        context.update(
            navigation_error=str(exc),
            nav_next_value=next_url.strip(),
            nav_prev_value=prev_url.strip(),
        )
        return templates.TemplateResponse(request, "_reader.html", context)
    repo.set_navigation(chapter_id, next_url=normalized_next, prev_url=normalized_prev)
    session.commit()

    refreshed = repo.get_by_id(chapter_id)
    series = SeriesRepo(session).get(cached.series_id) if cached.series_id else None
    return templates.TemplateResponse(
        request, "_reader.html", _cached_reader_context(request, refreshed, series)
    )


@router.post("/reader/{chapter_id}/reprocess", response_class=HTMLResponse)
async def reprocess_chapter(
    request: Request,
    chapter_id: int,
    session=Depends(get_session),  # type: ignore[no-untyped-def]
    state: AppState = Depends(get_app_state),
) -> HTMLResponse:
    """Re-run a chapter against the current dictionary, e.g. right after a quick-add.

    Reprocessing always works from the stored raw text, never by refetching the source: the
    text has not changed, only the dictionary has, so there is no reason to hit the network
    again (and no reason for it to fail if the site is down).
    """
    repo = ChapterCacheRepo(session)
    cached = repo.get_by_id(chapter_id)
    if cached is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} not found in cache")

    result = await _run_process(
        session, state, url=cached.url, raw_text=cached.raw_text, title=cached.title
    )
    # Raw text carries no navigation links; keep the ones captured at extraction time.
    if result.chapter_cache_id is not None and (cached.next_url or cached.prev_url):
        repo.set_navigation(
            result.chapter_cache_id, next_url=cached.next_url, prev_url=cached.prev_url
        )
        session.commit()

    # The rebuilt row is a new chapter_cache row, so re-attach it to the same story.
    series = None
    if result.chapter_cache_id is not None and cached.series_id is not None:
        repo.set_series(result.chapter_cache_id, cached.series_id)
        series = SeriesRepo(session).get(cached.series_id)
        session.commit()

    context = _reader_context(request, result, cached.url, series)
    context["next_url"] = result.chapter.next_url or cached.next_url
    context["prev_url"] = result.chapter.prev_url or cached.prev_url

    response = templates.TemplateResponse(request, "_reader.html", context)
    if result.chapter_cache_id is not None:
        response.headers["HX-Push-Url"] = f"/reader/{result.chapter_cache_id}"
    return response


@router.get("/dictionary", response_class=HTMLResponse)
async def dictionary_page(
    request: Request, session=Depends(get_session)  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    entries = DictionaryRepo(session).list()
    return templates.TemplateResponse(request, "dictionary.html", {"entries": entries})


@router.get("/dictionary/table", response_class=HTMLResponse)
async def dictionary_table(
    request: Request,
    policy: str = "",
    search: str = "",
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    entries = DictionaryRepo(session).list(
        policy=Policy(policy) if policy else None, search=search or None
    )
    return templates.TemplateResponse(request, "_dictionary_table.html", {"entries": entries})


@router.post("/dictionary/create", response_class=HTMLResponse)
async def dictionary_create(
    request: Request,
    surface: str = Form(...),
    display: str = Form(""),
    policy: str = Form("keep"),
    replacement: str = Form(""),
    candidates: str = Form(""),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = DictionaryRepo(session)
    repo.create(
        surface=surface,
        display=display or surface,
        policy=Policy(policy),
        replacement=replacement or None,
        candidates=[c.strip() for c in candidates.split(",") if c.strip()],
    )
    session.commit()
    entries = repo.list()
    return templates.TemplateResponse(request, "_dictionary_table.html", {"entries": entries})


@router.patch("/dictionary/{entry_id}", response_class=HTMLResponse)
async def dictionary_update(
    request: Request,
    entry_id: int,
    priority: int = Form(0),
    enabled: str = Form(""),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = DictionaryRepo(session)
    repo.update(entry_id, priority=priority, enabled=bool(enabled))
    session.commit()
    entries = repo.list()
    return templates.TemplateResponse(request, "_dictionary_table.html", {"entries": entries})


@router.delete("/dictionary/{entry_id}", response_class=HTMLResponse)
async def dictionary_delete(
    request: Request, entry_id: int, session=Depends(get_session)  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = DictionaryRepo(session)
    repo.delete(entry_id)
    session.commit()
    entries = repo.list()
    return templates.TemplateResponse(request, "_dictionary_table.html", {"entries": entries})


@router.post("/dictionary/import-csv", response_class=HTMLResponse)
async def dictionary_import_csv(
    request: Request,
    csv_file: UploadFile,
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    raw = (await csv_file.read()).decode("utf-8")
    repo = DictionaryRepo(session)
    for item in _parse_csv(raw):
        try:
            repo.create(**item.model_dump())
            session.commit()
        except Exception:  # skip bad rows, keep importing the rest
            session.rollback()
    entries = repo.list()
    return templates.TemplateResponse(request, "_dictionary_table.html", {"entries": entries})


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_page(
    request: Request,
    show: str = "open",
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = FeedbackRepo(session)
    resolved = {"open": False, "done": True}.get(show)
    return templates.TemplateResponse(
        request,
        "feedback.html",
        {"notes": repo.list(resolved=resolved), "show": show, "open_count": repo.count_open()},
    )


@router.post("/feedback", response_class=HTMLResponse)
async def feedback_create(
    request: Request,
    message: str = Form(...),
    chapter_cache_id: str = Form(""),
    chapter_title: str = Form(""),
    url: str = Form(""),
    para_index: str = Form(""),
    quote: str = Form(""),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    """Save a reading note. Returns a small confirmation fragment for the floating widget."""
    try:
        FeedbackRepo(session).add(
            message=message,
            chapter_cache_id=int(chapter_cache_id) if chapter_cache_id.isdigit() else None,
            chapter_title=chapter_title,
            url=url or None,
            para_index=int(para_index) if para_index.isdigit() else None,
            quote=quote,
        )
    except FeedbackError as exc:
        return HTMLResponse(f'<p class="form-error">{exc}</p>', status_code=400)
    session.commit()
    return HTMLResponse('<p class="form-ok">Đã lưu ghi chú. Xem lại ở mục Ghi chú.</p>')


@router.patch("/feedback/{feedback_id}", response_class=HTMLResponse)
async def feedback_toggle(
    request: Request,
    feedback_id: int,
    resolved: str = Form(""),
    show: str = Form("open"),
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = FeedbackRepo(session)
    if repo.set_resolved(feedback_id, resolved == "true") is None:
        raise HTTPException(status_code=404, detail=f"feedback {feedback_id} not found")
    session.commit()
    return templates.TemplateResponse(
        request,
        "_feedback_list.html",
        {"notes": repo.list(resolved={"open": False, "done": True}.get(show)), "show": show},
    )


@router.delete("/feedback/{feedback_id}", response_class=HTMLResponse)
async def feedback_delete(
    request: Request,
    feedback_id: int,
    show: str = "open",
    session=Depends(get_session),  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    repo = FeedbackRepo(session)
    if not repo.delete(feedback_id):
        raise HTTPException(status_code=404, detail=f"feedback {feedback_id} not found")
    session.commit()
    return templates.TemplateResponse(
        request,
        "_feedback_list.html",
        {"notes": repo.list(resolved={"open": False, "done": True}.get(show)), "show": show},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, state: AppState = Depends(get_app_state)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"settings": state.settings, "prompt_version": state.settings.llm_prompt_version},
    )

"""Server-rendered reader UI (Jinja2 + HTMX): home, reader, dictionary manager, settings."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from vietreader.api.deps import AppState, get_app_state, get_session
from vietreader.api.routes.dictionary import _parse_csv
from vietreader.core.dictionary import CompiledDictionary
from vietreader.core.models import Policy
from vietreader.db.repositories.chapter_cache import ChapterCacheRepo
from vietreader.db.repositories.dictionary import DictionaryRepo
from vietreader.db.repositories.llm_cache import LLMCacheRepo
from vietreader.db.repositories.run_log import RunLogRepo
from vietreader.llm.disambiguator import PROMPT_VERSION
from vietreader.pipeline.process_chapter import process_chapter
from vietreader.web.rendering import render_paragraphs_html

router = APIRouter(tags=["web"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "web" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "home.html", {})


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

    result = await process_chapter(
        source_url=url,
        raw_text=raw_text,
        title=title,
        dictionary_entries=entries,
        dict_version_hash=dict_version_hash,
        prompt_version=PROMPT_VERSION,
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


def _reader_context(request: Request, result, url: str | None) -> dict:  # type: ignore[no-untyped-def]
    return {
        "request": request,
        "id": result.chapter_cache_id,
        "title": result.chapter.title,
        "paragraphs_html": render_paragraphs_html(result.output_paragraphs, result.changelog),
        "raw_paragraphs": result.chapter.paragraphs,
        "stats": result.stats,
        "warnings": result.warnings,
        "status": result.status,
        "violations": result.violations,
        "next_url": result.chapter.next_url,
        "prev_url": result.chapter.prev_url,
        "series_key": url or "raw",
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
    result = await _run_process(
        session, state, url=url or None, raw_text=raw_text or None, title=title or None
    )
    context = _reader_context(request, result, url or None)
    return templates.TemplateResponse(request, "_reader.html", context)


@router.get("/reader/{chapter_id}", response_class=HTMLResponse)
async def reader_page(
    request: Request, chapter_id: int, session=Depends(get_session)  # type: ignore[no-untyped-def]
) -> HTMLResponse:
    cached = ChapterCacheRepo(session).get_by_id(chapter_id)
    if cached is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} not found in cache")
    import json as _json

    from vietreader.core.models import Change

    changelog = [Change(**c) for c in _json.loads(cached.changelog_json)]
    output_paragraphs = cached.output_text.split("\n\n")
    context = {
        "request": request,
        "id": cached.id,
        "title": cached.title,
        "paragraphs_html": render_paragraphs_html(output_paragraphs, changelog),
        "raw_paragraphs": cached.raw_text.split("\n\n"),
        "stats": {
            "replace_count": sum(1 for c in changelog if c.source == "replace"),
            "ask_count": sum(1 for c in changelog if c.source in ("llm", "llm_fallback")),
            "llm_calls": 0,
            "llm_cache_hits": 0,
            "duration_ms": 0.0,
            "from_cache": True,
        },
        "warnings": [],
        "status": "ok",
        "violations": [],
        "next_url": None,
        "prev_url": None,
        "series_key": cached.url or "raw",
        "url": cached.url,
    }
    return templates.TemplateResponse(request, "reader.html", context)


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


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, state: AppState = Depends(get_app_state)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "settings.html", {"settings": state.settings, "prompt_version": PROMPT_VERSION}
    )

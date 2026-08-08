"""Phase 7: reader UI smoke tests. Every route returns 200 and renders its template, plus a
true end-to-end quick-add test (add dictionary entry via API -> reprocess chapter -> see the
change reflected in the rendered HTML)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vietreader.api.app import create_app
from vietreader.llm.provider import FakeProvider
from vietreader.settings import Settings


@pytest.fixture
def app(tmp_path) -> FastAPI:  # type: ignore[no-untyped-def]
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        llm_api_key="test-key",
        llm_model="test-model",
    )
    return create_app(settings=settings, provider=FakeProvider(mode="correct"))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_home_page_renders(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Đọc" in resp.text
    assert 'hx-post="/read"' in resp.text


async def test_dictionary_page_renders(client: AsyncClient) -> None:
    resp = await client.get("/dictionary")
    assert resp.status_code == 200
    assert "Quản lý từ điển" in resp.text


async def test_settings_page_renders(client: AsyncClient) -> None:
    resp = await client.get("/settings")
    assert resp.status_code == 200
    assert "test-model" in resp.text


async def test_static_assets_served(client: AsyncClient) -> None:
    css = await client.get("/static/css/style.css")
    assert css.status_code == 200
    htmx = await client.get("/static/js/htmx.min.js")
    assert htmx.status_code == 200


async def test_read_raw_text_renders_reader_fragment(client: AsyncClient) -> None:
    resp = await client.post("/read", data={"raw_text": "Xin chào thế giới.", "title": "T1"})
    assert resp.status_code == 200
    assert "Xin chào thế giới" in resp.text
    assert "T1" in resp.text


async def test_reader_page_by_id_after_processing(client: AsyncClient) -> None:
    processed = await client.post("/api/chapters/process", json={"raw_text": "Nội dung chương."})
    chapter_id = processed.json()["id"]

    resp = await client.get(f"/reader/{chapter_id}")
    assert resp.status_code == 200
    assert "Nội dung chương" in resp.text


async def test_reader_page_unknown_id_404(client: AsyncClient) -> None:
    resp = await client.get("/reader/999999")
    assert resp.status_code == 404


async def test_dictionary_table_filter_fragment(client: AsyncClient) -> None:
    await client.post(
        "/dictionary/create", data={"surface": "linh lực", "policy": "keep"}
    )
    resp = await client.get("/dictionary/table", params={"policy": "keep"})
    assert resp.status_code == 200
    assert "linh lực" in resp.text


async def test_dictionary_web_update_and_delete(client: AsyncClient) -> None:
    created = await client.post(
        "/api/dictionary", json={"surface": "a", "display": "a", "policy": "keep"}
    )
    entry_id = created.json()["id"]

    updated = await client.patch(f"/dictionary/{entry_id}", data={"priority": "5"})
    assert updated.status_code == 200
    assert "a" in updated.text

    deleted = await client.delete(f"/dictionary/{entry_id}")
    assert deleted.status_code == 200
    assert f"dict-row-{entry_id}" not in deleted.text


async def test_dictionary_web_import_csv(client: AsyncClient) -> None:
    csv_content = (
        "surface,display,policy,replacement,candidates,priority,note,enabled\n"
        "x,x,keep,,,0,,true\n"
    )
    files = {"csv_file": ("entries.csv", csv_content, "text/csv")}
    resp = await client.post("/dictionary/import-csv", files=files)
    assert resp.status_code == 200
    assert ">x<" in resp.text or "dict-row" in resp.text


async def test_quick_add_end_to_end_reflected_on_reprocess(client: AsyncClient) -> None:
    raw_text = "Lão giả nhìn thiếu niên."

    before = await client.post("/read", data={"raw_text": raw_text})
    assert "Ông lão" not in before.text

    quick_add = await client.post(
        "/api/dictionary/quick-add",
        json={"surface": "lão giả", "policy": "replace", "replacement": "ông lão"},
    )
    assert quick_add.status_code == 201

    after = await client.post("/read", data={"raw_text": raw_text})
    # "Lão giả" was Title-cased in the source, so casing transfer capitalizes the replacement too.
    assert "Ông lão" in after.text
    assert "changed" in after.text

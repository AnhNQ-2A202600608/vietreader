"""Phase 6: HTTP API tests via httpx.AsyncClient against the real FastAPI app (in-process ASGI,
no real network). Covers every endpoint plus the required error paths."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
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


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_openapi_and_docs_load(client: AsyncClient) -> None:
    openapi = await client.get("/openapi.json")
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "VietReader API"

    docs = await client.get("/docs")
    assert docs.status_code == 200


async def test_dictionary_create_list_update_delete(client: AsyncClient) -> None:
    create = await client.post(
        "/api/dictionary",
        json={
            "surface": "lão giả",
            "display": "Lão giả",
            "policy": "replace",
            "replacement": "ông lão",
        },
    )
    assert create.status_code == 201
    entry_id = create.json()["id"]

    listed = await client.get("/api/dictionary")
    assert listed.status_code == 200
    assert any(e["id"] == entry_id for e in listed.json())

    filtered = await client.get("/api/dictionary", params={"policy": "replace", "search": "giả"})
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    updated = await client.patch(f"/api/dictionary/{entry_id}", json={"replacement": "ông cụ"})
    assert updated.status_code == 200
    assert updated.json()["replacement"] == "ông cụ"

    deleted = await client.delete(f"/api/dictionary/{entry_id}")
    assert deleted.status_code == 204

    missing = await client.patch(f"/api/dictionary/{entry_id}", json={"note": "x"})
    assert missing.status_code == 404


async def test_dictionary_replace_missing_replacement_returns_error_envelope(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/dictionary", json={"surface": "a", "display": "a", "policy": "replace"}
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "dictionary_error"
    assert "replacement" in body["error"]["message"]


async def test_dictionary_duplicate_surface_returns_error_envelope(client: AsyncClient) -> None:
    payload = {"surface": "linh lực", "display": "linh lực", "policy": "keep"}
    first = await client.post("/api/dictionary", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/dictionary", json=payload)
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "dictionary_error"


async def test_dictionary_quick_add(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/dictionary/quick-add",
        json={"surface": "đạo hữu", "policy": "ask", "candidates": ["đạo hữu", "bạn"]},
    )
    assert resp.status_code == 201
    assert resp.json()["display"] == "đạo hữu"


async def test_dictionary_import_and_export(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/dictionary/import",
        json={
            "entries": [
                {"surface": "a", "display": "a", "policy": "keep"},
                {
                    "surface": "b",
                    "display": "b",
                    "policy": "replace",
                },  # missing replacement -> error
            ],
            "csv": (
                "surface,display,policy,replacement,candidates,priority,note,enabled\n"
                "c,c,keep,,,0,,true\n"
            ),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 2  # "a" and csv row "c"; "b" fails
    assert len(body["errors"]) == 1
    assert body["errors"][0]["surface"] == "b"

    export = await client.get("/api/dictionary/export")
    assert export.status_code == 200
    surfaces = {e["surface"] for e in export.json()}
    assert {"a", "c"}.issubset(surfaces)


async def test_position_get_missing_then_put_then_get(client: AsyncClient) -> None:
    missing = await client.get("/api/position/series-1")
    assert missing.status_code == 404

    put = await client.put(
        "/api/position/series-1", json={"url": "https://example.com/c1", "para_index": 3}
    )
    assert put.status_code == 200

    got = await client.get("/api/position/series-1")
    assert got.status_code == 200
    assert got.json() == {
        "series_key": "series-1",
        "url": "https://example.com/c1",
        "para_index": 3,
    }


async def test_position_works_for_a_url_series_key(client: AsyncClient) -> None:
    """A real series key IS a URL, so it contains slashes.

    The route needs a `:path` parameter to match at all -- percent-encoding does not save it,
    because the path is decoded before routing. Until this was fixed, saving and restoring the
    reading position silently 404'd for every chapter opened from a URL, which is most of them.
    """
    series_key = "https://truyenfull.vn/dau-pha-thuong-khung"

    put = await client.put(
        f"/api/position/{series_key}",
        json={"url": f"{series_key}/chuong-5", "para_index": 12},
    )
    assert put.status_code == 200

    got = await client.get(f"/api/position/{series_key}")
    assert got.status_code == 200
    assert got.json() == {
        "series_key": series_key,
        "url": f"{series_key}/chuong-5",
        "para_index": 12,
    }


async def test_chapters_process_raw_text_then_get_by_id(client: AsyncClient) -> None:
    resp = await client.post("/api/chapters/process", json={"raw_text": "Xin chào thế giới."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["id"] is not None

    got = await client.get(f"/api/chapters/{body['id']}")
    assert got.status_code == 200
    assert got.json()["title"] == ""


async def test_chapters_process_requires_url_or_raw_text(client: AsyncClient) -> None:
    resp = await client.post("/api/chapters/process", json={})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_request"


async def test_chapters_get_unknown_id_404(client: AsyncClient) -> None:
    resp = await client.get("/api/chapters/999999")
    assert resp.status_code == 404


async def test_chapters_process_fetch_error_returns_422_with_paste_hint(
    client: AsyncClient, app: FastAPI
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    from vietreader.extraction.fetcher import Fetcher

    app.state.app_state.fetcher = Fetcher(
        user_agent="test-agent",
        delay_seconds=0,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )

    resp = await client.post("/api/chapters/process", json={"url": "https://example.com/chap/1"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "fetch_error"
    assert "dán trực tiếp" in body["error"]["hint"]

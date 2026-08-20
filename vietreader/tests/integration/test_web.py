"""Phase 7: reader UI smoke tests. Every route returns 200 and renders its template, plus a
true end-to-end quick-add test (add dictionary entry via API -> reprocess chapter -> see the
change reflected in the rendered HTML)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vietreader.api.app import create_app
from vietreader.db.repositories.chapter_cache import ChapterCacheRepo
from vietreader.extraction.fetcher import Fetcher
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
    assert "Bạn muốn đọc từ đâu?" in resp.text
    assert "Dán nội dung chương" in resp.text


async def test_dictionary_page_renders(client: AsyncClient) -> None:
    resp = await client.get("/dictionary")
    assert resp.status_code == 200
    assert "Từ điển" in resp.text
    assert 'hx-post="/dictionary/create"' in resp.text


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


async def test_pasted_heading_becomes_title_in_reader_and_library(client: AsyncClient) -> None:
    raw = (
        "Chương 51 — Trở lại cố hương\n\n"
        "Con đường cũ vẫn chạy dọc theo bờ sông nhưng hàng cây đã cao hơn trước."
    )

    read = await client.post("/read", data={"raw_text": raw})
    library = await client.get("/library")

    assert "<h2>Chương 51 — Trở lại cố hương</h2>" in read.text
    reader_body = read.text.split('<div class="reader-text"', 1)[1].split("</div>", 1)[0]
    assert "Chương 51 — Trở lại cố hương" not in reader_body
    assert "Chương 51 — Trở lại cố hương" in library.text
    assert "(không có tiêu đề)" not in library.text


async def test_read_normalizes_a_domain_only_url(app: FastAPI, client: AsyncClient) -> None:
    requested: list[str] = []
    html = (
        "<html><body><article><h1>Chương 12</h1>"
        "<p>Nội dung chương đủ dài để bộ trích xuất nhận diện chính xác.</p>"
        "<p>Đoạn thứ hai cũng đủ dài và giữ nguyên định dạng khi hiển thị.</p>"
        "</article></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, text=html)

    app.state.app_state.fetcher = Fetcher(
        delay_seconds=0, transport=httpx.MockTransport(handler)
    )
    resp = await client.post("/read", data={"url": "truyen.example/chuong-12"})

    assert resp.status_code == 200
    assert requested == ["https://truyen.example/chuong-12"]
    assert "Nội dung chương đủ dài" in resp.text
    assert "https://truyen.example/chuong-12" in resp.text


async def test_read_failure_explains_blocked_site_and_offers_paste(
    app: FastAPI, client: AsyncClient
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    app.state.app_state.fetcher = Fetcher(
        delay_seconds=0, max_retries=3, transport=httpx.MockTransport(handler)
    )
    resp = await client.post("/read", data={"url": "https://blocked.example/chapter"})

    assert resp.status_code == 200
    assert "Trang nguồn đang chặn đọc tự động" in resp.text
    assert "Dán nội dung thay thế" in resp.text
    assert "Chi tiết kỹ thuật" in resp.text


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


async def test_read_pushes_a_real_url_so_the_chapter_can_be_reopened(
    client: AsyncClient,
) -> None:
    """Without this header the chapter only exists in the swapped-in fragment: refreshing or
    hitting back loses it."""
    resp = await client.post("/read", data={"raw_text": "Một chương ngắn.", "title": "C1"})
    assert resp.status_code == 200
    pushed = resp.headers.get("HX-Push-Url")
    assert pushed is not None and pushed.startswith("/reader/")

    reopened = await client.get(pushed)
    assert reopened.status_code == 200
    assert "Một chương ngắn" in reopened.text


async def test_library_lists_standalone_chapters_most_recent_first(client: AsyncClient) -> None:
    """Pasted chapters have no URL to derive a series from, so they stay standalone and are
    listed on their own, newest first."""
    empty = await client.get("/library")
    assert empty.status_code == 200
    assert "Chưa có gì ở đây" in empty.text

    await client.post("/read", data={"raw_text": "Chương một.", "title": "Chương một"})
    await client.post("/read", data={"raw_text": "Chương hai.", "title": "Chương hai"})

    resp = await client.get("/library")
    assert resp.status_code == 200
    assert "Chương lẻ" in resp.text
    assert resp.text.index("Chương hai") < resp.text.index("Chương một")


async def test_home_greets_the_reader_by_name(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Ngân Giang" in resp.text  # tên mặc định trong Settings


async def test_reader_name_is_configurable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Tên người đọc phải đổi được qua cấu hình, không hardcode trong template."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'other.db'}",
        llm_api_key="test-key",
        llm_model="test-model",
        reader_name="Ai Đó Khác",
    )
    app = create_app(settings=settings, provider=FakeProvider(mode="correct"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/")
        assert "Ai Đó Khác" in resp.text
        assert "Ngân Giang" not in resp.text


async def test_home_offers_to_continue_the_last_chapter(client: AsyncClient) -> None:
    before = await client.get("/")
    assert "Tiếp tục đọc" not in before.text

    await client.post("/read", data={"raw_text": "Nội dung.", "title": "Chương đang đọc"})

    after = await client.get("/")
    assert "Tiếp tục đọc" in after.text
    assert "Chương đang đọc" in after.text


async def test_pasted_chapters_do_not_share_one_reading_position(client: AsyncClient) -> None:
    """Every pasted chapter used to be keyed as "raw", so they all overwrote each other's
    position. Each chapter must own its own key."""
    first = await client.post("/read", data={"raw_text": "Chương A.", "title": "A"})
    second = await client.post("/read", data={"raw_text": "Chương B.", "title": "B"})

    key_a = first.text.split('data-series-key="')[1].split('"')[0]
    key_b = second.text.split('data-series-key="')[1].split('"')[0]
    assert key_a != key_b
    assert key_a != "raw"


async def test_reprocess_applies_a_newly_added_entry_without_refetching(
    client: AsyncClient,
) -> None:
    raw_text = "Lão giả mỉm cười."
    read = await client.post("/read", data={"raw_text": raw_text})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]
    assert "Ông lão" not in read.text

    quick_add = await client.post(
        "/api/dictionary/quick-add",
        json={"surface": "lão giả", "policy": "replace", "replacement": "ông lão"},
    )
    assert quick_add.status_code == 201

    resp = await client.post(f"/reader/{chapter_id}/reprocess")
    assert resp.status_code == 200
    assert "Ông lão" in resp.text
    assert resp.headers.get("HX-Push-Url", "").startswith("/reader/")


async def test_reprocess_keeps_chapter_navigation(app: FastAPI, client: AsyncClient) -> None:
    """Adding a word mid-series must not strip the 'next chapter' link: reprocessing rebuilds
    from raw text, which carries no links of its own."""
    read = await client.post("/read", data={"raw_text": "Lão giả đi.", "title": "C7"})
    chapter_id = int(read.headers["HX-Push-Url"].rsplit("/", 1)[1])

    state = app.state.app_state
    with state.session_factory() as session:
        ChapterCacheRepo(session).set_navigation(
            chapter_id, next_url="https://example.com/c8", prev_url="https://example.com/c6"
        )
        session.commit()

    await client.post(
        "/api/dictionary/quick-add",
        json={"surface": "lão giả", "policy": "replace", "replacement": "ông lão"},
    )
    resp = await client.post(f"/reader/{chapter_id}/reprocess")
    assert resp.status_code == 200
    assert "Ông lão" in resp.text
    assert "https://example.com/c8" in resp.text

    new_id = int(resp.headers["HX-Push-Url"].rsplit("/", 1)[1])
    reopened = await client.get(f"/reader/{new_id}")
    assert "https://example.com/c8" in reopened.text


async def test_library_shows_one_entry_per_chapter_after_reprocessing(
    client: AsyncClient,
) -> None:
    """Each dictionary edit caches a new row for the same chapter. The library must show the
    chapter once, not once per dictionary version."""
    read = await client.post("/read", data={"raw_text": "Lão giả đi.", "title": "Chương duy nhất"})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]

    await client.post(
        "/api/dictionary/quick-add",
        json={"surface": "lão giả", "policy": "replace", "replacement": "ông lão"},
    )
    await client.post(f"/reader/{chapter_id}/reprocess")

    resp = await client.get("/library")
    assert resp.text.count("Chương duy nhất") == 1


async def test_navigation_can_be_set_by_hand(client: AsyncClient) -> None:
    """Đường thoát khi dò tự động trượt, hoặc khi site đổi chương mà không đổi địa chỉ."""
    read = await client.post("/read", data={"raw_text": "Chương dán tay.", "title": "C1"})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]
    # Văn bản dán tay không có liên kết nào để dò.
    assert "Chương sau →" not in read.text

    saved = await client.post(
        f"/reader/{chapter_id}/navigation",
        data={"next_url": "https://truyen.vn/abc/chuong-2",
              "prev_url": "https://truyen.vn/abc/chuong-0"},
    )
    assert saved.status_code == 200
    assert "Chương sau →" in saved.text
    assert "https://truyen.vn/abc/chuong-2" in saved.text

    # Và phải còn đó khi mở lại chương.
    reopened = await client.get(f"/reader/{chapter_id}")
    assert "https://truyen.vn/abc/chuong-2" in reopened.text


async def test_chapter_title_can_be_renamed_from_reader(client: AsyncClient) -> None:
    read = await client.post("/read", data={"raw_text": "Một chương không có heading."})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]
    assert "(không có tiêu đề)" in read.text

    renamed = await client.post(
        f"/reader/{chapter_id}/title",
        data={"title": "  Chương 18 — Trở về  "},
    )
    assert renamed.status_code == 200
    assert "Chương 18 — Trở về" in renamed.text
    assert "Đã lưu tên chương" in renamed.text

    reopened = await client.get(f"/reader/{chapter_id}")
    library = await client.get("/library")
    assert "Chương 18 — Trở về" in reopened.text
    assert "Chương 18 — Trở về" in library.text


async def test_chapter_title_rejects_blank_and_unknown_chapter(client: AsyncClient) -> None:
    read = await client.post("/read", data={"raw_text": "Nội dung.", "title": "Tên cũ"})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]

    blank = await client.post(f"/reader/{chapter_id}/title", data={"title": "   "})
    assert blank.status_code == 200
    assert "Tên chương không được để trống" in blank.text
    assert "Tên cũ" in blank.text

    missing = await client.post("/reader/999999/title", data={"title": "Tên mới"})
    assert missing.status_code == 404


async def test_navigation_normalizes_missing_scheme_and_keeps_invalid_form_visible(
    client: AsyncClient,
) -> None:
    read = await client.post("/read", data={"raw_text": "Chương dán tay.", "title": "C1"})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]

    saved = await client.post(
        f"/reader/{chapter_id}/navigation",
        data={"next_url": "truyen.vn/abc/chuong-2"},
    )
    assert "https://truyen.vn/abc/chuong-2" in saved.text

    invalid = await client.post(
        f"/reader/{chapter_id}/navigation",
        data={"next_url": "không phải liên kết"},
    )
    assert invalid.status_code == 200
    assert "Hãy nhập một địa chỉ web" in invalid.text
    assert "không phải liên kết" in invalid.text


async def test_navigation_can_be_cleared(client: AsyncClient) -> None:
    read = await client.post("/read", data={"raw_text": "Chương khác.", "title": "C2"})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]
    await client.post(
        f"/reader/{chapter_id}/navigation", data={"next_url": "https://truyen.vn/x/2"}
    )

    cleared = await client.post(
        f"/reader/{chapter_id}/navigation", data={"next_url": "   ", "prev_url": ""}
    )
    assert cleared.status_code == 200
    assert "https://truyen.vn/x/2" not in cleared.text


async def test_navigation_unknown_chapter_404(client: AsyncClient) -> None:
    resp = await client.post("/reader/999999/navigation", data={"next_url": "https://a.vn/2"})
    assert resp.status_code == 404


async def test_chapter_read_from_a_site_gets_navigation_without_an_adapter(
    app: FastAPI, client: AsyncClient
) -> None:
    """Không có file adapter nào cho truyen.test — liên kết phải được dò tự động."""
    def handler(request: httpx.Request) -> httpx.Response:
        page = _story_html(f"Chương tại {request.url.path}").replace(
            "</article>",
            '</article><div><a href="/truyen-abc/chuong-4">Chương trước</a>'
            '<a href="/truyen-abc/chuong-6">Chương sau</a></div>',
        )
        return httpx.Response(200, text=page)

    app.state.app_state.fetcher = Fetcher(
        user_agent="test-agent", delay_seconds=0, transport=httpx.MockTransport(handler)
    )

    resp = await client.post(
        "/read", data={"url": "https://truyen.test/truyen-abc/chuong-5"}
    )
    assert "https://truyen.test/truyen-abc/chuong-6" in resp.text
    assert "Chương sau →" in resp.text


async def test_reprocess_unknown_chapter_404(client: AsyncClient) -> None:
    resp = await client.post("/reader/999999/reprocess")
    assert resp.status_code == 404


def _story_html(heading: str) -> str:
    """The heading must also appear in the BODY text.

    The generic extractor drops a first paragraph that merely repeats the title, so a fixture
    that varies only its heading would produce byte-identical chapters -- and chapters are
    cached by content, so they would silently collapse into one row.
    """
    body = " ".join(
        [
            f"Mở đầu {heading}: lão giả chậm rãi bước qua khoảng sân vắng lặng.",
            "Thiếu niên đứng chờ ở bậc thềm, trong lòng dâng lên một nỗi bồn chồn khó tả.",
            "Gió thổi qua hàng cây, mang theo mùi nhựa thông và hơi lạnh của núi rừng.",
            "Không ai nói với ai câu nào, chỉ có tiếng lá khô lạo xạo dưới chân người đi.",
        ]
    )
    return (
        f"<html><head><title>{heading}</title></head><body><article>"
        f"<h1>{heading}</h1><p>{body}</p><p>{body}</p><p>{body}</p>"
        f"</article></body></html>"
    )


def _story_transport() -> httpx.MockTransport:
    """Every URL gets distinct text.

    Chapters are cached by content, so serving the same body for two URLs would make them
    collapse into one cache row and quietly weaken any test about grouping.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_story_html(f"Chương tại {request.url.path}"))

    return httpx.MockTransport(handler)


def _use_mock_fetcher(app: FastAPI) -> None:
    app.state.app_state.fetcher = Fetcher(
        user_agent="test-agent", delay_seconds=0, transport=_story_transport()
    )


async def test_chapters_of_one_story_group_into_a_series(
    app: FastAPI, client: AsyncClient
) -> None:
    _use_mock_fetcher(app)
    base = "https://truyen.test/truyen-abc"

    first = await client.post("/read", data={"url": f"{base}/chuong-1"})
    second = await client.post("/read", data={"url": f"{base}/chuong-2"})

    # Both chapters store their reading position under the STORY, not their own URL -- that is
    # what lets "continue reading" move across chapters.
    key_1 = first.text.split('data-series-key="')[1].split('"')[0]
    key_2 = second.text.split('data-series-key="')[1].split('"')[0]
    assert key_1 == key_2 == base

    library = await client.get("/library")
    assert "Bộ truyện" in library.text
    series_id = library.text.split('href="/series/')[1].split('"')[0]

    page = await client.get(f"/series/{series_id}")
    assert page.status_code == 200
    assert "2 chương" in page.text

    reopened = await client.get(first.headers["HX-Push-Url"])
    assert f'href="/series/{series_id}"' in reopened.text
    assert "Chương lẻ" not in library.text


async def test_two_stories_on_one_site_do_not_merge(app: FastAPI, client: AsyncClient) -> None:
    _use_mock_fetcher(app)
    a = await client.post("/read", data={"url": "https://truyen.test/truyen-a/chuong-1"})
    b = await client.post("/read", data={"url": "https://truyen.test/truyen-b/chuong-1"})

    key_a = a.text.split('data-series-key="')[1].split('"')[0]
    key_b = b.text.split('data-series-key="')[1].split('"')[0]
    assert key_a != key_b


async def test_identical_text_at_two_urls_does_not_steal_a_chapter(
    app: FastAPI, client: AsyncClient
) -> None:
    """chapter_cache is keyed by CONTENT, so two URLs with byte-identical text share one row.

    Opening the second URL must not drag that row into a different story: before this was
    guarded, story A silently lost the chapter to story B. The same flaw shows up whenever one
    chapter is reachable via two URLs (trailing slash, ?page=1, http vs https).
    """
    same_html = _story_html("Chương giống hệt")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=same_html)

    app.state.app_state.fetcher = Fetcher(
        user_agent="test-agent", delay_seconds=0, transport=httpx.MockTransport(handler)
    )

    first = await client.post("/read", data={"url": "https://truyen.test/truyen-a/chuong-1"})
    second = await client.post("/read", data={"url": "https://truyen.test/truyen-b/chuong-1"})

    key_1 = first.text.split('data-series-key="')[1].split('"')[0]
    key_2 = second.text.split('data-series-key="')[1].split('"')[0]
    assert key_1 == "https://truyen.test/truyen-a"
    # The shared row keeps the story it was first filed under, rather than being moved.
    assert key_2 == key_1

    library = await client.get("/library")
    # And no empty phantom story is created for the second URL.
    assert library.text.count('href="/series/') == 1


async def test_batch_page_renders(client: AsyncClient) -> None:
    resp = await client.get("/batch")
    assert resp.status_code == 200
    assert 'hx-post="/batch"' in resp.text


async def test_batch_ignores_blank_and_duplicate_lines(client: AsyncClient) -> None:
    resp = await client.post(
        "/batch",
        data={"urls": "https://truyen.test/t/chuong-1\n\n  \nhttps://truyen.test/t/chuong-1\nkhông-phải-url"},
    )
    assert resp.status_code == 200
    assert "Đang xử lý 1 chương" in resp.text


async def test_batch_with_no_valid_url_says_so(client: AsyncClient) -> None:
    resp = await client.post("/batch", data={"urls": "linh tinh\n\n"})
    assert "Chưa có địa chỉ nào hợp lệ" in resp.text


async def test_batch_adds_chapters_into_one_series_sorted_by_number(
    app: FastAPI, client: AsyncClient
) -> None:
    """Dán nhiều chương lộn xộn: phải gộp vào MỘT bộ và hiện ra theo đúng thứ tự chương."""
    _use_mock_fetcher(app)
    base = "https://truyen.test/truyen-abc"

    # Cố tình dán ngược thứ tự để chứng minh việc sắp xếp là thật.
    steps = [f"{base}/chuong-3", f"{base}/chuong-1", f"{base}/chuong-2"]
    remaining = "\n".join(steps)
    done = 0
    while remaining:
        resp = await client.post(
            "/batch/step",
            data={"urls": remaining, "done": str(done), "total": str(len(steps))},
        )
        assert resp.status_code == 200
        done += 1
        remaining = (
            resp.text.split('name="urls" value="')[1].split('"')[0]
            if 'name="urls" value="' in resp.text
            else ""
        )
    assert done == len(steps)

    library = await client.get("/library")
    assert library.text.count('href="/series/') == 1  # gộp vào đúng một bộ

    series_id = library.text.split('href="/series/')[1].split('"')[0]
    page = await client.get(f"/series/{series_id}")
    assert "3 chương" in page.text
    order = [page.text.index(f"{base}/chuong-{n}") for n in (1, 2, 3)]
    assert order == sorted(order), "chương phải hiện theo số thứ tự, không theo lúc thêm"


async def test_batch_progress_counter_advances(app: FastAPI, client: AsyncClient) -> None:
    """Bộ đếm phải chạy 1/3, 2/3, 3/3.

    Trước đây nó hiện 1/3, 1/2, 1/1 vì mồi dùng hx-include="find input" — mà `find` chỉ lấy
    ĐÚNG MỘT phần tử, nên `done`/`total` không được gửi kèm và luôn về 0. Chuỗi vẫn chạy đúng
    nên test chức năng không thấy gì; chỉ nhìn màn hình mới lộ.
    """
    _use_mock_fetcher(app)
    base = "https://truyen.test/truyen-abc"
    steps = [f"{base}/chuong-1", f"{base}/chuong-2", f"{base}/chuong-3"]

    remaining, done, seen = "\n".join(steps), 0, []
    while remaining:
        resp = await client.post(
            "/batch/step", data={"urls": remaining, "done": str(done), "total": "3"}
        )
        done += 1
        seen.append(f"{done}/3")
        assert f"{done}/3" in resp.text, f"buoc {done} hien sai bo dem"
        remaining = (
            resp.text.split('name="urls" value="')[1].split('"')[0]
            if 'name="urls" value="' in resp.text
            else ""
        )

    assert seen == ["1/3", "2/3", "3/3"]


async def test_batch_reports_a_chapter_that_was_already_there(
    app: FastAPI, client: AsyncClient
) -> None:
    _use_mock_fetcher(app)
    url = "https://truyen.test/truyen-abc/chuong-9"
    await client.post("/read", data={"url": url})

    resp = await client.post("/batch/step", data={"urls": url, "done": "0", "total": "1"})
    assert "đã có sẵn" in resp.text


async def test_one_bad_url_does_not_stop_the_batch(app: FastAPI, client: AsyncClient) -> None:
    """URL hỏng phải được báo lỗi rồi đi tiếp, không kéo đổ cả mẻ."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "hong" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, text=_story_html(f"Chương tại {request.url.path}"))

    app.state.app_state.fetcher = Fetcher(
        user_agent="t", delay_seconds=0, max_retries=0, transport=httpx.MockTransport(handler)
    )

    bad = "https://truyen.test/truyen-abc/chuong-hong"
    good = "https://truyen.test/truyen-abc/chuong-7"

    first = await client.post(
        "/batch/step", data={"urls": f"{bad}\n{good}", "done": "0", "total": "2"}
    )
    assert first.status_code == 200
    assert "lỗi" in first.text
    assert good in first.text  # vẫn còn mồi cho URL kế tiếp

    second = await client.post("/batch/step", data={"urls": good, "done": "1", "total": "2"})
    assert "mới thêm" in second.text
    assert "Xong." in second.text


async def test_series_can_be_renamed_and_followed(app: FastAPI, client: AsyncClient) -> None:
    _use_mock_fetcher(app)
    await client.post("/read", data={"url": "https://truyen.test/truyen-abc/chuong-1"})
    library = await client.get("/library")
    series_id = library.text.split('href="/series/')[1].split('"')[0]

    renamed = await client.patch(f"/series/{series_id}", data={"title": "Đấu Phá Thương Khung"})
    assert renamed.status_code == 200
    assert "Đấu Phá Thương Khung" in renamed.text

    followed = await client.post(f"/series/{series_id}/follow", data={"followed": "true"})
    assert followed.status_code == 200
    assert "Bỏ theo dõi" in followed.text

    page = await client.get(f"/series/{series_id}")
    assert "Đấu Phá Thương Khung" in page.text


async def test_series_unknown_id_404(client: AsyncClient) -> None:
    assert (await client.get("/series/999999")).status_code == 404


async def test_feedback_note_is_saved_against_its_chapter(client: AsyncClient) -> None:
    read = await client.post("/read", data={"raw_text": "Lão giả đi.", "title": "Chương ghi chú"})
    chapter_id = read.headers["HX-Push-Url"].rsplit("/", 1)[1]

    saved = await client.post(
        "/feedback",
        data={
            "message": "Chỗ này thay từ chưa hợp ngữ cảnh",
            "chapter_cache_id": chapter_id,
            "chapter_title": "Chương ghi chú",
            "para_index": "2",
            "quote": "Lão giả đi.",
        },
    )
    assert saved.status_code == 200
    assert "Đã lưu" in saved.text

    page = await client.get("/feedback")
    assert "Chỗ này thay từ chưa hợp ngữ cảnh" in page.text
    assert "đoạn 3" in page.text  # stored 0-based, shown 1-based
    assert f'href="/reader/{chapter_id}"' in page.text


async def test_empty_feedback_is_rejected(client: AsyncClient) -> None:
    resp = await client.post("/feedback", data={"message": "   "})
    assert resp.status_code == 400
    assert (await client.get("/feedback")).text.count("note ") == 0


async def test_feedback_can_be_resolved_and_deleted(client: AsyncClient) -> None:
    await client.post("/feedback", data={"message": "Ghi chú thử"})
    page = await client.get("/feedback")
    assert "Ghi chú thử" in page.text

    resolved = await client.patch("/feedback/1", data={"resolved": "true", "show": "open"})
    assert resolved.status_code == 200
    assert "Ghi chú thử" not in resolved.text  # no longer in the "open" filter

    done = await client.get("/feedback", params={"show": "done"})
    assert "Ghi chú thử" in done.text

    deleted = await client.delete("/feedback/1", params={"show": "all"})
    assert deleted.status_code == 200
    assert "Ghi chú thử" not in deleted.text


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

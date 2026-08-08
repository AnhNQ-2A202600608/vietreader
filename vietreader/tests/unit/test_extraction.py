"""Phase 4 extraction tests. Real HTML fixtures (no network fetch) + a couple of synthetic
snippets for precise edge cases. See tests/fixtures/html/SOURCES.md for fixture provenance.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from vietreader.extraction.base import ExtractionError, from_raw_text
from vietreader.extraction.config_adapter import ConfigAdapter, SiteConfig
from vietreader.extraction.fetcher import Fetcher, FetchError
from vietreader.extraction.registry import Registry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
CONFIG_SITES = Path(__file__).resolve().parents[2] / "config" / "sites"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_config_adapter_matches_fixture_extracts_title_paragraphs_next_url() -> None:
    html = _read_fixture("quotes_toscrape_page1.html")
    config = SiteConfig.from_yaml(
        (CONFIG_SITES / "quotes.toscrape.com.yml").read_text(encoding="utf-8")
    )
    adapter = ConfigAdapter(config)

    chapter = adapter.extract(html, "https://quotes.toscrape.com/page/1/")

    assert chapter.title == "Quotes to Scrape"
    assert len(chapter.paragraphs) == 10  # 10 quotes on the page
    assert "The world as we have created it" in chapter.paragraphs[0]
    assert chapter.next_url == "https://quotes.toscrape.com/page/2/"


def test_relative_next_url_resolved_to_absolute() -> None:
    html = _read_fixture("quotes_toscrape_page1.html")
    config = SiteConfig.from_yaml(
        (CONFIG_SITES / "quotes.toscrape.com.yml").read_text(encoding="utf-8")
    )
    chapter = ConfigAdapter(config).extract(html, "https://quotes.toscrape.com/page/1/")
    assert chapter.next_url is not None
    assert chapter.next_url.startswith("https://quotes.toscrape.com/")


def test_no_adapter_falls_back_to_generic_still_gets_paragraphs() -> None:
    html = _read_fixture("vi_wikipedia_ho_hoan_kiem.html")
    registry = Registry()  # real config/sites/: no entry for vi.wikipedia.org -> generic

    chapter = registry.extract(html, "https://vi.wikipedia.org/wiki/H%E1%BB%93_Ho%C3%A0n_Ki%E1%BA%BFm")

    assert chapter.paragraphs
    assert "Hoàn Kiếm" in chapter.title


def test_strip_selectors_removes_configured_clutter() -> None:
    html = _read_fixture("quotes_toscrape_page1.html")
    config = SiteConfig(
        domain="quotes.toscrape.com",
        title="h1 a",
        content=".row.header-box + .row .col-md-8",
        paragraph_split="newline",
        strip_selectors=("div.tags",),
    )
    chapter = ConfigAdapter(config).extract(html, "https://quotes.toscrape.com/page/1/")
    joined = "\n".join(chapter.paragraphs)
    assert "deep-thoughts" not in joined
    assert "world as we have created it" in joined.lower()


def test_no_next_link_selector_match_returns_none_without_crash() -> None:
    html = "<html><body><h1>Title</h1><div class='c'><p>Nội dung.</p></div></body></html>"
    config = SiteConfig(
        domain="example.com",
        title="h1",
        content="div.c",
        paragraph_split="p",
        next_link="a#does-not-exist@href",
    )
    chapter = ConfigAdapter(config).extract(html, "https://example.com/chap/1")
    assert chapter.next_url is None
    assert chapter.paragraphs == ["Nội dung."]


def test_empty_html_raises_extraction_error() -> None:
    config = SiteConfig(domain="example.com", title="h1", content="div.c")
    with pytest.raises(ExtractionError):
        ConfigAdapter(config).extract("", "https://example.com/chap/1")


def test_content_selector_matching_nothing_raises_extraction_error() -> None:
    html = "<html><body><h1>Title</h1><p>orphan text, no content container</p></body></html>"
    config = SiteConfig(domain="example.com", title="h1", content="div.does-not-exist")
    with pytest.raises(ExtractionError):
        ConfigAdapter(config).extract(html, "https://example.com/chap/1")


def test_from_raw_text_splits_on_blank_lines_and_normalizes() -> None:
    raw = "Chương 1\r\n\r\nĐoạn một.   \r\nvẫn đoạn một.\r\n\r\n\r\n\r\nĐoạn hai.\r\n"
    chapter = from_raw_text(raw, title="Chương 1")

    assert chapter.title == "Chương 1"
    assert chapter.paragraphs == ["Chương 1", "Đoạn một.\nvẫn đoạn một.", "Đoạn hai."]
    assert chapter.next_url is None
    assert chapter.source_url is None


async def test_fetch_403_raises_fetch_error_with_paste_hint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    fetcher = Fetcher(user_agent="test-agent", max_retries=0, delay_seconds=0)
    with pytest.raises(FetchError, match="dán trực tiếp"):
        await fetcher.fetch("https://example.com/chap/1", transport=httpx.MockTransport(handler))


async def test_fetch_timeout_raises_fetch_error_with_paste_hint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    fetcher = Fetcher(user_agent="test-agent", max_retries=1, delay_seconds=0)
    with pytest.raises(FetchError, match="dán trực tiếp"):
        await fetcher.fetch("https://example.com/chap/1", transport=httpx.MockTransport(handler))

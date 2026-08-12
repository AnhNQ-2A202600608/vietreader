"""Phase 5 integration tests: pipeline orchestration wired to a real (in-memory) DB."""

from __future__ import annotations

from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from vietreader.core.dictionary import CompiledDictionary
from vietreader.core.models import Policy
from vietreader.db.repositories.chapter_cache import (
    ChapterCacheRepo,
    compute_raw_hash,
    compute_source_key,
)
from vietreader.db.repositories.dictionary import DictionaryRepo
from vietreader.db.repositories.llm_cache import LLMCacheRepo
from vietreader.db.repositories.run_log import RunLogRepo
from vietreader.extraction.fetcher import Fetcher
from vietreader.extraction.registry import Registry
from vietreader.llm.provider import FakeProvider
from vietreader.pipeline.process_chapter import process_chapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
CONFIG_SITES = Path(__file__).resolve().parents[2] / "config" / "sites"
QUOTES_URL = "https://quotes.toscrape.com/page/1/"


def _seed_dictionary(session: Session) -> list:
    repo = DictionaryRepo(session)
    repo.create(surface="world", display="world", policy=Policy.REPLACE, replacement="planet")
    repo.create(
        surface="choices", display="choices", policy=Policy.ASK, candidates=["choices", "decisions"]
    )
    repo.create(surface="miracle", display="miracle", policy=Policy.KEEP)
    session.commit()
    return repo.list_enabled()


def _quotes_transport() -> httpx.MockTransport:
    html = (FIXTURES / "quotes_toscrape_page1.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    return httpx.MockTransport(handler)


async def test_end_to_end_with_fake_provider_and_html_fixture(db_session: Session) -> None:
    entries = _seed_dictionary(db_session)
    dict_version_hash = CompiledDictionary.from_entries(entries).version_hash
    provider = FakeProvider(mode="correct", choose={"p0_s0": 0})  # keep "choices"
    fetcher = Fetcher(user_agent="test-agent", delay_seconds=0, transport=_quotes_transport())

    result = await process_chapter(
        source_url=QUOTES_URL,
        raw_text=None,
        title=None,
        dictionary_entries=entries,
        dict_version_hash=dict_version_hash,
        prompt_version="v1",
        model="test-model",
        provider=provider,
        chapter_cache_repo=ChapterCacheRepo(db_session),
        run_log_repo=RunLogRepo(db_session),
        llm_cache=LLMCacheRepo(db_session),
        registry=Registry(sites_dir=CONFIG_SITES),
        fetcher=fetcher,
    )
    db_session.commit()

    assert result.status == "ok"
    assert result.chapter.title == "Quotes to Scrape"
    assert "planet" in result.output_paragraphs[0]
    assert result.stats.replace_count == 1
    assert result.stats.ask_count == 1
    assert result.stats.llm_calls == 1
    assert result.stats.from_cache is False


async def test_second_call_hits_cache_with_zero_llm_calls(db_session: Session) -> None:
    entries = _seed_dictionary(db_session)
    dict_version_hash = CompiledDictionary.from_entries(entries).version_hash
    provider = FakeProvider(mode="correct", choose={"p0_s0": 0})
    fetcher = Fetcher(user_agent="test-agent", delay_seconds=0, transport=_quotes_transport())
    kwargs = dict(
        source_url=QUOTES_URL,
        raw_text=None,
        title=None,
        dictionary_entries=entries,
        dict_version_hash=dict_version_hash,
        prompt_version="v1",
        model="test-model",
        provider=provider,
        chapter_cache_repo=ChapterCacheRepo(db_session),
        run_log_repo=RunLogRepo(db_session),
        llm_cache=LLMCacheRepo(db_session),
        registry=Registry(sites_dir=CONFIG_SITES),
        fetcher=fetcher,
    )

    first = await process_chapter(**kwargs)
    db_session.commit()
    second = await process_chapter(**kwargs)
    db_session.commit()

    assert first.stats.from_cache is False
    assert second.stats.from_cache is True
    assert second.stats.llm_calls == 0
    assert second.output_paragraphs == first.output_paragraphs
    assert provider.call_count == 1  # only the first call actually hit the provider


async def test_dictionary_change_causes_cache_miss(db_session: Session) -> None:
    entries = _seed_dictionary(db_session)
    dict_version_hash_1 = CompiledDictionary.from_entries(entries).version_hash
    provider = FakeProvider(mode="correct", choose={"p0_s0": 0})
    fetcher = Fetcher(user_agent="test-agent", delay_seconds=0, transport=_quotes_transport())

    first = await process_chapter(
        source_url=QUOTES_URL,
        raw_text=None,
        title=None,
        dictionary_entries=entries,
        dict_version_hash=dict_version_hash_1,
        prompt_version="v1",
        model="test-model",
        provider=provider,
        chapter_cache_repo=ChapterCacheRepo(db_session),
        run_log_repo=RunLogRepo(db_session),
        llm_cache=LLMCacheRepo(db_session),
        registry=Registry(sites_dir=CONFIG_SITES),
        fetcher=fetcher,
    )
    db_session.commit()

    dict_repo = DictionaryRepo(db_session)
    dict_repo.create(surface="new-term", display="new-term", policy=Policy.KEEP)
    db_session.commit()
    entries_v2 = dict_repo.list_enabled()
    dict_version_hash_2 = CompiledDictionary.from_entries(entries_v2).version_hash
    assert dict_version_hash_2 != dict_version_hash_1

    second = await process_chapter(
        source_url=QUOTES_URL,
        raw_text=None,
        title=None,
        dictionary_entries=entries_v2,
        dict_version_hash=dict_version_hash_2,
        prompt_version="v1",
        model="test-model",
        provider=provider,
        chapter_cache_repo=ChapterCacheRepo(db_session),
        run_log_repo=RunLogRepo(db_session),
        llm_cache=LLMCacheRepo(db_session),
        registry=Registry(sites_dir=CONFIG_SITES),
        fetcher=fetcher,
    )
    db_session.commit()

    assert first.stats.from_cache is False
    assert second.stats.from_cache is False  # chapter cache miss: dict_version_hash changed
    # The LLM-level cache is keyed independently (prompt_version+model+term+candidates+
    # left+right -- spec §3.4), so it still hits even though the chapter cache missed;
    # dict_version_hash is not one of its components. That's the two-layer cache working
    # as designed, not a bug: reprocessing the chapter doesn't have to re-ask the LLM the
    # exact same disambiguation question.
    assert provider.call_count == 1


async def test_chapter_navigation_is_persisted_and_survives_a_cache_hit(
    db_session: Session,
) -> None:
    """The library reopens chapters from cache, so 'next chapter' has to come from the DB
    rather than from a fresh parse of the source page."""
    entries = _seed_dictionary(db_session)
    dict_version_hash = CompiledDictionary.from_entries(entries).version_hash
    provider = FakeProvider(mode="correct", choose={"p0_s0": 0})
    fetcher = Fetcher(user_agent="test-agent", delay_seconds=0, transport=_quotes_transport())
    repo = ChapterCacheRepo(db_session)
    kwargs = dict(
        source_url=QUOTES_URL,
        raw_text=None,
        title=None,
        dictionary_entries=entries,
        dict_version_hash=dict_version_hash,
        prompt_version="v1",
        model="test-model",
        provider=provider,
        chapter_cache_repo=repo,
        run_log_repo=RunLogRepo(db_session),
        llm_cache=LLMCacheRepo(db_session),
        registry=Registry(sites_dir=CONFIG_SITES),
        fetcher=fetcher,
    )

    first = await process_chapter(**kwargs)
    db_session.commit()

    assert first.chapter.next_url is not None
    stored = repo.get_by_id(first.chapter_cache_id)
    assert stored is not None
    assert stored.next_url == first.chapter.next_url

    second = await process_chapter(**kwargs)
    db_session.commit()
    assert second.stats.from_cache is True
    assert second.chapter.next_url == first.chapter.next_url


async def test_reopening_a_chapter_updates_its_reading_recency(db_session: Session) -> None:
    repo = ChapterCacheRepo(db_session)
    older = repo.put(
        source_key="k-old", url=None, title="Cũ", raw_hash="h1", raw_text="a",
        output_text="a", changelog_json="[]", dict_version_hash="d", prompt_version="v1",
        model="m",
    )
    newer = repo.put(
        source_key="k-new", url=None, title="Mới", raw_hash="h2", raw_text="b",
        output_text="b", changelog_json="[]", dict_version_hash="d", prompt_version="v1",
        model="m",
    )
    db_session.commit()
    assert [c.id for c in repo.list_recent()][0] == newer.id

    repo.touch(older.id)
    db_session.commit()
    assert [c.id for c in repo.list_recent()][0] == older.id


async def test_validator_failure_returns_raw_text_and_does_not_cache(db_session: Session) -> None:
    entries = _seed_dictionary(db_session)
    dict_version_hash = CompiledDictionary.from_entries(entries).version_hash
    provider = FakeProvider(mode="correct", choose={"p0_s0": 0})
    fetcher = Fetcher(user_agent="test-agent", delay_seconds=0, transport=_quotes_transport())
    chapter_cache_repo = ChapterCacheRepo(db_session)

    import vietreader.pipeline.process_chapter as pc_module

    original_apply_changes = pc_module.apply_changes

    def corrupting_apply_changes(paragraphs, changelog):  # type: ignore[no-untyped-def]
        output = original_apply_changes(paragraphs, changelog)
        return [p + "!!CORRUPTED!!" for p in output]

    pc_module.apply_changes = corrupting_apply_changes
    try:
        result = await process_chapter(
            source_url=QUOTES_URL,
            raw_text=None,
            title=None,
            dictionary_entries=entries,
            dict_version_hash=dict_version_hash,
            prompt_version="v1",
            model="test-model",
            provider=provider,
            chapter_cache_repo=chapter_cache_repo,
            run_log_repo=RunLogRepo(db_session),
            llm_cache=LLMCacheRepo(db_session),
            registry=Registry(sites_dir=CONFIG_SITES),
            fetcher=fetcher,
        )
    finally:
        pc_module.apply_changes = original_apply_changes
    db_session.commit()

    assert result.status == "validation_failed"
    assert any(v.startswith("I1:") for v in result.violations)
    assert result.output_paragraphs == result.chapter.paragraphs  # raw text returned, not corrupted

    raw_joined = "\n\n".join(result.chapter.paragraphs)
    source_key = compute_source_key(
        compute_raw_hash(raw_joined), dict_version_hash, "v1", "test-model"
    )
    assert chapter_cache_repo.get(source_key) is None  # HARD FAIL must not be cached

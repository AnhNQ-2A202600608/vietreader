"""Phase 5 repository tests against an in-memory DB."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from vietreader.core.dictionary import DictionaryEntryError
from vietreader.core.models import Policy
from vietreader.db.repositories.chapter_cache import ChapterCacheRepo
from vietreader.db.repositories.dictionary import DictionaryRepo
from vietreader.db.repositories.dictionary_version import DictionaryVersionRepo
from vietreader.db.repositories.llm_cache import LLMCacheRepo
from vietreader.db.repositories.position import PositionRepo
from vietreader.db.repositories.run_log import RunLogRepo
from vietreader.db.repositories.series import SeriesRepo


def test_dictionary_repo_create_get_update_delete(db_session: Session) -> None:
    repo = DictionaryRepo(db_session)
    entry = repo.create(
        surface="lão giả", display="Lão giả", policy=Policy.REPLACE, replacement="ông lão"
    )
    db_session.commit()

    fetched = repo.get(entry.id)
    assert fetched is not None
    assert fetched.surface == "lão giả"

    updated = repo.update(entry.id, replacement="ông cụ")
    db_session.commit()
    assert updated is not None
    assert updated.replacement == "ông cụ"

    assert repo.delete(entry.id) is True
    assert repo.get(entry.id) is None


def test_dictionary_repo_rejects_duplicate_surface(db_session: Session) -> None:
    repo = DictionaryRepo(db_session)
    repo.create(surface="linh lực", display="linh lực", policy=Policy.KEEP)
    db_session.commit()

    with pytest.raises(DictionaryEntryError):
        repo.create(surface="linh lực", display="linh lực", policy=Policy.KEEP)


def test_dictionary_repo_filters_by_policy_and_search(db_session: Session) -> None:
    repo = DictionaryRepo(db_session)
    repo.create(surface="lão giả", display="lão giả", policy=Policy.REPLACE, replacement="ông lão")
    repo.create(surface="linh lực", display="linh lực", policy=Policy.KEEP)
    db_session.commit()

    keep_only = repo.list(policy=Policy.KEEP)
    assert [e.surface for e in keep_only] == ["linh lực"]

    search_result = repo.list(search="giả")
    assert [e.surface for e in search_result] == ["lão giả"]


def test_llm_cache_repo_roundtrip(db_session: Session) -> None:
    repo = LLMCacheRepo(db_session)
    assert repo.get("k1") is None
    repo.set("k1", 2)
    db_session.commit()
    assert repo.get("k1") == 2
    repo.set("k1", 3)
    db_session.commit()
    assert repo.get("k1") == 3


def test_chapter_cache_repo_put_and_get(db_session: Session) -> None:
    repo = ChapterCacheRepo(db_session)
    assert repo.get("key-1") is None
    entry = repo.put(
        source_key="key-1",
        url="https://example.com",
        title="Chương 1",
        raw_hash="abc",
        raw_text="raw",
        output_text="output",
        changelog_json="[]",
        dict_version_hash="dv1",
        prompt_version="v1",
        model="m1",
    )
    db_session.commit()
    assert repo.get("key-1") is not None
    assert repo.get_by_id(entry.id) is not None


def test_chapter_cache_roundtrip_preserves_series_id(db_session: Session) -> None:
    series = SeriesRepo(db_session).get_or_create("https://example.com/story")
    repo = ChapterCacheRepo(db_session)
    entry = repo.put(
        source_key="key-series",
        url="https://example.com/story/chuong-1",
        title="Chương 1",
        raw_hash="series-hash",
        raw_text="raw",
        output_text="output",
        changelog_json="[]",
        dict_version_hash="dv1",
        prompt_version="v1",
        model="m1",
    )
    repo.set_series(entry.id, series.id)
    db_session.commit()

    fetched = repo.get_by_id(entry.id)
    assert fetched is not None
    assert fetched.series_id == series.id
    assert repo.list_recent()[0].series_id == series.id


def test_legacy_blank_cache_title_is_inferred_on_read(db_session: Session) -> None:
    repo = ChapterCacheRepo(db_session)
    entry = repo.put(
        source_key="legacy-blank-title",
        url=None,
        title="",
        raw_hash="legacy-title-hash",
        raw_text=(
            "Chương 88 — Cửa đá mở ra\n\n"
            "Ánh sáng từ bên trong khe cửa tràn ra khắp hành lang tối."
        ),
        output_text=(
            "Chương 88 — Cửa đá mở ra\n\n"
            "Ánh sáng từ bên trong khe cửa tràn ra khắp hành lang tối."
        ),
        changelog_json="[]",
        dict_version_hash="dv1",
        prompt_version="v1",
        model="m1",
    )
    db_session.commit()

    fetched = repo.get_by_id(entry.id)
    assert fetched is not None
    assert fetched.title == "Chương 88 — Cửa đá mở ra"


def test_dictionary_version_repo_is_idempotent(db_session: Session) -> None:
    repo = DictionaryVersionRepo(db_session)
    first = repo.ensure("hash-1", 3)
    second = repo.ensure("hash-1", 3)
    db_session.commit()

    assert first.id == second.id


def test_position_repo_upsert(db_session: Session) -> None:
    repo = PositionRepo(db_session)
    assert repo.get("series-1") is None
    repo.upsert("series-1", "https://example.com/c1", 5)
    db_session.commit()
    position = repo.get("series-1")
    assert position is not None
    assert position.para_index == 5

    repo.upsert("series-1", "https://example.com/c2", 9)
    db_session.commit()
    position = repo.get("series-1")
    assert position is not None
    assert position.url == "https://example.com/c2"
    assert position.para_index == 9


def test_run_log_repo_log_does_not_raise(db_session: Session) -> None:
    repo = RunLogRepo(db_session)
    repo.log(stage="test", level="INFO", message="hello")
    db_session.commit()

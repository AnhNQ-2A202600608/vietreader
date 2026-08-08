from __future__ import annotations

from vietreader.core.dictionary import DictionaryEntry
from vietreader.core.models import Policy, Span
from vietreader.llm.disambiguator import (
    DisambiguationRequest,
    cache_key,
    disambiguate_batch,
)
from vietreader.llm.provider import FakeProvider


def ask_entry(id: int, surface: str, candidates: list[str]) -> DictionaryEntry:
    return DictionaryEntry(
        id=id, surface=surface, display=surface, policy=Policy.ASK, candidates=candidates
    )


def request(
    id: str, entry: DictionaryEntry, left: str = "trái", right: str = "phải"
) -> DisambiguationRequest:
    span = Span(
        start=0, end=len(entry.surface), text=entry.surface, entry_id=entry.id, policy=Policy.ASK
    )
    return DisambiguationRequest(id=id, span=span, entry=entry, left=left, right=right)


class DictCache:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.get_calls = 0
        self.set_calls = 0

    def get(self, key: str) -> int | None:
        self.get_calls += 1
        return self.store.get(key)

    def set(self, key: str, choice_index: int) -> None:
        self.set_calls += 1
        self.store[key] = choice_index


async def test_happy_path_three_spans() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn", "vị này"])
    reqs = [request(f"p0_s{i}", entry) for i in range(3)]
    provider = FakeProvider(mode="correct", choose={r.id: 2 for r in reqs})

    results = await disambiguate_batch(reqs, provider, model="test-model")

    assert len(results) == 3
    assert provider.call_count == 1
    for r in results:
        assert r.decision is not None
        assert r.decision.choice_index == 2
        assert r.decision.replacement == "vị này"
        assert r.decision.source == "llm"


async def test_broken_json_retries_then_falls_back_to_keep() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn"])
    reqs = [request("p0_s0", entry)]
    provider = FakeProvider(mode="broken_json")

    results = await disambiguate_batch(reqs, provider, model="test-model", max_retries=2)

    assert provider.call_count == 3  # 1 initial + 2 retries
    assert len(results) == 1
    assert results[0].decision is None
    assert results[0].warning is not None


async def test_choice_out_of_range_falls_back_to_keep() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn"])
    reqs = [request("p0_s0", entry)]
    provider = FakeProvider(mode="out_of_range")

    results = await disambiguate_batch(reqs, provider, model="test-model")

    assert len(results) == 1
    assert results[0].decision is None
    assert results[0].warning is not None


async def test_missing_id_falls_back_others_still_ok() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn"])
    reqs = [request("p0_s0", entry), request("p0_s1", entry)]
    provider = FakeProvider(mode="missing_id")  # drops the response item for the first request

    results = await disambiguate_batch(reqs, provider, model="test-model")

    by_id = {r.id: r for r in results}
    assert by_id["p0_s0"].decision is None
    assert by_id["p0_s0"].warning is not None
    assert by_id["p0_s1"].decision is not None


async def test_provider_timeout_falls_back_without_crashing() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn"])
    reqs = [request("p0_s0", entry)]
    provider = FakeProvider(mode="timeout")

    results = await disambiguate_batch(reqs, provider, model="test-model", max_retries=1)

    assert provider.call_count == 2  # 1 initial + 1 retry
    assert results[0].decision is None


async def test_hundred_spans_split_into_three_batches_40_40_20() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn"])
    reqs = [request(f"p0_s{i}", entry) for i in range(100)]
    provider = FakeProvider(mode="correct")

    results = await disambiguate_batch(reqs, provider, model="test-model", batch_size=40)

    assert len(results) == 100
    assert provider.call_count == 3


async def test_no_ask_spans_means_zero_provider_calls() -> None:
    provider = FakeProvider(mode="correct")

    results = await disambiguate_batch([], provider, model="test-model")

    assert results == []
    assert provider.call_count == 0


async def test_cache_hit_avoids_second_provider_call() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn"])
    reqs = [request("p0_s0", entry)]
    provider = FakeProvider(mode="correct")
    cache = DictCache()

    first = await disambiguate_batch(reqs, provider, model="test-model", cache=cache)
    second = await disambiguate_batch(reqs, provider, model="test-model", cache=cache)

    assert provider.call_count == 1
    assert first[0].decision is not None
    assert second[0].decision is not None
    assert first[0].decision.choice_index == second[0].decision.choice_index


async def test_changing_prompt_version_causes_cache_miss() -> None:
    entry = ask_entry(1, "đạo hữu", ["đạo hữu", "bạn"])
    reqs = [request("p0_s0", entry)]
    provider = FakeProvider(mode="correct")
    cache = DictCache()

    await disambiguate_batch(reqs, provider, model="test-model", prompt_version="v1", cache=cache)
    await disambiguate_batch(reqs, provider, model="test-model", prompt_version="v2", cache=cache)

    assert provider.call_count == 2


def test_cache_key_changes_with_each_component() -> None:
    base = cache_key("v1", "model-a", "term", ["a", "b"], "left", "right")
    assert base != cache_key("v2", "model-a", "term", ["a", "b"], "left", "right")
    assert base != cache_key("v1", "model-b", "term", ["a", "b"], "left", "right")
    assert base != cache_key("v1", "model-a", "term2", ["a", "b"], "left", "right")
    assert base != cache_key("v1", "model-a", "term", ["a", "c"], "left", "right")
    assert base != cache_key("v1", "model-a", "term", ["a", "b"], "left2", "right")
    assert base != cache_key("v1", "model-a", "term", ["a", "b"], "left", "right2")

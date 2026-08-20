"""Offline tests for AnthropicProvider using httpx.MockTransport (no real network calls).

A separate, real-network smoke test lives in tests/integration/test_anthropic_live.py,
marked @pytest.mark.live and skipped by default.
"""

from __future__ import annotations

import json

import httpx
import pytest

from vietreader.llm.anthropic import AnthropicProvider
from vietreader.llm.provider import DisambiguationItem

MODEL = "claude-haiku-4-5-20251001"


def _make_handler(expected_status: int = 200, body: dict | None = None):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["payload"] = json.loads(request.content)
        if expected_status != 200:
            return httpx.Response(expected_status, json={"error": "boom"})
        return httpx.Response(200, json=body)

    return handler, captured


def _one_item(id: str = "p0_s0", left: str = "", right: str = "") -> list[DisambiguationItem]:
    return [
        DisambiguationItem(
            id=id, term="đạo hữu", left=left, right=right, candidates=["đạo hữu", "bạn"]
        )
    ]


async def test_disambiguate_sends_expected_payload_and_parses_text_response() -> None:
    response_body = {
        "content": [{"type": "text", "text": '[{"id": "p0_s0", "choice": 1}]'}],
    }
    handler, captured = _make_handler(body=response_body)
    provider = AnthropicProvider(
        api_key="test-key", model=MODEL, transport=httpx.MockTransport(handler)
    )
    items = _one_item(left="trái", right="phải")

    raw = await provider.disambiguate(items, temperature=0.0, max_tokens=40)

    assert raw == '[{"id": "p0_s0", "choice": 1}]'
    request = captured["request"]
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"]
    payload = captured["payload"]
    assert payload["model"] == MODEL
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 40
    assert "đạo hữu" in payload["messages"][0]["content"]
    assert "p0_s0" in payload["messages"][0]["content"]


async def test_disambiguate_concatenates_multiple_text_blocks() -> None:
    response_body = {
        "content": [
            {"type": "text", "text": "[{"},
            {"type": "text", "text": '"id": "p0_s0", "choice": 0}]'},
        ],
    }
    handler, _ = _make_handler(body=response_body)
    provider = AnthropicProvider(
        api_key="test-key", model=MODEL, transport=httpx.MockTransport(handler)
    )

    raw = await provider.disambiguate(_one_item(), temperature=0.0, max_tokens=40)

    assert raw == '[{"id": "p0_s0", "choice": 0}]'


async def test_disambiguate_raises_on_http_error_status() -> None:
    handler, _ = _make_handler(expected_status=401)
    provider = AnthropicProvider(
        api_key="bad-key", model=MODEL, transport=httpx.MockTransport(handler)
    )

    with pytest.raises(httpx.HTTPStatusError):
        await provider.disambiguate(_one_item(), temperature=0.0, max_tokens=40)


async def test_unknown_prompt_version_fails_before_network() -> None:
    provider = AnthropicProvider(
        api_key="test-key",
        model=MODEL,
        prompt_version="does-not-exist",
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    with pytest.raises(ValueError, match="prompt version"):
        await provider.disambiguate(_one_item(), temperature=0.0, max_tokens=40)

"""Anthropic LLMProvider implementation: plain httpx, no SDK lock-in (spec §1.1)."""

from __future__ import annotations

import json
from importlib import resources

import httpx

from vietreader.llm.provider import DisambiguationItem

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

_PROMPT_TEMPLATE = (
    resources.files("vietreader.llm.prompts")
    .joinpath("disambiguate.v1.txt")
    .read_text(encoding="utf-8")
)


def _build_prompt(items: list[DisambiguationItem]) -> str:
    items_json = json.dumps(
        [
            {
                "id": item.id,
                "term": item.term,
                "left": item.left,
                "right": item.right,
                "candidates": item.candidates,
            }
            for item in items
        ],
        ensure_ascii=False,
    )
    return _PROMPT_TEMPLATE.replace("{{ITEMS_JSON}}", items_json)


class AnthropicProvider:
    """LLMProvider backed by the real Anthropic Messages API.

    `transport` is an injection point for tests (httpx.MockTransport) so the request/response
    handling can be exercised offline; it is left unset (real network) in production.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._transport = transport

    async def disambiguate(
        self,
        items: list[DisambiguationItem],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        prompt = _build_prompt(items)
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return "".join(block["text"] for block in data["content"] if block["type"] == "text")

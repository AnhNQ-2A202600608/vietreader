"""Live smoke test against the real Anthropic API. Skipped by default (spec §Phase 3 acceptance).

Run explicitly with: pytest -m live --run-live
Requires VIETREADER_LLM_API_KEY (or ANTHROPIC_API_KEY) to be set in the environment.
"""

from __future__ import annotations

import os

import pytest

from vietreader.llm.anthropic import AnthropicProvider
from vietreader.llm.provider import DisambiguationItem

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_disambiguate_real_api() -> None:
    api_key = os.environ.get("VIETREADER_LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip(
            "No live LLM credentials in environment "
            "(VIETREADER_LLM_API_KEY / ANTHROPIC_API_KEY not set) — NOT RUN."
        )

    provider = AnthropicProvider(api_key=api_key, model="claude-haiku-4-5-20251001")
    items = [
        DisambiguationItem(
            id="p0_s0",
            term="đạo hữu",
            left="Hắn quay sang nhìn",
            right="và nói: hãy cẩn thận.",
            candidates=["đạo hữu", "bạn", "vị này"],
        )
    ]

    raw = await provider.disambiguate(items, temperature=0.0, max_tokens=64)

    assert raw.strip()

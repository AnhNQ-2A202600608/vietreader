"""LLMCacheRepo: DB-backed CacheBackend for llm.disambiguator (structurally implements the
CacheBackend Protocol: get(key) -> int | None, set(key, choice_index) -> None)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from vietreader.db.models import LLMCacheRow


class LLMCacheRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> int | None:
        row = self._session.get(LLMCacheRow, key)
        if row is None:
            return None
        data = json.loads(row.response_json)
        choice = data.get("choice")
        return choice if isinstance(choice, int) else None

    def set(self, key: str, choice_index: int) -> None:
        row = self._session.get(LLMCacheRow, key)
        payload = json.dumps({"choice": choice_index})
        if row is None:
            self._session.add(LLMCacheRow(cache_key=key, response_json=payload))
        else:
            row.response_json = payload
        self._session.flush()

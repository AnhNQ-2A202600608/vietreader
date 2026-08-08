"""Phase 9: the seed dictionary has >= 60 entries covering all 3 policies, and loading it
is idempotent (safe to run against an already-seeded DB)."""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from vietreader.core.dictionary import DictionaryEntryError
from vietreader.core.models import Policy
from vietreader.db.repositories.dictionary import DictionaryRepo

SEED_PATH = Path(__file__).resolve().parents[2] / "config" / "seed_dictionary.yml"


def test_seed_file_has_at_least_60_entries_covering_all_policies() -> None:
    data = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    entries = data["entries"]
    assert len(entries) >= 60

    policies = {e["policy"] for e in entries}
    assert policies == {"keep", "replace", "ask"}

    surfaces = [e["surface"] for e in entries]
    assert len(surfaces) == len(set(surfaces)), "duplicate surface in seed dictionary"


def test_seed_dictionary_loads_and_is_idempotent(db_session: Session) -> None:
    data = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    repo = DictionaryRepo(db_session)

    created = 0
    for entry in data["entries"]:
        repo.create(
            surface=entry["surface"],
            display=entry["display"],
            policy=Policy(entry["policy"]),
            replacement=entry.get("replacement"),
            candidates=entry.get("candidates") or [],
        )
        created += 1
    db_session.commit()
    assert created == len(data["entries"])

    skipped = 0
    for entry in data["entries"]:
        try:
            repo.create(
                surface=entry["surface"],
                display=entry["display"],
                policy=Policy(entry["policy"]),
                replacement=entry.get("replacement"),
                candidates=entry.get("candidates") or [],
            )
        except DictionaryEntryError:
            db_session.rollback()
            skipped += 1
    assert skipped == len(data["entries"])

    assert len(repo.list()) == len(data["entries"])

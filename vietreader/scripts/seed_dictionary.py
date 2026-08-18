"""Load config/seed_dictionary.yml into the configured DB. Idempotent: skips entries whose
surface already exists (does not overwrite/duplicate on repeated runs).

Usage: python scripts/seed_dictionary.py

Chỉ insert những entry mới chưa có trong database, không chèn trùng lặp.
Đọc danh sách surface đã có trong 1 query duy nhất để tối ưu tốc độ kết nối qua mạng khi deploy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietreader.core.dictionary import DictionaryEntryError  # noqa: E402
from vietreader.core.models import Policy  # noqa: E402
from vietreader.db.base import create_db_engine, create_session_factory  # noqa: E402
from vietreader.db.models import Base, DictionaryEntryRow  # noqa: E402
from vietreader.db.repositories.dictionary import DictionaryRepo  # noqa: E402
from vietreader.settings import get_settings  # noqa: E402

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "seed_dictionary.yml"


def main() -> None:
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    data = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    created, skipped = 0, 0

    with session_factory() as session:
        existing_surfaces = set(
            session.scalars(select(DictionaryEntryRow.surface)).all()
        )
        repo = DictionaryRepo(session)
        for entry in data["entries"]:
            surface = entry["surface"].strip().lower()
            if surface in existing_surfaces:
                skipped += 1
                continue
            try:
                repo.create(
                    surface=surface,
                    display=entry.get("display") or surface,
                    policy=Policy(entry["policy"]),
                    replacement=entry.get("replacement"),
                    candidates=entry.get("candidates") or [],
                )
                session.commit()
                existing_surfaces.add(surface)
                created += 1
            except DictionaryEntryError:
                session.rollback()
                skipped += 1

    print(f"Seeded {created} new entries into {settings.database_url} ({skipped} already existed).")


if __name__ == "__main__":
    main()

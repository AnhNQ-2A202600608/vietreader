"""Deployment settings must fail closed when production secrets are incomplete."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vietreader.settings import Settings


def test_require_postgres_rejects_sqlite_fallback() -> None:
    with pytest.raises(ValidationError, match="VIETREADER_DATABASE_URL is not PostgreSQL"):
        Settings(database_url="sqlite:///./temporary.db", require_postgres=True)


def test_require_postgres_accepts_neon_url() -> None:
    settings = Settings(
        database_url=(
            "postgresql://owner:secret@ep-example-pooler.ap-southeast-1.aws.neon.tech/db"
            "?sslmode=require"
        ),
        require_postgres=True,
    )

    assert settings.require_postgres is True


def test_production_auth_requires_both_credentials() -> None:
    with pytest.raises(ValidationError, match="AUTH_USERNAME/PASSWORD are missing"):
        Settings(require_auth=True)

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_missing_database_url_fails_with_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, session_secret="test-session-secret-0123456789")

    assert "database_url" in str(exc_info.value)

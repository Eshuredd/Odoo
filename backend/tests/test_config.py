from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import BACKEND_DIR, Settings
from app.db.session import resolve_database_url


def test_default_path_is_independent_of_working_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    url = resolve_database_url("sqlite:///data/subcadence.db")
    assert Path(url.database) == BACKEND_DIR / "data" / "subcadence.db"


def test_environment_settings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'env.db').as_posix()}")
    monkeypatch.setenv("API_PORT", "8123")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000","http://127.0.0.1:3000"]')
    settings = Settings(_env_file=None)
    assert settings.api_port == 8123
    assert settings.database_url.endswith("env.db")
    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


@pytest.mark.parametrize("origin", ["*", "https://*.example.test", "http://localhost:3000/path", "null"])
def test_cors_rejects_wildcards_and_non_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


@pytest.mark.parametrize("url", ["postgresql://localhost/db", "sqlite:///file.db?mode=ro"])
def test_unsupported_database_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError, match="Only standard SQLite"):
        resolve_database_url(url)


def test_example_env_is_loadable_and_has_no_default_secrets() -> None:
    settings = Settings(_env_file=BACKEND_DIR.parent / ".env.example")
    assert settings.api_host == "127.0.0.1"
    assert settings.auth_secret_key is None or settings.auth_secret_key.get_secret_value() == ""
    assert settings.admin_password is None or settings.admin_password.get_secret_value() == ""

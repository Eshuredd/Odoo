from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.engine import URL

from app.core.config import BACKEND_DIR, Settings
from app.db.session import create_db_engine
from app.main import create_app


def migration_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return URL.create("sqlite", database=str(tmp_path / "isolated.db")).render_as_string()


@pytest.fixture
def migrated_url(database_url: str) -> str:
    command.upgrade(migration_config(database_url), "head")
    return database_url


@pytest.fixture
def engine(migrated_url: str) -> Iterator[Engine]:
    engine = create_db_engine(migrated_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def client(migrated_url: str) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url=migrated_url)
    with TestClient(create_app(settings)) as client:
        yield client

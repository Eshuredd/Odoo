from collections.abc import Iterator
from pathlib import Path
from datetime import datetime, timedelta
import secrets

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.engine import URL

from app.core.config import BACKEND_DIR, Settings
from app.db.session import create_db_engine
from app.db.base import utc_now
from app.main import create_app
from app.core.security import hash_password
from app.models import User, UserRole

# Synthetic test input only. There are no embedded application/demo credentials.
TEST_PASSWORD = "Abcdefgh!"


class ManualClock:
    def __init__(self) -> None:
        self.now = utc_now().replace(microsecond=0)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: int) -> None:
        self.now += timedelta(**kwargs)


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


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def auth_settings(migrated_url: str) -> Settings:
    return Settings(
        _env_file=None, database_url=migrated_url, auth_secret_key=secrets.token_urlsafe(48),
        app_env="development", smtp_host="", smtp_username="", smtp_password="", smtp_from_email="",
        password_reset_base_url="http://localhost:3000/reset-password",
    )


@pytest.fixture
def auth_client(auth_settings: Settings, clock: ManualClock) -> Iterator[TestClient]:
    with TestClient(create_app(auth_settings, clock=clock)) as client:
        yield client


@pytest.fixture
def make_user(auth_client: TestClient, clock: ManualClock):
    def create(role: UserRole = UserRole.CUSTOMER, email: str | None = None) -> User:
        with auth_client.app.state.session_factory() as session, session.begin():
            user = User(email=email or f"{role.value}@example.com", role=role,
                        password_hash=hash_password(TEST_PASSWORD), created_at=clock(), updated_at=clock())
            session.add(user)
            session.flush()
            return user
    return create


@pytest.fixture
def bearer_headers(auth_client: TestClient):
    def headers(user: User) -> dict[str, str]:
        response = auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        assert response.status_code == 200
        return {"Authorization": "Bearer " + response.json()["access_token"]}
    return headers


@pytest.fixture
def commerce(auth_client: TestClient, make_user, bearer_headers):
    from commercial_helpers import Commerce
    return Commerce(auth_client, bearer_headers(make_user(UserRole.ADMIN)))

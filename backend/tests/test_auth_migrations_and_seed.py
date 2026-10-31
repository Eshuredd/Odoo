import subprocess
import sys

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import BACKEND_DIR
from app.core.errors import ServiceError
from app.core.security import verify_password
from app.db.session import create_db_engine, create_session_factory
from app.models import AuditLog, User, UserRole
from app.services.auth import seed_admin
from conftest import TEST_PASSWORD, ManualClock, migration_config


def test_stage1_upgrade_preserves_existing_users_and_audit_actors(database_url: str) -> None:
    config = migration_config(database_url)
    command.upgrade(config, "0001_foundation")
    engine = create_db_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id, email, password_hash, role) VALUES (7, 'existing@example.com', 'opaque-existing-hash', 'staff')"))
            connection.execute(text("INSERT INTO audit_logs (actor_id, action, entity, entity_id) VALUES (7, 'existing', 'user', '7')"))
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            user = connection.execute(text("SELECT id, email, password_hash, role, auth_version FROM users")).one()
            assert tuple(user) == (7, "existing@example.com", "opaque-existing-hash", "staff", 0)
            assert connection.scalar(text("SELECT actor_id FROM audit_logs")) == 7
        inspector = inspect(engine)
        assert inspector.get_foreign_keys("password_reset_tokens")[0]["referred_table"] == "users"
        assert {index["name"] for index in inspector.get_indexes("password_reset_tokens")} == {
            "ix_password_reset_tokens_user_id_consumed_at", "ix_password_reset_tokens_expires_at",
        }
        assert inspector.get_indexes("email_outbox")[0]["name"] == "ix_email_outbox_created_at_id"
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("UPDATE users SET auth_version=-1 WHERE id=7"))
        command.downgrade(config, "0001_foundation")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT actor_id FROM audit_logs")) == 7
            assert connection.scalar(text("SELECT email FROM users WHERE id=7")) == "existing@example.com"
        command.upgrade(config, "head")
    finally:
        engine.dispose()


def test_admin_seed_is_idempotent_and_does_not_change_credentials(engine, clock: ManualClock) -> None:
    factory = create_session_factory(engine)
    with factory() as session:
        first_id, created = seed_admin(session, email=" ADMIN@EXAMPLE.COM ", password=TEST_PASSWORD, clock=clock)
    assert created is True
    with factory() as session:
        second_id, created = seed_admin(session, email="admin@example.com", password="Different!password", clock=clock)
    assert (second_id, created) == (first_id, False)
    with factory() as session:
        user = session.get(User, first_id)
        assert user.role == UserRole.ADMIN
        assert verify_password(user.password_hash, TEST_PASSWORD)
        assert not verify_password(user.password_hash, "Different!password")
        assert session.scalars(select(AuditLog)).one().action == "user.admin_seeded"


@pytest.mark.parametrize("role", [UserRole.CUSTOMER, UserRole.STAFF])
def test_seed_never_promotes_existing_account(auth_client, make_user, role: UserRole, clock: ManualClock) -> None:
    user = make_user(role)
    with auth_client.app.state.session_factory() as session:
        with pytest.raises(ServiceError, match="non-admin"):
            seed_admin(session, email=user.email, password=TEST_PASSWORD, clock=clock)
    with auth_client.app.state.session_factory() as session:
        assert session.get(User, user.id).role == role


@pytest.mark.parametrize("email,password", [("invalid", TEST_PASSWORD), ("admin@example.com", "weak")])
def test_seed_validates_email_and_password(engine, clock: ManualClock, email: str, password: str) -> None:
    with create_session_factory(engine)() as session, pytest.raises(ValueError):
        seed_admin(session, email=email, password=password, clock=clock)


def test_seed_cli_reads_environment_and_is_safe(migrated_url: str, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_url)
    monkeypatch.setenv("ADMIN_EMAIL", "cli-admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", TEST_PASSWORD)
    first = subprocess.run([sys.executable, "-m", "scripts.seed_admin"], cwd=BACKEND_DIR, capture_output=True, text=True)
    second = subprocess.run([sys.executable, "-m", "scripts.seed_admin"], cwd=BACKEND_DIR, capture_output=True, text=True)
    assert first.returncode == second.returncode == 0
    assert "Admin created" in first.stdout
    assert "credentials unchanged" in second.stdout
    assert TEST_PASSWORD not in first.stdout + first.stderr + second.stdout + second.stderr
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    missing = subprocess.run([sys.executable, "-m", "scripts.seed_admin"], cwd=BACKEND_DIR, capture_output=True, text=True)
    assert missing.returncode == 1
    assert "ADMIN_EMAIL and ADMIN_PASSWORD are required" in missing.stderr

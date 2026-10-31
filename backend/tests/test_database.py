from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from shutil import copytree

import pytest
from alembic import command
from sqlalchemy import Column, Engine, MetaData, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR
from app.db.base import Base, UTCDateTime
from app.db.session import create_db_engine, create_session_factory
from app.models import AuditLog, User, UserRole
from conftest import migration_config

# Deliberately non-credential fixture marker: no authentication exists in Stage 1.
HASH_MARKER = "test-only-opaque-hash"


def insert_user(connection: Connection, email: str = "person@example.test", role: str = "customer") -> int:
    result = connection.execute(text(
        "INSERT INTO users (email, password_hash, role) VALUES (:email, :hash, :role)"
    ), {"email": email, "hash": HASH_MARKER, "role": role})
    return result.lastrowid


def test_initial_migration_and_metadata_match(database_url: str) -> None:
    config = migration_config(database_url)
    command.upgrade(config, "head")
    engine = create_db_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == {"users", "audit_logs", "alembic_version"}
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_foundation"
        command.check(config)
        command.upgrade(config, "head")  # Repeated upgrade must be harmless.
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")
    finally:
        engine.dispose()


def test_future_timestamp_migration_can_be_generated_and_applied(
    migrated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Copy the migration environment and metadata, leaving source and developer DB alone.
    script_dir = tmp_path / "migration_scripts"
    copytree(BACKEND_DIR / "alembic", script_dir, ignore=lambda _path, names: [
        name for name in names if name == "__pycache__"
    ])
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    metadata.tables["users"].append_column(Column("last_seen_at", UTCDateTime(), nullable=True))
    monkeypatch.setattr(Base, "metadata", metadata)
    config = migration_config(migrated_url)
    config.set_main_option("script_location", str(script_dir))
    revision = command.revision(config, message="test timestamp addition", autogenerate=True)
    assert revision is not None
    assert "sa.DateTime()" in Path(revision.path).read_text(encoding="utf-8")
    command.upgrade(config, "head")
    command.check(config)


def test_sqlite_pragmas_apply_to_every_connection(engine: Engine) -> None:
    with engine.connect() as first, engine.connect() as second:
        for connection in (first, second):
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert connection.scalar(text("PRAGMA busy_timeout")) == 5000
            assert connection.scalar(text("PRAGMA journal_mode")) == "wal"


def test_memory_database_does_not_require_wal() -> None:
    engine = create_db_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA journal_mode")) == "memory"
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        engine.dispose()


def test_engine_creates_nested_database_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "data" / "local.db"
    engine = create_db_engine(f"sqlite:///{path.as_posix()}")
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
        assert path.is_file()
    finally:
        engine.dispose()


def test_email_unique_case_insensitively_at_database_level(engine: Engine) -> None:
    with engine.begin() as connection:
        insert_user(connection, "Customer@Example.test")
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert_user(connection, "customer@example.TEST")


@pytest.mark.parametrize("role", ["admin", "staff", "customer"])
def test_supported_roles_at_database_level(engine: Engine, role: str) -> None:
    with engine.begin() as connection:
        insert_user(connection, role=role)


@pytest.mark.parametrize("role", ["superuser", "ADMIN", ""])
def test_invalid_roles_rejected_at_database_level(engine: Engine, role: str) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert_user(connection, role=role)


def test_foreign_key_rejects_missing_actor(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO audit_logs (actor_id, action, entity, entity_id) "
            "VALUES (999, 'created', 'user', '999')"
        ))


def test_audit_survives_actor_deletion_and_ids_are_not_reused(engine: Engine) -> None:
    with engine.begin() as connection:
        actor_id = insert_user(connection)
        connection.execute(text(
            "INSERT INTO audit_logs (actor_id, action, entity, entity_id) "
            "VALUES (:actor, 'created', 'user', :entity_id)"
        ), {"actor": actor_id, "entity_id": str(actor_id)})
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": actor_id})
        assert connection.scalar(text("SELECT actor_id FROM audit_logs")) is None
        assert insert_user(connection) > actor_id


def test_typed_models_defaults_utc_and_json(engine: Engine) -> None:
    local = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    with Session(engine) as session:
        with session.begin():
            user = User(email="typed@example.test", password_hash=HASH_MARKER, role=UserRole.STAFF)
            session.add(user)
            session.flush()
            audit = AuditLog(actor_id=user.id, action="created", entity="user", entity_id=str(user.id),
                             timestamp=local, detail={"source": "test", "fields": ["email"]})
            session.add(audit)
        session.expire_all()
        assert user.role is UserRole.STAFF
        assert user.is_active is True
        assert user.created_at.tzinfo is UTC
        assert user.updated_at.tzinfo is UTC
        assert audit.timestamp == local.astimezone(UTC)
        assert audit.detail == {"source": "test", "fields": ["email"]}
        previous_update = user.updated_at
        user.is_active = False
        session.commit()
        session.refresh(user)
        assert user.updated_at > previous_update


def test_naive_timestamps_rejected(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(User(email="naive@example.test", password_hash=HASH_MARKER,
                         role=UserRole.CUSTOMER, created_at=datetime(2026, 1, 1)))
        with pytest.raises(StatementError, match="Timestamps must include a timezone"):
            session.commit()


def test_failed_transaction_rolls_back(engine: Engine) -> None:
    factory = create_session_factory(engine)
    with pytest.raises(IntegrityError), factory() as session, session.begin():
        session.add(User(email="rollback@example.test", password_hash=HASH_MARKER, role=UserRole.ADMIN))
        session.flush()
        session.add(User(email="ROLLBACK@example.test", password_hash=HASH_MARKER, role=UserRole.STAFF))
    with factory() as session:
        assert session.scalar(text("SELECT count(*) FROM users")) == 0


def test_uncommitted_session_is_rolled_back(engine: Engine) -> None:
    with create_session_factory(engine)() as session:
        session.add(User(email="uncommitted@example.test", password_hash=HASH_MARKER, role=UserRole.ADMIN))
        session.flush()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 0


def test_begin_immediate_acquires_write_transaction(engine: Engine) -> None:
    from sqlalchemy import event

    statements: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with engine.connect().execution_options(sqlite_begin_mode="IMMEDIATE") as connection:
            with connection.begin():
                insert_user(connection)
        assert "BEGIN IMMEDIATE" in statements
    finally:
        event.remove(engine, "before_cursor_execute", record)

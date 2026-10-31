import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection, URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import BACKEND_DIR


def resolve_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername not in {"sqlite", "sqlite+pysqlite"} or url.query:
        raise ValueError("Only standard SQLite database URLs without query parameters are supported")
    if url.database and url.database != ":memory:":
        path = Path(url.database).expanduser()
        if not path.is_absolute():
            path = BACKEND_DIR / path
        url = url.set(database=str(path.resolve()))
    return url


def create_db_engine(database_url: str) -> Engine:
    url = resolve_database_url(database_url)
    file_backed = bool(url.database and url.database != ":memory:")
    if file_backed:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5.0},
        **({} if file_backed else {"poolclass": StaticPool}),
    )

    @event.listens_for(engine, "connect")
    def configure_connection(connection: sqlite3.Connection, _record: object) -> None:
        # Disable sqlite3's legacy implicit BEGIN; SQLAlchemy controls all transactions.
        connection.isolation_level = None
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            if file_backed:
                mode = cursor.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if mode.lower() != "wal":
                    raise sqlite3.OperationalError("SQLite WAL mode could not be enabled")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def begin_transaction(connection: Connection) -> None:
        # Future billing can opt in before beginning a transaction using
        # connection.execution_options(sqlite_begin_mode="IMMEDIATE").
        mode = connection.get_execution_options().get("sqlite_begin_mode", "DEFERRED")
        if mode not in {"DEFERRED", "IMMEDIATE"}:
            raise ValueError("Unsupported SQLite transaction mode")
        connection.exec_driver_sql(f"BEGIN {mode}")

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """One session per request; services explicitly commit via `with session.begin()`."""
    with request.app.state.session_factory() as session:
        yield session
    # Session.close rolls back unfinished transactions, including failed requests.

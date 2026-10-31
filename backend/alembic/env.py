from logging.config import fileConfig

from alembic import context

from app.core.config import Settings
from app.db.base import Base, UTCDateTime
from app.db.session import create_db_engine, resolve_database_url
from app import models  # noqa: F401 -- register model metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
# Programmatic callers (tests) can override the URL without touching process environment.
database_url = config.attributes.get("database_url") or Settings().database_url


def render_item(kind: str, item: object, _autogen_context: object) -> str | bool:
    # Migration files should use stable SQL types, not import application decorators.
    if kind == "type" and isinstance(item, UTCDateTime):
        return "sa.DateTime()"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=resolve_database_url(database_url), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"}, render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata,
                render_as_batch=True, compare_type=True, transactional_ddl=True,
                render_item=render_item,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

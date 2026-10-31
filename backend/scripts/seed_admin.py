import sys

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.clock import utc_now
from app.core.config import Settings
from app.core.errors import ServiceError
from app.db.session import create_db_engine, create_session_factory
from app.services.auth import seed_admin


def main() -> int:
    try:
        settings = Settings()
    except ValidationError:
        print("Invalid environment settings; check local configuration.", file=sys.stderr)
        return 1
    if not settings.admin_email or not settings.admin_password or not settings.admin_password.get_secret_value():
        print("ADMIN_EMAIL and ADMIN_PASSWORD are required.", file=sys.stderr)
        return 1
    engine = None
    try:
        engine = create_db_engine(settings.database_url)
        with create_session_factory(engine)() as session:
            user_id, created = seed_admin(session, email=settings.admin_email,
                                          password=settings.admin_password.get_secret_value(), clock=utc_now)
    except ValueError as error:
        print(f"Invalid admin credentials: {error}", file=sys.stderr)
        return 1
    except ServiceError as error:
        print(error.detail, file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Database unavailable or schema not migrated. Run alembic upgrade head.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print(f"Admin {'created' if created else 'already exists; credentials unchanged'} (ID {user_id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

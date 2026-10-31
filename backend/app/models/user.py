from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, Enum, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, utc_now


class UserRole(StrEnum):
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320, collation="NOCASE"), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[UserRole] = mapped_column(Enum(
        UserRole, values_callable=lambda roles: [role.value for role in roles],
        native_enum=False, create_constraint=True, validate_strings=True, name="user_role",
    ))
    is_active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="user_is_active"), default=True, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

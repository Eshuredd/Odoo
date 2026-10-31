from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Enum, text
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

from app.db.base import UTCDateTime, utc_now

MAX_INTEGER = 2**63 - 1
MAX_QUANTITY = 1_000_000
MAX_TAX_RATE = 10_000


def integer_check(column: str, minimum: int = 0, maximum: int = MAX_INTEGER) -> CheckConstraint:
    return CheckConstraint(
        f"typeof({column}) = 'integer' AND {column} BETWEEN {minimum} AND {maximum}",
        name=f"{column}_range",
    )


def nonempty(column: str) -> CheckConstraint:
    return CheckConstraint(f"length(trim({column})) > 0", name=f"{column}_nonempty")


def enum_type(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, values_callable=lambda values: [value.value for value in values],
                native_enum=False, create_constraint=True, validate_strings=True, name=name)


def boolean(name: str, default: bool = True) -> MappedColumn[bool]:
    return mapped_column(Boolean(create_constraint=True, name=name), default=default,
                         server_default=text("1" if default else "0"))


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP"),
    )

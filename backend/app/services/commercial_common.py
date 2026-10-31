from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.core.principal import Principal
from app.models import UserRole
from app.services.auth import check_principal

M = TypeVar("M")
S = TypeVar("S", bound=BaseModel)


@contextmanager
def write_scope(session: Session, actor: Principal, *roles: UserRole) -> Iterator[None]:
    try:
        with session.begin():
            session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
            current = check_principal(session, actor)
            if current.role not in roles or current.role != actor.role:
                raise ServiceError(403, "Insufficient permissions")
            yield
    except IntegrityError:
        raise ServiceError(409, "Record conflicts with existing data or constraints") from None


def get_record(session: Session, model: type[M], identifier: int) -> M:
    row = session.get(model, identifier)
    if row is None:
        raise ServiceError(404, "Record not found")
    return row


def page(session: Session, statement: Select, schema: type[S], limit: int, offset: int) -> dict:
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = session.scalars(statement.limit(limit).offset(offset)).all()
    return {"items": [schema.model_validate(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def apply_fields(row: object, values: dict) -> None:
    for key, value in values.items():
        setattr(row, key, value)


def validated_patch(row: object, patch: BaseModel, schema: type[S]) -> dict:
    values = {name: getattr(row, name) for name in schema.model_fields}
    values.update(patch.model_dump(exclude_unset=True))
    try:
        return schema.model_validate(values).model_dump()
    except ValidationError as error:
        raise ServiceError(422, error.errors()[0]["msg"]) from None

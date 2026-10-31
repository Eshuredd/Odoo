from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_clock, get_current_principal, require_roles
from app.core.clock import Clock
from app.core.principal import Principal
from app.db.session import get_db
from app.models import UserRole
from app.models.commercial_common import MAX_INTEGER

Database = Annotated[Session, Depends(get_db)]
Current = Annotated[Principal, Depends(get_current_principal)]
Admin = Annotated[Principal, Depends(require_roles(UserRole.ADMIN))]
Operator = Annotated[Principal, Depends(require_roles(UserRole.ADMIN, UserRole.STAFF))]
RequestClock = Annotated[Clock, Depends(get_clock)]
RecordId = Annotated[int, Path(ge=1, le=MAX_INTEGER)]
FilterId = Annotated[int | None, Query(ge=1, le=MAX_INTEGER)]


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=MAX_INTEGER)] = 0,
) -> Pagination:
    return Pagination(limit, offset)


Paging = Annotated[Pagination, Depends(pagination)]

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_clock, require_roles
from app.core.clock import Clock
from app.core.principal import Principal
from app.db.session import get_db
from app.models import UserRole
from app.schemas.auth import AccountCreate, PublicUser
from app.services.auth import create_account

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/staff", status_code=201, response_model=PublicUser)
def create_staff(
    body: AccountCreate, principal: Annotated[Principal, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)], clock: Annotated[Clock, Depends(get_clock)],
) -> PublicUser:
    return create_account(db, email=body.email, password=body.password.get_secret_value(),
                          role=UserRole.STAFF, clock=clock, actor=principal)

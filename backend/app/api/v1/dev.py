from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.principal import Principal
from app.db.session import get_db
from app.models import EmailOutbox, UserRole
from app.schemas.outbox import OutboxMessage, OutboxPage

router = APIRouter(prefix="/api/v1/dev", tags=["development"])


@router.get("/email-outbox", response_model=OutboxPage)
def email_outbox(
    principal: Annotated[Principal, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OutboxPage:
    with db.begin():
        total = db.scalar(select(func.count()).select_from(EmailOutbox)) or 0
        messages = db.scalars(select(EmailOutbox).order_by(
            EmailOutbox.created_at.desc(), EmailOutbox.id.desc(),
        ).limit(limit).offset(offset))
        return OutboxPage(items=[OutboxMessage.model_validate(message) for message in messages],
                          total=total, limit=limit, offset=offset)

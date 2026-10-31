from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_event(
    session: Session, *, actor_id: int, action: str, entity_id: int, now: datetime,
    detail: dict[str, Any] | None = None, entity: str = "user",
) -> None:
    session.add(AuditLog(
        actor_id=actor_id, action=action, entity=entity, entity_id=str(entity_id),
        timestamp=now, detail=detail or {},
    ))

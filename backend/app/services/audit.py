from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_event(
    session: Session, *, actor_id: int, action: str, entity_id: int, now: datetime,
    detail: dict[str, str] | None = None,
) -> None:
    session.add(AuditLog(
        actor_id=actor_id, action=action, entity="user", entity_id=str(entity_id),
        timestamp=now, detail=detail or {},
    ))

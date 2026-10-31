from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, utc_now


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_entity_id", "entity", "entity_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, server_default=text("CURRENT_TIMESTAMP"), index=True
    )
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))

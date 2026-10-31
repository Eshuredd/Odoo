from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OutboxMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipient_email: str
    subject: str
    body: str
    created_at: datetime


class OutboxPage(BaseModel):
    items: list[OutboxMessage]
    total: int
    limit: int
    offset: int

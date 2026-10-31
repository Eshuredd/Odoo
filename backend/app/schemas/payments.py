from datetime import date, datetime
from typing import Annotated
from pydantic import Field, StrictInt, StringConstraints
from app.models import PaymentMethod
from app.models.commercial_common import MAX_INTEGER
from app.schemas.commercial import Input, Output


class PaymentCreate(Input):
    amount_paise: Annotated[StrictInt, Field(ge=1, le=MAX_INTEGER)]
    method: PaymentMethod
    payment_date: date
    reference: Annotated[str, StringConstraints(max_length=200)] | None = None
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    note: Annotated[str, StringConstraints(max_length=2000)] | None = None


class PaymentOut(Output):
    id: int
    invoice_id: int
    amount_paise: int
    method: PaymentMethod
    payment_date: date
    reference: str | None
    note: str | None
    created_at: datetime

from datetime import date, datetime
from enum import StrEnum
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UTCDateTime, utc_now
from app.models.commercial_common import enum_type, integer_check, nonempty


class PaymentMethod(StrEnum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    UPI = "upi"
    CARD = "card"
    OTHER = "other"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (integer_check("amount_paise", 1), nonempty("idempotency_key"),
                     Index("ix_payments_payment_date_id", "payment_date", "id"), {"sqlite_autoincrement": True})
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    amount_paise: Mapped[int]
    method: Mapped[PaymentMethod] = mapped_column(enum_type(PaymentMethod, "payment_method"))
    payment_date: Mapped[date]
    reference: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    note: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

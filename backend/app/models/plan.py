from datetime import date
from enum import StrEnum

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.commercial_common import MAX_QUANTITY, Timestamps, boolean, enum_type, integer_check, nonempty


class BillingPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Plan(Timestamps, Base):
    __tablename__ = "plans"
    __table_args__ = (
        nonempty("name"), integer_check("price_paise"), integer_check("min_quantity", 1, MAX_QUANTITY),
        CheckConstraint("valid_to >= valid_from", name="valid_dates"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    price_paise: Mapped[int]
    billing_period: Mapped[BillingPeriod] = mapped_column(enum_type(BillingPeriod, "billing_period"))
    min_quantity: Mapped[int]
    valid_from: Mapped[date]
    valid_to: Mapped[date]
    auto_close: Mapped[bool] = boolean("plan_auto_close", False)
    closable: Mapped[bool] = boolean("plan_closable")
    pausable: Mapped[bool] = boolean("plan_pausable", False)
    renewable: Mapped[bool] = boolean("plan_renewable")
    active: Mapped[bool] = boolean("plan_active")

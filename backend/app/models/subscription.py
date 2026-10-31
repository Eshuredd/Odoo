from datetime import date
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Computed, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.commercial_common import MAX_QUANTITY, MAX_TAX_RATE, Timestamps, boolean, enum_type, integer_check
from app.models.plan import BillingPeriod


class SubscriptionStatus(StrEnum):
    DRAFT = "draft"
    QUOTATION = "quotation"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    CLOSED = "closed"


class Subscription(Timestamps, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        integer_check("payment_terms_days", 0, 3650), integer_check("recurring_base_price_paise"),
        CheckConstraint("expiry_date >= start_date", name="valid_dates"),
        CheckConstraint("quotation_expiry_date IS NULL OR quotation_expiry_date >= quotation_date", name="quotation_dates"),
        CheckConstraint("status = 'draft' OR (quotation_date IS NOT NULL AND quotation_expiry_date IS NOT NULL)", name="quotation_required"),
        CheckConstraint("status IN ('draft', 'quotation') OR (commercial_snapshot IS NOT NULL AND billing_period IS NOT NULL)", name="snapshot_required"),
        CheckConstraint("is_paused = 0 OR status = 'active'", name="pause_active_only"),
        CheckConstraint("status != 'active' OR next_invoice_date IS NOT NULL", name="active_billing_date"),
        CheckConstraint("status != 'closed' OR next_invoice_date IS NULL", name="closed_no_billing"),
        Index("ix_subscriptions_status_next_invoice_date", "status", "next_invoice_date"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), Computed("printf('SUB-%06d', id)", persisted=True), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(enum_type(SubscriptionStatus, "subscription_status"))
    start_date: Mapped[date]
    expiry_date: Mapped[date]
    quotation_date: Mapped[date | None]
    quotation_expiry_date: Mapped[date | None]
    payment_terms_days: Mapped[int]
    next_invoice_date: Mapped[date | None]
    is_paused: Mapped[bool] = boolean("subscription_paused", False)
    recurring_base_price_paise: Mapped[int]
    billing_period: Mapped[BillingPeriod | None] = mapped_column(enum_type(BillingPeriod, "subscription_billing_period"))
    commercial_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    lines: Mapped[list["SubscriptionLine"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="SubscriptionLine.id",
    )


class SubscriptionLine(Base):
    __tablename__ = "subscription_lines"
    __table_args__ = (
        integer_check("quantity", 1, MAX_QUANTITY), integer_check("unit_price_paise"),
        integer_check("tax_rate_basis_points", maximum=MAX_TAX_RATE), integer_check("amount_paise"),
        CheckConstraint("amount_paise = quantity * unit_price_paise", name="amount_matches_quantity_price"),
        ForeignKeyConstraint(["variant_id", "product_id"], ["product_variants.id", "product_variants.product_id"],
                             name="fk_subscription_lines_variant_product", ondelete="RESTRICT"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    variant_id: Mapped[int | None]
    quantity: Mapped[int]
    unit_price_paise: Mapped[int]
    tax_rate_basis_points: Mapped[int]
    amount_paise: Mapped[int]

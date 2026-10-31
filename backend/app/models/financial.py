"""Persisted financial records; migration 0004 also protects immutable snapshots."""
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Computed, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utc_now
from app.models.commercial_common import Timestamps, boolean, enum_type, integer_check, nonempty


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PAID = "paid"
    CANCELLED = "cancelled"


class DiscountType(StrEnum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class DiscountScope(StrEnum):
    SUBSCRIPTION = "subscription"
    PRODUCT = "product"


class Discount(Timestamps, Base):
    __tablename__ = "discounts"
    __table_args__ = (
        nonempty("name"), integer_check("minimum_purchase_paise"), integer_check("minimum_quantity", 1),
        integer_check("times_used"),
        CheckConstraint("valid_to >= valid_from", name="valid_dates"),
        CheckConstraint("(discount_type='fixed' AND typeof(value_paise)='integer' AND value_paise>=0 AND rate_basis_points IS NULL) OR "
                        "(discount_type='percentage' AND value_paise IS NULL AND typeof(rate_basis_points)='integer' AND rate_basis_points BETWEEN 0 AND 10000)", name="type_value"),
        CheckConstraint("(scope='subscription' AND product_id IS NULL) OR (scope='product' AND product_id IS NOT NULL)", name="scope_product"),
        CheckConstraint("usage_limit IS NULL OR (typeof(usage_limit)='integer' AND usage_limit>=0 AND times_used<=usage_limit)", name="usage_limit"),
        Index("ix_discounts_active_valid_from_valid_to", "active", "valid_from", "valid_to"),
        {"sqlite_autoincrement": True},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    discount_type: Mapped[DiscountType] = mapped_column(enum_type(DiscountType, "discount_type"))
    scope: Mapped[DiscountScope] = mapped_column(enum_type(DiscountScope, "discount_scope"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    value_paise: Mapped[int | None]
    rate_basis_points: Mapped[int | None]
    minimum_purchase_paise: Mapped[int] = mapped_column(default=0)
    minimum_quantity: Mapped[int] = mapped_column(default=1)
    valid_from: Mapped[date]
    valid_to: Mapped[date]
    usage_limit: Mapped[int | None]
    times_used: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = boolean("discount_active")


class Invoice(Timestamps, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("subscription_id", "period_start", "period_end", name="uq_invoices_subscription_period"),
        CheckConstraint("period_end > period_start", name="valid_period"),
        CheckConstraint("invoice_date = period_start AND due_date >= invoice_date", name="valid_dates"),
        *(integer_check(name) for name in ("subtotal_paise", "discount_total_paise", "tax_total_paise", "total_paise")),
        CheckConstraint("discount_total_paise <= subtotal_paise AND total_paise = subtotal_paise - discount_total_paise + tax_total_paise", name="totals"),
        Index("ix_invoices_customer_id_due_date", "customer_id", "due_date"),
        Index("ix_invoices_status_due_date", "status", "due_date"),
        {"sqlite_autoincrement": True},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), Computed("printf('INV-%06d', id)", persisted=True), unique=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_profiles.id", ondelete="RESTRICT"))
    period_start: Mapped[date]
    period_end: Mapped[date]
    invoice_date: Mapped[date]
    due_date: Mapped[date]
    status: Mapped[InvoiceStatus] = mapped_column(enum_type(InvoiceStatus, "invoice_status"), default=InvoiceStatus.DRAFT)
    subtotal_paise: Mapped[int]
    discount_total_paise: Mapped[int]
    tax_total_paise: Mapped[int]
    total_paise: Mapped[int]
    applied_discount_id: Mapped[int | None] = mapped_column(ForeignKey("discounts.id", ondelete="RESTRICT"))
    applied_discount_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    sealed: Mapped[bool] = boolean("invoice_sealed", False)
    lines: Mapped[list["InvoiceLine"]] = relationship(lazy="selectin", cascade="save-update, merge", order_by="InvoiceLine.id")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("line_type IN ('plan','product')", name="line_type"), nonempty("description"),
        CheckConstraint("(line_type='plan' AND product_id IS NULL AND variant_id IS NULL AND quantity=1 AND tax_rate_basis_points=0) OR (line_type='product' AND product_id IS NOT NULL)", name="line_reference"),
        integer_check("quantity", 1, 1000000), integer_check("tax_rate_basis_points", maximum=10000),
        *(integer_check(name) for name in ("unit_price_paise", "subtotal_paise", "discount_paise", "taxable_amount_paise", "tax_paise", "total_paise")),
        CheckConstraint("subtotal_paise = quantity * unit_price_paise AND discount_paise <= subtotal_paise AND taxable_amount_paise = subtotal_paise - discount_paise AND total_paise = taxable_amount_paise + tax_paise", name="totals"),
        {"sqlite_autoincrement": True},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    line_type: Mapped[str] = mapped_column(String(10))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(1000))
    quantity: Mapped[int]
    unit_price_paise: Mapped[int]
    subtotal_paise: Mapped[int]
    discount_paise: Mapped[int]
    taxable_amount_paise: Mapped[int]
    tax_rate_basis_points: Mapped[int]
    tax_paise: Mapped[int]
    total_paise: Mapped[int]


class DiscountRedemption(Base):
    __tablename__ = "discount_redemptions"
    __table_args__ = (UniqueConstraint("discount_id", "invoice_id"), {"sqlite_autoincrement": True})
    id: Mapped[int] = mapped_column(primary_key=True)
    discount_id: Mapped[int] = mapped_column(ForeignKey("discounts.id", ondelete="RESTRICT"), index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), unique=True)
    redeemed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

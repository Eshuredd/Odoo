from datetime import date, datetime
from typing import ClassVar, Annotated

from pydantic import Field, StrictBool, StrictInt, model_validator

from app.models import DiscountScope, DiscountType, InvoiceStatus
from app.models.commercial_common import MAX_INTEGER
from app.schemas.commercial import Input, Output, Patch, Name, Money, Rate, Identifier

Count = Annotated[StrictInt, Field(ge=0, le=MAX_INTEGER)]
MinimumQuantity = Annotated[StrictInt, Field(ge=1, le=MAX_INTEGER)]


class DiscountCreate(Input):
    name: Name
    discount_type: DiscountType
    scope: DiscountScope
    product_id: Identifier | None = None
    value_paise: Money | None = None
    rate_basis_points: Rate | None = None
    minimum_purchase_paise: Money = 0
    minimum_quantity: MinimumQuantity = 1
    valid_from: date
    valid_to: date
    usage_limit: Count | None = None
    active: StrictBool = True

    @model_validator(mode="after")
    def rule(self):
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot precede valid_from")
        if self.discount_type == DiscountType.FIXED:
            valid = self.value_paise is not None and self.rate_basis_points is None
        else:
            valid = self.value_paise is None and self.rate_basis_points is not None
        if not valid:
            raise ValueError("Fixed rules require only value_paise; percentage rules require only rate_basis_points")
        if (self.scope == DiscountScope.PRODUCT) != (self.product_id is not None):
            raise ValueError("Only product-scoped rules require product_id")
        return self


class DiscountPatch(Patch):
    nullable_fields: ClassVar[frozenset[str]] = frozenset({"product_id", "value_paise", "rate_basis_points", "usage_limit"})
    name: Name | None = None
    discount_type: DiscountType | None = None
    scope: DiscountScope | None = None
    product_id: Identifier | None = None
    value_paise: Money | None = None
    rate_basis_points: Rate | None = None
    minimum_purchase_paise: Money | None = None
    minimum_quantity: MinimumQuantity | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    usage_limit: Count | None = None
    active: StrictBool | None = None


class DiscountOut(DiscountCreate, Output):
    id: int
    times_used: int
    created_at: datetime
    updated_at: datetime



class LineOut(Output):
    line_type: str
    product_id: int | None
    variant_id: int | None
    description: str
    quantity: int
    unit_price_paise: int
    subtotal_paise: int
    discount_paise: int
    taxable_amount_paise: int
    tax_rate_basis_points: int
    tax_paise: int
    total_paise: int


class InvoiceLineOut(LineOut):
    id: int
    invoice_id: int


class InvoiceOut(Output):
    id: int
    number: str
    subscription_id: int
    customer_id: int
    period_start: date
    period_end: date
    invoice_date: date
    due_date: date
    status: InvoiceStatus
    subtotal_paise: int
    discount_total_paise: int
    tax_total_paise: int
    total_paise: int
    applied_discount_id: int | None
    applied_discount_snapshot: dict | None
    lines: list[InvoiceLineOut]
    created_at: datetime
    updated_at: datetime
    paid_amount_paise: int
    remaining_balance_paise: int
    payment_progress: str
    is_overdue: bool | None = None
    days_overdue: int | None = None


class BillingRequest(Input):
    as_of: date


class AgingBucket(Output):
    invoice_count: int
    amount_paise: int


class MonthlyCollection(Output):
    month: str
    amount_paise: int


class ReportSummary(Output):
    as_of: date
    from_date: date
    to_date: date
    active_subscription_count: int
    paused_subscription_count: int
    revenue_collected_paise: int
    outstanding_balance_paise: int
    overdue_invoice_count: int
    overdue_amount_paise: int
    aging_buckets: dict[str, AgingBucket]
    invoice_count_by_status: dict[str, int]
    monthly_collections: list[MonthlyCollection]


class BillingInvoice(Output):
    subscription_id: int
    subscription_number: str
    customer_id: int
    period_start: date
    period_end: date
    invoice_date: date
    due_date: date
    invoice_id: int | None = None
    invoice_number: str | None = None
    disposition: str
    catch_up: bool
    subtotal_paise: int
    discount_total_paise: int
    tax_total_paise: int
    total_paise: int
    applied_discount_id: int | None
    applied_discount_snapshot: dict | None
    lines: list[LineOut]


class BillingIssue(Output):
    subscription_id: int
    subscription_number: str
    reason: str


class BillingReport(Output):
    as_of: date
    dry_run: bool
    eligible_subscription_count: int
    generated_or_proposed_invoice_count: int
    projected_or_actual_total_paise: int
    skipped_count: int
    failed_count: int
    invoices: list[BillingInvoice]
    existing_invoices: list[BillingInvoice]
    skipped: list[BillingIssue]
    errors: list[BillingIssue]
    auto_closed_subscription_ids: list[int]

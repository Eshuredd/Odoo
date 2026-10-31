from datetime import date, datetime
from typing import Annotated, Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StringConstraints, model_validator

from app.models import BillingPeriod, ProductType, SubscriptionStatus
from app.models.commercial_common import MAX_INTEGER, MAX_QUANTITY, MAX_TAX_RATE
from app.schemas.auth import AccountCreate

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[StrictInt, Field(ge=0, le=MAX_INTEGER)]
Quantity = Annotated[StrictInt, Field(ge=1, le=MAX_QUANTITY)]
Identifier = Annotated[StrictInt, Field(ge=1, le=MAX_INTEGER)]
Rate = Annotated[StrictInt, Field(ge=0, le=MAX_TAX_RATE)]
Days = Annotated[StrictInt, Field(ge=0, le=3650)]
PositiveDays = Annotated[StrictInt, Field(ge=1, le=3650)]
ShortText = Annotated[str, StringConstraints(max_length=10000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Patch(Input):
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_nulls(self):
        for name in self.model_fields_set - self.nullable_fields:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class CustomerCreate(AccountCreate):
    company_name: Name
    contact_name: Name
    phone: Annotated[str, StringConstraints(max_length=50)] | None = None
    notes: ShortText | None = None


class CustomerPatch(Patch):
    nullable_fields = frozenset({"phone", "notes"})
    company_name: Name | None = None
    contact_name: Name | None = None
    phone: Annotated[str, StringConstraints(max_length=50)] | None = None
    notes: ShortText | None = None


class CustomerOut(Output):
    id: int
    user_id: int
    company_name: str
    contact_name: str
    phone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class TaxCreate(Input):
    name: Name
    rate_basis_points: Rate
    active: StrictBool = True


class TaxPatch(Patch):
    name: Name | None = None
    rate_basis_points: Rate | None = None
    active: StrictBool | None = None


class TaxOut(TaxCreate, Output):
    id: int
    created_at: datetime


class ProductCreate(Input):
    name: Name
    product_type: ProductType
    sales_price_paise: Money
    cost_price_paise: Money = 0
    notes: ShortText | None = None
    tax_id: Identifier | None = None
    active: StrictBool = True


class ProductPatch(Patch):
    nullable_fields = frozenset({"notes", "tax_id"})
    name: Name | None = None
    product_type: ProductType | None = None
    sales_price_paise: Money | None = None
    cost_price_paise: Money | None = None
    notes: ShortText | None = None
    tax_id: Identifier | None = None
    active: StrictBool | None = None


class ProductOut(ProductCreate, Output):
    id: int
    created_at: datetime
    updated_at: datetime


class VariantCreate(Input):
    attribute: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    extra_price_paise: Money = 0
    active: StrictBool = True


class VariantPatch(Patch):
    attribute: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    extra_price_paise: Money | None = None
    active: StrictBool | None = None


class VariantOut(VariantCreate, Output):
    id: int
    product_id: int


class PlanCreate(Input):
    name: Name
    price_paise: Money
    billing_period: BillingPeriod
    min_quantity: Quantity = 1
    valid_from: date
    valid_to: date
    auto_close: StrictBool = False
    closable: StrictBool = True
    pausable: StrictBool = False
    renewable: StrictBool = True
    active: StrictBool = True

    @model_validator(mode="after")
    def dates(self):
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot precede valid_from")
        return self


class PlanPatch(Patch):
    name: Name | None = None
    price_paise: Money | None = None
    billing_period: BillingPeriod | None = None
    min_quantity: Quantity | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    auto_close: StrictBool | None = None
    closable: StrictBool | None = None
    pausable: StrictBool | None = None
    renewable: StrictBool | None = None
    active: StrictBool | None = None


class PlanOut(PlanCreate, Output):
    id: int
    created_at: datetime
    updated_at: datetime


class LineInput(Input):
    product_id: Identifier
    variant_id: Identifier | None = None
    quantity: Quantity


class LinePatch(Patch):
    nullable_fields = frozenset({"variant_id"})
    product_id: Identifier | None = None
    variant_id: Identifier | None = None
    quantity: Quantity | None = None


class TemplateLineOut(LineInput, Output):
    id: int
    template_id: int


class TemplateCreate(Input):
    name: Name
    validity_days: PositiveDays = 30
    plan_id: Identifier
    active: StrictBool = True
    lines: list[LineInput] = Field(default_factory=list, max_length=100)


class TemplatePatch(Patch):
    name: Name | None = None
    validity_days: PositiveDays | None = None
    plan_id: Identifier | None = None
    active: StrictBool | None = None
    lines: list[LineInput] | None = Field(default=None, max_length=100)


class TemplateOut(Output):
    id: int
    name: str
    validity_days: int
    plan_id: int
    active: bool
    lines: list[TemplateLineOut]


class SubscriptionDates(Input):
    customer_id: Identifier
    start_date: date
    expiry_date: date
    payment_terms_days: Days = 0
    as_of: date

    @model_validator(mode="after")
    def dates(self):
        if self.expiry_date < self.start_date:
            raise ValueError("expiry_date cannot precede start_date")
        return self


class SubscriptionCreate(SubscriptionDates):
    plan_id: Identifier
    lines: list[LineInput] = Field(min_length=1, max_length=100)


class FromTemplate(SubscriptionDates):
    template_id: Identifier


class Action(Input):
    as_of: date


class QuotationAction(Action):
    validity_days: PositiveDays = 30


class RenewAction(Action):
    new_expiry_date: date


class SubscriptionLineOut(LineInput, Output):
    id: int
    subscription_id: int
    unit_price_paise: int
    tax_rate_basis_points: int
    amount_paise: int


class SubscriptionOut(Output):
    id: int
    number: str
    customer_id: int
    plan_id: int
    status: SubscriptionStatus
    start_date: date
    expiry_date: date
    quotation_date: date | None
    quotation_expiry_date: date | None
    payment_terms_days: int
    next_invoice_date: date | None
    is_paused: bool
    recurring_base_price_paise: int
    billing_period: BillingPeriod | None
    commercial_snapshot: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    lines: list[SubscriptionLineOut]

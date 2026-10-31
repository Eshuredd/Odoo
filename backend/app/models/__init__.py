"""Import all models here so Alembic sees the complete metadata."""

from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.models.password_reset import PasswordResetToken
from app.models.email_outbox import EmailOutbox
from app.models.customer import CustomerProfile
from app.models.catalog import Product, ProductType, ProductVariant, Tax
from app.models.plan import BillingPeriod, Plan
from app.models.quotation import QuotationTemplate, QuotationTemplateLine
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.financial import Invoice, InvoiceLine, InvoiceStatus, Discount, DiscountType, DiscountScope, DiscountRedemption

__all__ = [
    "AuditLog", "User", "UserRole", "PasswordResetToken", "EmailOutbox", "CustomerProfile",
    "Product", "ProductType", "ProductVariant", "Tax", "BillingPeriod", "Plan",
    "QuotationTemplate", "QuotationTemplateLine", "Subscription", "SubscriptionLine", "SubscriptionStatus",
    "Invoice", "InvoiceLine", "InvoiceStatus", "Discount", "DiscountType", "DiscountScope", "DiscountRedemption",
]

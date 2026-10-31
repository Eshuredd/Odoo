from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, utc_now
from app.models.commercial_common import (
    MAX_TAX_RATE, Timestamps, boolean, enum_type, integer_check, nonempty,
)


class ProductType(StrEnum):
    GOODS = "goods"
    SERVICE = "service"


class Tax(Base):
    __tablename__ = "taxes"
    __table_args__ = (nonempty("name"), integer_check("rate_basis_points", maximum=MAX_TAX_RATE),
                      {"sqlite_autoincrement": True})

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    rate_basis_points: Mapped[int]
    active: Mapped[bool] = boolean("tax_active")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, server_default=text("CURRENT_TIMESTAMP"),
    )


class Product(Timestamps, Base):
    __tablename__ = "products"
    __table_args__ = (
        nonempty("name"), integer_check("sales_price_paise"), integer_check("cost_price_paise"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    product_type: Mapped[ProductType] = mapped_column(enum_type(ProductType, "product_type"))
    sales_price_paise: Mapped[int]
    cost_price_paise: Mapped[int]
    notes: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"), index=True)
    active: Mapped[bool] = boolean("product_active")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        nonempty("attribute"), nonempty("value"), integer_check("extra_price_paise"),
        UniqueConstraint("id", "product_id", name="uq_product_variants_id_product_id"),
        UniqueConstraint("product_id", "attribute", "value", name="uq_product_variants_product_attribute_value"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    attribute: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(100))
    extra_price_paise: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    active: Mapped[bool] = boolean("variant_active")

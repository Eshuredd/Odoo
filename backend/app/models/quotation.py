from sqlalchemy import ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.commercial_common import MAX_QUANTITY, boolean, integer_check, nonempty


class QuotationTemplate(Base):
    __tablename__ = "quotation_templates"
    __table_args__ = (nonempty("name"), integer_check("validity_days", 1, 3650),
                      {"sqlite_autoincrement": True})

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    validity_days: Mapped[int]
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    active: Mapped[bool] = boolean("template_active")
    lines: Mapped[list["QuotationTemplateLine"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="QuotationTemplateLine.id",
    )


class QuotationTemplateLine(Base):
    __tablename__ = "quotation_template_lines"
    __table_args__ = (
        integer_check("quantity", 1, MAX_QUANTITY),
        ForeignKeyConstraint(["variant_id", "product_id"], ["product_variants.id", "product_variants.product_id"],
                             name="fk_template_lines_variant_product", ondelete="RESTRICT"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("quotation_templates.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    variant_id: Mapped[int | None]
    quantity: Mapped[int]

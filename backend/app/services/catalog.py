from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import ServiceError
from app.core.principal import Principal
from app.models import Plan, Product, ProductVariant, QuotationTemplate, QuotationTemplateLine, Tax, UserRole
from app.schemas import commercial as schemas
from app.services.audit import record_event
from app.services.commercial_common import apply_fields, get_record, validated_patch, write_scope

M = TypeVar("M")


def reference(session: Session, model: type[M], identifier: int, label: str) -> M:
    row = session.get(model, identifier)
    if row is None:
        raise ServiceError(422, f"{label} does not exist")
    return row


def selected_product(session: Session, product_id: int, variant_id: int | None) -> tuple[Product, ProductVariant | None, Tax | None]:
    product = reference(session, Product, product_id, "Product")
    if not product.active:
        raise ServiceError(422, "Product is inactive")
    variant = None
    if variant_id is not None:
        variant = reference(session, ProductVariant, variant_id, "Variant")
        if variant.product_id != product.id:
            raise ServiceError(422, "Variant does not belong to the selected product")
        if not variant.active:
            raise ServiceError(422, "Variant is inactive")
    tax = reference(session, Tax, product.tax_id, "Tax") if product.tax_id is not None else None
    if tax is not None and not tax.active:
        raise ServiceError(422, "Product tax is inactive")
    return product, variant, tax


def save_tax(session: Session, body: schemas.TaxCreate | schemas.TaxPatch, actor: Principal, clock: Clock, identifier: int | None = None) -> schemas.TaxOut:
    with write_scope(session, actor, UserRole.ADMIN):
        row = get_record(session, Tax, identifier) if identifier else Tax(created_at=clock())
        values = validated_patch(row, body, schemas.TaxCreate) if identifier else body.model_dump()
        apply_fields(row, values)
        session.add(row)
        session.flush()
        record_event(session, actor_id=actor.id, action="tax.updated" if identifier else "tax.created",
                     entity="tax", entity_id=row.id, now=clock())
        return schemas.TaxOut.model_validate(row)


def save_product(session: Session, body: schemas.ProductCreate | schemas.ProductPatch, actor: Principal, clock: Clock, identifier: int | None = None) -> schemas.ProductOut:
    with write_scope(session, actor, UserRole.ADMIN):
        row = get_record(session, Product, identifier) if identifier else Product(created_at=clock())
        values = validated_patch(row, body, schemas.ProductCreate) if identifier else body.model_dump()
        if values["tax_id"] is not None:
            reference(session, Tax, values["tax_id"], "Tax")
        apply_fields(row, values)
        row.updated_at = clock()
        session.add(row)
        session.flush()
        record_event(session, actor_id=actor.id, action="product.updated" if identifier else "product.created",
                     entity="product", entity_id=row.id, now=clock())
        return schemas.ProductOut.model_validate(row)


def save_variant(session: Session, product_id: int, body: schemas.VariantCreate | schemas.VariantPatch, actor: Principal, clock: Clock, identifier: int | None = None) -> schemas.VariantOut:
    with write_scope(session, actor, UserRole.ADMIN):
        get_record(session, Product, product_id)
        if identifier:
            row = session.scalar(select(ProductVariant).where(ProductVariant.id == identifier,
                                                              ProductVariant.product_id == product_id))
            if row is None:
                raise ServiceError(404, "Record not found")
            values = validated_patch(row, body, schemas.VariantCreate)
        else:
            row = ProductVariant(product_id=product_id)
            values = body.model_dump()
        apply_fields(row, values)
        session.add(row)
        session.flush()
        record_event(session, actor_id=actor.id, action="variant.updated" if identifier else "variant.created",
                     entity="product_variant", entity_id=row.id, now=clock())
        return schemas.VariantOut.model_validate(row)


def save_plan(session: Session, body: schemas.PlanCreate | schemas.PlanPatch, actor: Principal, clock: Clock, identifier: int | None = None) -> schemas.PlanOut:
    with write_scope(session, actor, UserRole.ADMIN):
        row = get_record(session, Plan, identifier) if identifier else Plan(created_at=clock())
        values = validated_patch(row, body, schemas.PlanCreate) if identifier else body.model_dump()
        apply_fields(row, values)
        row.updated_at = clock()
        session.add(row)
        session.flush()
        record_event(session, actor_id=actor.id, action="plan.updated" if identifier else "plan.created",
                     entity="plan", entity_id=row.id, now=clock())
        return schemas.PlanOut.model_validate(row)


def save_template(session: Session, body: schemas.TemplateCreate | schemas.TemplatePatch, actor: Principal, clock: Clock, identifier: int | None = None) -> schemas.TemplateOut:
    with write_scope(session, actor, UserRole.ADMIN):
        row = get_record(session, QuotationTemplate, identifier) if identifier else QuotationTemplate()
        values = body.model_dump(exclude_unset=True) if identifier else body.model_dump()
        if "plan_id" in values:
            reference(session, Plan, values["plan_id"], "Plan")
        lines = values.pop("lines", None)
        if lines is not None:
            for line in lines:
                selected_product(session, line["product_id"], line.get("variant_id"))
            row.lines = [QuotationTemplateLine(**line) for line in lines]
        apply_fields(row, values)
        session.add(row)
        session.flush()
        record_event(session, actor_id=actor.id, action="template.updated" if identifier else "template.created",
                     entity="quotation_template", entity_id=row.id, now=clock())
        return schemas.TemplateOut.model_validate(row)


def save_template_line(
    session: Session, template_id: int, body: schemas.LineInput | schemas.LinePatch,
    actor: Principal, clock: Clock, identifier: int | None = None,
) -> schemas.TemplateLineOut:
    with write_scope(session, actor, UserRole.ADMIN):
        template = get_record(session, QuotationTemplate, template_id)
        if identifier:
            row = next((line for line in template.lines if line.id == identifier), None)
            if row is None:
                raise ServiceError(404, "Record not found")
            values = validated_patch(row, body, schemas.LineInput)
        else:
            if len(template.lines) >= 100:
                raise ServiceError(422, "Templates support at most 100 lines")
            row = QuotationTemplateLine(template_id=template_id)
            values = body.model_dump()
        selected_product(session, values["product_id"], values["variant_id"])
        apply_fields(row, values)
        session.add(row)
        session.flush()
        record_event(session, actor_id=actor.id, action="template.line_updated" if identifier else "template.line_added",
                     entity="quotation_template", entity_id=template_id, now=clock())
        return schemas.TemplateLineOut.model_validate(row)


def delete_template_line(session: Session, template_id: int, identifier: int, actor: Principal, clock: Clock) -> None:
    with write_scope(session, actor, UserRole.ADMIN):
        get_record(session, QuotationTemplate, template_id)
        row = session.scalar(select(QuotationTemplateLine).where(
            QuotationTemplateLine.id == identifier, QuotationTemplateLine.template_id == template_id,
        ))
        if row is None:
            raise ServiceError(404, "Record not found")
        session.delete(row)
        record_event(session, actor_id=actor.id, action="template.line_removed", entity="quotation_template",
                     entity_id=template_id, now=clock())

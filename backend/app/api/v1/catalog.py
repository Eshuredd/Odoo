from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.api.commercial_dependencies import Admin, Database, Operator, Paging, RequestClock, RecordId, FilterId
from app.core.errors import ServiceError
from app.models import Plan, Product, ProductType, ProductVariant, QuotationTemplate, QuotationTemplateLine, Tax
from app.schemas import commercial as s
from app.services import catalog
from app.services.commercial_common import get_record, page

router = APIRouter(tags=["catalog"])
Search = Annotated[str | None, Query(max_length=200)]


def search_query(model: type, search: str | None, active: bool | None):
    query = select(model).order_by(model.id)
    if search:
        query = query.where(model.name.contains(search, autoescape=True))
    if active is not None:
        query = query.where(model.active == active)
    return query


@router.get("/taxes", response_model=s.Page[s.TaxOut])
def list_taxes(actor: Operator, db: Database, paging: Paging, search: Search = None, active: bool | None = None) -> dict:
    return page(db, search_query(Tax, search, active), s.TaxOut, paging.limit, paging.offset)


@router.get("/taxes/{identifier}", response_model=s.TaxOut)
def get_tax(identifier: RecordId, actor: Operator, db: Database) -> s.TaxOut:
    return s.TaxOut.model_validate(get_record(db, Tax, identifier))


@router.post("/taxes", status_code=201, response_model=s.TaxOut)
def create_tax(body: s.TaxCreate, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_tax(db, body, actor, clock)


@router.patch("/taxes/{identifier}", response_model=s.TaxOut)
def update_tax(identifier: RecordId, body: s.TaxPatch, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_tax(db, body, actor, clock, identifier)


@router.get("/products", response_model=s.Page[s.ProductOut])
def list_products(
    actor: Operator, db: Database, paging: Paging, search: Search = None, active: bool | None = None,
    tax_id: FilterId = None, product_type: ProductType | None = None,
) -> dict:
    query = search_query(Product, search, active)
    if tax_id is not None:
        query = query.where(Product.tax_id == tax_id)
    if product_type is not None:
        query = query.where(Product.product_type == product_type)
    return page(db, query, s.ProductOut, paging.limit, paging.offset)


@router.get("/products/{identifier}", response_model=s.ProductOut)
def get_product(identifier: RecordId, actor: Operator, db: Database) -> s.ProductOut:
    return s.ProductOut.model_validate(get_record(db, Product, identifier))


@router.post("/products", status_code=201, response_model=s.ProductOut)
def create_product(body: s.ProductCreate, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_product(db, body, actor, clock)


@router.patch("/products/{identifier}", response_model=s.ProductOut)
def update_product(identifier: RecordId, body: s.ProductPatch, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_product(db, body, actor, clock, identifier)


@router.get("/products/{product_id}/variants", response_model=s.Page[s.VariantOut])
def list_variants(product_id: RecordId, actor: Operator, db: Database, paging: Paging, active: bool | None = None) -> dict:
    get_record(db, Product, product_id)
    query = select(ProductVariant).where(ProductVariant.product_id == product_id).order_by(ProductVariant.id)
    if active is not None:
        query = query.where(ProductVariant.active == active)
    return page(db, query, s.VariantOut, paging.limit, paging.offset)


@router.get("/products/{product_id}/variants/{identifier}", response_model=s.VariantOut)
def get_variant(product_id: RecordId, identifier: RecordId, actor: Operator, db: Database) -> s.VariantOut:
    row = db.scalar(select(ProductVariant).where(ProductVariant.id == identifier, ProductVariant.product_id == product_id))
    if row is None:
        raise ServiceError(404, "Record not found")
    return s.VariantOut.model_validate(row)


@router.post("/products/{product_id}/variants", status_code=201, response_model=s.VariantOut)
def create_variant(product_id: RecordId, body: s.VariantCreate, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_variant(db, product_id, body, actor, clock)


@router.patch("/products/{product_id}/variants/{identifier}", response_model=s.VariantOut)
def update_variant(product_id: RecordId, identifier: RecordId, body: s.VariantPatch, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_variant(db, product_id, body, actor, clock, identifier)


@router.get("/plans", response_model=s.Page[s.PlanOut])
def list_plans(
    actor: Operator, db: Database, paging: Paging, search: Search = None, active: bool | None = None,
    as_of: date | None = None,
) -> dict:
    query = search_query(Plan, search, active)
    if as_of is not None:
        query = query.where(Plan.active.is_(True), Plan.valid_from <= as_of, Plan.valid_to >= as_of)
    return page(db, query, s.PlanOut, paging.limit, paging.offset)


@router.get("/plans/{identifier}", response_model=s.PlanOut)
def get_plan(identifier: RecordId, actor: Operator, db: Database) -> s.PlanOut:
    return s.PlanOut.model_validate(get_record(db, Plan, identifier))


@router.post("/plans", status_code=201, response_model=s.PlanOut)
def create_plan(body: s.PlanCreate, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_plan(db, body, actor, clock)


@router.patch("/plans/{identifier}", response_model=s.PlanOut)
def update_plan(identifier: RecordId, body: s.PlanPatch, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_plan(db, body, actor, clock, identifier)


@router.get("/quotation-templates", response_model=s.Page[s.TemplateOut])
def list_templates(
    actor: Operator, db: Database, paging: Paging, search: Search = None, active: bool | None = None,
    plan_id: FilterId = None,
) -> dict:
    query = search_query(QuotationTemplate, search, active)
    if plan_id is not None:
        query = query.where(QuotationTemplate.plan_id == plan_id)
    return page(db, query, s.TemplateOut, paging.limit, paging.offset)


@router.get("/quotation-templates/{identifier}", response_model=s.TemplateOut)
def get_template(identifier: RecordId, actor: Operator, db: Database) -> s.TemplateOut:
    return s.TemplateOut.model_validate(get_record(db, QuotationTemplate, identifier))


@router.post("/quotation-templates", status_code=201, response_model=s.TemplateOut)
def create_template(body: s.TemplateCreate, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_template(db, body, actor, clock)


@router.patch("/quotation-templates/{identifier}", response_model=s.TemplateOut)
def update_template(identifier: RecordId, body: s.TemplatePatch, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_template(db, body, actor, clock, identifier)


@router.get("/quotation-templates/{template_id}/lines", response_model=s.Page[s.TemplateLineOut])
def list_template_lines(template_id: RecordId, actor: Operator, db: Database, paging: Paging) -> dict:
    get_record(db, QuotationTemplate, template_id)
    query = select(QuotationTemplateLine).where(QuotationTemplateLine.template_id == template_id).order_by(QuotationTemplateLine.id)
    return page(db, query, s.TemplateLineOut, paging.limit, paging.offset)


@router.post("/quotation-templates/{template_id}/lines", status_code=201, response_model=s.TemplateLineOut)
def create_template_line(template_id: RecordId, body: s.LineInput, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_template_line(db, template_id, body, actor, clock)


@router.patch("/quotation-templates/{template_id}/lines/{identifier}", response_model=s.TemplateLineOut)
def update_template_line(template_id: RecordId, identifier: RecordId, body: s.LinePatch, actor: Admin, db: Database, clock: RequestClock):
    return catalog.save_template_line(db, template_id, body, actor, clock, identifier)


@router.delete("/quotation-templates/{template_id}/lines/{identifier}", status_code=204)
def delete_template_line(template_id: RecordId, identifier: RecordId, actor: Admin, db: Database, clock: RequestClock) -> Response:
    catalog.delete_template_line(db, template_id, identifier, actor, clock)
    return Response(status_code=204)

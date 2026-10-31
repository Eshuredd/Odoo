"""One atomic write transaction per subscription; preview is a read-only snapshot."""
from dataclasses import replace
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.errors import ServiceError
from app.core.principal import Principal
from app.db.base import utc_now
from app.models import Discount, DiscountRedemption, Invoice, InvoiceLine, Subscription, SubscriptionStatus, UserRole
from app.schemas.financial import BillingReport, InvoiceOut
from app.services.audit import record_event
from app.services.auth import check_principal
from app.services.commercial_common import write_scope
from app.services.periods import due_periods
from app.services.pricing import Charge, Rule, price_invoice


def rules_for(session: Session) -> list[Rule]:
    return [Rule(**{key: getattr(row, key) for key in Rule.__dataclass_fields__})
            for row in session.scalars(select(Discount).where(Discount.active.is_(True)).order_by(Discount.id))]


def charges_for(row: Subscription) -> list[Charge]:
    snapshot = row.commercial_snapshot
    if not snapshot or len(snapshot["lines"]) != len(row.lines):
        raise ValueError("Accepted commercial snapshot is missing or inconsistent")
    charges = [Charge("plan", snapshot["plan"]["name"], 1, row.recurring_base_price_paise)]
    for line, label in zip(row.lines, snapshot["lines"]):
        description = label["product_name"]
        if label.get("variant_id") is not None:
            description += f" · {label['attribute']}: {label['value']}"
        charges.append(Charge("product", description, line.quantity, line.unit_price_paise,
                              line.tax_rate_basis_points, line.product_id, line.variant_id))
    return charges


def auto_close_due(row: Subscription, as_of: date) -> bool:
    return bool(row.commercial_snapshot and row.commercial_snapshot["plan"]["auto_close"] and
                as_of > row.expiry_date and row.next_invoice_date > row.expiry_date)


def selected_ids(session: Session, as_of: date) -> list[int]:
    # The due scan uses the existing (status, next_invoice_date) index.
    due = select(Subscription.id).where(Subscription.status == SubscriptionStatus.ACTIVE,
                                         Subscription.next_invoice_date <= as_of)
    # Also close expired contracts when the next boundary is still in the future.
    closure = select(Subscription.id).where(Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.expiry_date < as_of, Subscription.next_invoice_date > Subscription.expiry_date,
        Subscription.commercial_snapshot["plan"]["auto_close"].as_boolean().is_(True))
    return sorted(set(session.scalars(due)) | set(session.scalars(closure)))


def process_subscription(session: Session, row: Subscription, as_of: date, dry_run: bool,
                         rules: list[Rule], actor: Principal, clock: Clock) -> tuple[dict, list[Rule]]:
    result = {"invoices": [], "existing_invoices": [], "skipped": [], "auto_closed_subscription_ids": []}
    issue = {"subscription_id": row.id, "subscription_number": row.number}
    if row.status != SubscriptionStatus.ACTIVE or row.next_invoice_date is None:
        result["skipped"].append({**issue, "reason": "Subscription is no longer active"})
        return result, rules
    if row.is_paused:
        result["skipped"].append({**issue, "reason": "Paused: billing is deferred; scheduled periods remain due after resume"})
        return result, rules
    charges = charges_for(row)
    next_date = row.next_invoice_date
    for start, end in due_periods(row.start_date, row.billing_period, next_date, row.expiry_date, as_of):
        common = {**issue, "customer_id": row.customer_id, "period_start": start, "period_end": end,
                  "catch_up": end <= as_of}
        existing = session.scalar(select(Invoice).where(Invoice.subscription_id == row.id,
                                  Invoice.period_start == start, Invoice.period_end == end))
        if existing:
            value = InvoiceOut.model_validate(existing).model_dump()
            result["existing_invoices"].append({**common, **{key: value[key] for key in (
                "invoice_date", "due_date", "subtotal_paise", "discount_total_paise", "tax_total_paise", "total_paise",
                "applied_discount_id", "applied_discount_snapshot", "lines")},
                "invoice_id": existing.id, "invoice_number": existing.number, "disposition": "existing"})
        else:
            calculated = price_invoice(charges, rules, start)
            invoice_date, due_date = start, start + timedelta(days=row.payment_terms_days)
            invoice = None
            if not dry_run:
                invoice = Invoice(subscription_id=row.id, customer_id=row.customer_id, period_start=start, period_end=end,
                    invoice_date=invoice_date, due_date=due_date, created_at=clock(), updated_at=clock(),
                    **{key: value for key, value in calculated.items() if key != "lines"})
                session.add(invoice)
                session.flush()
                session.add_all([InvoiceLine(invoice_id=invoice.id, **line) for line in calculated["lines"]])
                session.flush()
                invoice.sealed = True
                if calculated["applied_discount_id"] is not None:
                    # Migration trigger atomically increments and checks the global usage limit.
                    session.add(DiscountRedemption(discount_id=calculated["applied_discount_id"], invoice_id=invoice.id,
                                                   redeemed_at=clock()))
                    record_event(session, actor_id=actor.id, action="discount.redeemed", entity="invoice",
                        entity_id=invoice.id, now=clock(), detail={"discount_id": calculated["applied_discount_id"]})
                record_event(session, actor_id=actor.id, action="invoice.generated", entity="invoice", entity_id=invoice.id,
                    now=clock(), detail={"subscription_id": row.id, "period_start": start.isoformat(),
                                         "period_end": end.isoformat(), "as_of": as_of.isoformat()})
                session.flush()
            result["invoices"].append({**common, **calculated, "invoice_date": invoice_date, "due_date": due_date,
                "invoice_id": invoice.id if invoice else None, "invoice_number": invoice.number if invoice else None,
                "disposition": "proposed" if dry_run else "generated"})
            rules = [replace(rule, times_used=rule.times_used + 1) if rule.id == calculated["applied_discount_id"] else rule
                     for rule in rules]
        next_date = end
    would_close = bool(row.commercial_snapshot["plan"]["auto_close"] and as_of > row.expiry_date and next_date > row.expiry_date)
    if would_close:
        result["auto_closed_subscription_ids"].append(row.id)
    if not result["invoices"] and not result["existing_invoices"] and not would_close:
        result["skipped"].append({**issue, "reason": "No eligible unbilled period on or before expiry and as_of"})
    if not dry_run and (next_date != row.next_invoice_date or would_close):
        row.next_invoice_date = next_date
        if would_close:
            row.status, row.next_invoice_date = SubscriptionStatus.CLOSED, None
            record_event(session, actor_id=actor.id, action="subscription.auto_closed", entity="subscription", entity_id=row.id,
                         now=clock(), detail={"as_of": as_of.isoformat(), "expiry_date": row.expiry_date.isoformat()})
        row.updated_at = clock()
        session.flush()
    return result, rules


def run_billing(session_factory: sessionmaker[Session], as_of: date, dry_run: bool, actor: Principal,
                clock: Clock = utc_now) -> BillingReport:
    report = {"as_of": as_of, "dry_run": dry_run, "eligible_subscription_count": 0, "invoices": [],
              "existing_invoices": [], "skipped": [], "errors": [], "auto_closed_subscription_ids": []}

    def merge(result: dict) -> None:
        for key, values in result.items():
            report[key].extend(values)

    def failure(identifier: int, number: str, error: Exception) -> None:
        # Never expose SQL, binds, or stack traces in an operational report.
        reason = str(error) if isinstance(error, (ValueError, OverflowError)) else "Subscription billing failed; all its changes were rolled back"
        report["errors"].append({"subscription_id": identifier, "subscription_number": number, "reason": reason})

    with session_factory() as read, read.begin():
        current = check_principal(read, actor)
        if current.role not in {UserRole.ADMIN, UserRole.STAFF} or current.role != actor.role:
            raise ServiceError(403, "Insufficient permissions")
        identifiers = selected_ids(read, as_of)
        report["eligible_subscription_count"] = len(identifiers)
        if dry_run:
            rules = rules_for(read)
            for identifier in identifiers:
                row = read.get(Subscription, identifier)
                try:
                    result, consumed = process_subscription(read, row, as_of, True, rules, actor, clock)
                    merge(result)
                    rules = consumed
                except Exception as error:
                    failure(identifier, row.number, error)
    if not dry_run:
        for identifier in identifiers:
            number = f"SUB-{identifier:06d}"
            try:
                with session_factory() as session:
                    with write_scope(session, actor, UserRole.ADMIN, UserRole.STAFF):
                        row = session.get(Subscription, identifier)
                        if row is None:
                            raise ValueError("Subscription no longer exists")
                        number = row.number
                        result, _ = process_subscription(session, row, as_of, False, rules_for(session), actor, clock)
                    # Merge only after successful commit, including commit-time failures.
                    merge(result)
            except ServiceError as error:
                if error.status_code in {401, 403}:
                    raise
                failure(identifier, number, error)
            except Exception as error:
                failure(identifier, number, error)
    return BillingReport(**report, generated_or_proposed_invoice_count=len(report["invoices"]),
        projected_or_actual_total_paise=sum(invoice["total_paise"] for invoice in report["invoices"]),
        skipped_count=len(report["skipped"]) + len(report["existing_invoices"]), failed_count=len(report["errors"]))

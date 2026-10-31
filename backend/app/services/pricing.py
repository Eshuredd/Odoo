"""Deterministic, database-free integer pricing and discount allocation."""
from dataclasses import asdict, dataclass
from datetime import date
from collections.abc import Sequence

from app.models.commercial_common import MAX_INTEGER


def checked(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_INTEGER:
        raise ValueError("Invoice amount exceeds the supported integer range")
    return value


def half_up(amount: int, basis_points: int) -> int:
    return (amount * basis_points + 5000) // 10000


@dataclass(frozen=True)
class Charge:
    line_type: str
    description: str
    quantity: int
    unit_price_paise: int
    tax_rate_basis_points: int = 0
    product_id: int | None = None
    variant_id: int | None = None


@dataclass(frozen=True)
class Rule:
    id: int
    name: str
    discount_type: str
    scope: str
    product_id: int | None
    value_paise: int | None
    rate_basis_points: int | None
    minimum_purchase_paise: int
    minimum_quantity: int
    valid_from: date
    valid_to: date
    usage_limit: int | None
    times_used: int
    active: bool = True


def allocate(amount: int, subtotals: list[int]) -> list[int]:
    base = sum(subtotals)
    if not base or not amount:
        return [0] * len(subtotals)
    shares = [amount * value // base for value in subtotals]
    order = sorted(range(len(shares)), key=lambda i: (-(amount * subtotals[i] % base), i))
    for index in order[:amount - sum(shares)]:
        shares[index] += 1
    return shares


def price_invoice(charges: Sequence[Charge], rules: Sequence[Rule], period_start: date) -> dict:
    if not charges:
        raise ValueError("An invoice needs at least one charge")
    for line in charges:
        checked(line.unit_price_paise)
        if not 1 <= line.quantity <= 1000000 or not 0 <= line.tax_rate_basis_points <= 10000:
            raise ValueError("Invalid frozen quantity or tax rate")
    subtotals = [checked(line.quantity * line.unit_price_paise) for line in charges]
    subtotal = checked(sum(subtotals))

    def calculation(shares: list[int]) -> dict:
        lines = []
        for line, base, discount in zip(charges, subtotals, shares):
            taxable = base - discount
            tax = checked(half_up(taxable, line.tax_rate_basis_points))
            lines.append({**asdict(line), "subtotal_paise": base, "discount_paise": discount,
                          "taxable_amount_paise": taxable, "tax_paise": tax, "total_paise": taxable + tax})
        return {"lines": lines, "subtotal_paise": subtotal, "discount_total_paise": sum(shares),
                "tax_total_paise": sum(line["tax_paise"] for line in lines),
                "total_paise": sum(line["total_paise"] for line in lines)}

    # Undiscounted total can exceed SQLite while a valid discount brings it into range.
    baseline = calculation([0] * len(charges))
    best, selected, saving = baseline, None, 0
    for rule in sorted(rules, key=lambda item: item.id):
        if not rule.active or not rule.valid_from <= period_start <= rule.valid_to:
            continue
        if rule.usage_limit is not None and rule.times_used >= rule.usage_limit:
            continue
        eligible = [value if rule.scope == "subscription" or line.product_id == rule.product_id else 0
                    for line, value in zip(charges, subtotals)]
        quantity = sum(line.quantity for line in charges if line.line_type == "product" and
                       (rule.scope == "subscription" or line.product_id == rule.product_id))
        if subtotal < rule.minimum_purchase_paise or quantity < rule.minimum_quantity or not sum(eligible):
            continue
        amount = min(sum(eligible), rule.value_paise) if rule.discount_type == "fixed" else half_up(sum(eligible), rule.rate_basis_points)
        result = calculation(allocate(amount, eligible))
        actual_saving = baseline["total_paise"] - result["total_paise"]
        if actual_saving > saving:
            best, selected, saving = result, rule, actual_saving
    for line in best["lines"]:
        checked(line["total_paise"])
    for name in ("subtotal_paise", "discount_total_paise", "tax_total_paise", "total_paise"):
        checked(best[name])
    snapshot = None
    if selected:
        snapshot = asdict(selected)
        snapshot["valid_from"] = selected.valid_from.isoformat()
        snapshot["valid_to"] = selected.valid_to.isoformat()
    return {**best, "applied_discount_id": selected.id if selected else None, "applied_discount_snapshot": snapshot}

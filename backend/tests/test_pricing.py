from dataclasses import replace
from datetime import date

import pytest

from app.models.commercial_common import MAX_INTEGER
from app.services.periods import boundary, due_periods, period_index
from app.services.pricing import Charge, Rule, allocate, half_up, price_invoice

D = date.fromisoformat


def rule(**overrides):
    return replace(Rule(1, "Synthetic rule", "fixed", "subscription", None, 100, None, 0, 1,
                        D("2024-01-01"), D("2030-12-31"), None, 0), **overrides)


@pytest.mark.parametrize("anchor,cadence,expected", [
    ("2026-01-31", "monthly", ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31"]),
    ("2028-01-31", "monthly", ["2028-01-31", "2028-02-29", "2028-03-31"]),
    ("2024-02-29", "yearly", ["2024-02-29", "2025-02-28", "2026-02-28", "2027-02-28", "2028-02-29"]),
    ("2026-01-31", "daily", ["2026-01-31", "2026-02-01", "2026-02-02"]),
    ("2026-01-31", "weekly", ["2026-01-31", "2026-02-07", "2026-02-14"]),
])
def test_boundaries_from_original_anchor(anchor, cadence, expected):
    assert [boundary(D(anchor), cadence, i).isoformat() for i in range(len(expected))] == expected
    for i, value in enumerate(expected):
        assert period_index(D(anchor), cadence, D(value)) == i


def test_inclusive_expiry_and_as_of_full_final_period():
    periods = list(due_periods(D("2026-01-31"), "monthly", D("2026-01-31"), D("2026-04-30"), D("2026-04-30")))
    assert len(periods) == 4 and periods[-1] == (D("2026-04-30"), D("2026-05-31"))
    assert list(due_periods(D("2026-01-31"), "monthly", D("2026-01-31"), D("2026-04-30"), D("2026-01-30"))) == []
    with pytest.raises(ValueError):
        period_index(D("2026-01-31"), "monthly", D("2026-03-28"))
    with pytest.raises((ValueError, OverflowError)):
        boundary(D("9999-12-31"), "monthly", 1)


def test_rounding_allocation_tax_and_fixed_cap():
    assert half_up(1, 5000) == 1 and half_up(1, 4999) == 0
    assert allocate(2, [1, 1, 1]) == [1, 1, 0]
    charges = [Charge("plan", "Base", 1, 1), Charge("product", "Item", 1, 2, 5000, 4)]
    value = price_invoice(charges, [rule(value_paise=1)], D("2026-01-01"))
    assert [line["discount_paise"] for line in value["lines"]] == [0, 1]
    assert (value["subtotal_paise"], value["discount_total_paise"], value["tax_total_paise"], value["total_paise"]) == (3, 1, 1, 3)
    capped = price_invoice(charges, [rule(value_paise=1000)], D("2026-01-01"))
    assert capped["total_paise"] == 0 and capped["discount_total_paise"] == 3


def test_product_scope_percentage_and_best_actual_saving_tie():
    charges = [Charge("plan", "Base", 1, 100), Charge("product", "A", 2, 100, 10000, 4), Charge("product", "B", 1, 100, 0, 5)]
    product = rule(scope="product", product_id=4, discount_type="percentage", value_paise=None, rate_basis_points=5000)
    value = price_invoice(charges, [rule(id=2, value_paise=120), product], D("2026-01-01"))
    assert value["applied_discount_id"] == 1  # 100 + 100 tax saving beats 120 + 60 tax saving.
    assert [line["discount_paise"] for line in value["lines"]] == [0, 100, 0]
    assert value["total_paise"] == 400
    tie = price_invoice(charges, [product, replace(product, id=0)], D("2026-01-01"))
    assert tie["applied_discount_id"] == 0


@pytest.mark.parametrize("changes", [
    {"active": False}, {"times_used": 1, "usage_limit": 1}, {"minimum_purchase_paise": 999},
    {"minimum_quantity": 3}, {"valid_to": D("2025-12-31")},
    {"scope": "product", "product_id": 99}, {"value_paise": 0},
])
def test_ineligible_rules_do_not_consume(changes):
    value = price_invoice([Charge("product", "A", 2, 100, 1800, 4)], [rule(**changes)], D("2026-01-01"))
    assert value["applied_discount_id"] is None and value["total_paise"] == 236


def test_large_integer_values_and_explicit_overflow():
    charges = [Charge("product", "Big", 1, MAX_INTEGER, 0, 1)]
    assert price_invoice(charges, [], D("2026-01-01"))["total_paise"] == MAX_INTEGER
    with pytest.raises(ValueError, match="integer range"):
        price_invoice([replace(charges[0], tax_rate_basis_points=1)], [], D("2026-01-01"))
    with pytest.raises(ValueError):
        price_invoice([replace(charges[0], quantity=2)], [], D("2026-01-01"))
    for amount in range(1, 50):
        shares = allocate(amount, [7, 13, 30])
        assert sum(shares) == amount and all(0 <= a <= b for a, b in zip(shares, [7, 13, 30]))

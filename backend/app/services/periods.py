"""Pure anchored calendar arithmetic, shared by preview and execution."""
from calendar import monthrange
from datetime import date, timedelta
from collections.abc import Iterator


def boundary(anchor: date, cadence: str, index: int) -> date:
    if index < 0:
        raise ValueError("Billing index cannot be negative")
    if cadence in {"daily", "weekly"}:
        return anchor + timedelta(days=index * (1 if cadence == "daily" else 7))
    if cadence not in {"monthly", "yearly"}:
        raise ValueError("Unsupported billing frequency")
    months = anchor.year * 12 + anchor.month - 1 + index * (1 if cadence == "monthly" else 12)
    year, month = divmod(months, 12)
    month += 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def period_index(anchor: date, cadence: str, start: date) -> int:
    if cadence in {"daily", "weekly"}:
        days = (start - anchor).days
        index = days // (1 if cadence == "daily" else 7)
    elif cadence == "monthly":
        index = (start.year - anchor.year) * 12 + start.month - anchor.month
    elif cadence == "yearly":
        index = start.year - anchor.year
    else:
        raise ValueError("Unsupported billing frequency")
    if boundary(anchor, cadence, index) != start:
        raise ValueError("Next billing date is not on the original anchor")
    return index


def due_periods(anchor: date, cadence: str, next_date: date, expiry: date, as_of: date) -> Iterator[tuple[date, date]]:
    index = period_index(anchor, cadence, next_date)
    start = next_date
    while start <= min(expiry, as_of):
        end = boundary(anchor, cadence, index + 1)
        yield start, end
        start, index = end, index + 1

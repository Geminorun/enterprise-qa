from __future__ import annotations

from datetime import date


def as_date(value: str | None) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return date.today()


def years_between(start: object, end: date) -> float | None:
    if not isinstance(start, str):
        return None
    try:
        start_date = date.fromisoformat(start)
    except ValueError:
        return None
    return round((end - start_date).days / 365.25, 1)


def full_years_between(start: object, end: date) -> int | None:
    if not isinstance(start, str):
        return None
    try:
        start_date = date.fromisoformat(start)
    except ValueError:
        return None
    years = end.year - start_date.year
    if (end.month, end.day) < (start_date.month, start_date.day):
        years -= 1
    return max(years, 0)

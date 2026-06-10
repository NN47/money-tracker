from datetime import date, datetime, timedelta
import re


def parse_relative_or_full_date(raw: str, *, today: date | None = None) -> date:
    """Parse relative Russian date phrases and full dd.mm.yyyy dates."""
    base_date = today or date.today()
    text = raw.strip().lower()
    if text == "сегодня":
        return base_date
    if text == "завтра":
        return base_date + timedelta(days=1)
    m = re.fullmatch(r"через\s+(\d+)\s+дн(?:я|ей)?", text)
    if m:
        return base_date + timedelta(days=int(m.group(1)))
    return datetime.strptime(text, "%d.%m.%Y").date()


def parse_transaction_date(raw: str, *, today: date | None = None) -> date:
    """Parse a transaction date.

    Short dates without a year (dd.mm) are treated as dates in the current
    year, including already-passed dates, because transactions often record
    operations that have already happened.
    """
    base_date = today or date.today()
    try:
        return parse_relative_or_full_date(raw, today=base_date)
    except ValueError:
        return datetime.strptime(raw.strip().lower(), "%d.%m").date().replace(year=base_date.year)


def parse_future_date(raw: str, *, today: date | None = None) -> date:
    """Parse a date for future-oriented entities such as scheduled payments."""
    base_date = today or date.today()
    try:
        return parse_relative_or_full_date(raw, today=base_date)
    except ValueError:
        parsed_date = datetime.strptime(raw.strip().lower(), "%d.%m").date().replace(year=base_date.year)
    if parsed_date < base_date:
        parsed_date = parsed_date.replace(year=parsed_date.year + 1)
    return parsed_date

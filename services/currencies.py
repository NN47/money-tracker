import re

DEFAULT_CURRENCY = "RUB"

CURRENCY_ALIASES = {
    "RUB": ["rub", "rur", "руб", "рубль", "рубли", "рублей", "₽", "р", "российский рубль"],
    "BYN": ["byn", "бел руб", "белруб", "белорусский рубль", "белорусские рубли", "br"],
    "UAH": ["uah", "грн", "гривна", "гривны", "гривен", "₴"],
    "KZT": ["kzt", "тенге", "тг", "₸"],
    "KGS": ["kgs", "сом", "киргизский сом", "кыргызский сом"],
    "UZS": ["uzs", "сум", "узбекский сум"],
    "TJS": ["tjs", "сомони", "таджикский сомони"],
    "AMD": ["amd", "драм", "драмы", "армянский драм", "֏"],
    "AZN": ["azn", "манат", "азербайджанский манат", "₼"],
    "MDL": ["mdl", "лей", "молдавский лей", "молдавские леи"],
    "GEL": ["gel", "лари", "грузинский лари", "₾"],
    "TMT": ["tmt", "туркменский манат", "манат тм"],
    "USD": ["usd", "dollar", "dollars", "доллар", "доллары", "долларов", "бакс", "баксы", "$"],
    "EUR": ["eur", "euro", "евро", "€"],
    "TRY": ["try", "лира", "лиры", "турецкая лира", "₺"],
}

SUPPORTED_CURRENCIES = tuple(CURRENCY_ALIASES.keys())

_ALIAS_TO_CODE = {
    alias.casefold(): code
    for code, aliases in CURRENCY_ALIASES.items()
    for alias in [code, *aliases]
}
_PATTERN = re.compile(
    r"(?<![\wа-яё])(" + "|".join(re.escape(a) for a in sorted(_ALIAS_TO_CODE, key=len, reverse=True)) + r")(?![\wа-яё])",
    re.IGNORECASE,
)


def extract_currency(text: str) -> tuple[str | None, str]:
    """Extract the first supported currency alias and return (ISO code, cleaned text)."""
    match = _PATTERN.search(text or "")
    if not match:
        return None, (text or "").strip()
    code = _ALIAS_TO_CODE[match.group(1).casefold()]
    cleaned = f"{text[:match.start()]} {text[match.end():]}"
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return code, cleaned


CURRENCY_SYMBOLS = {
    "RUB": "₽",
    "UAH": "₴",
    "KZT": "₸",
    "USD": "$",
    "EUR": "€",
    "TRY": "₺",
    "GEL": "₾",
    "AMD": "֏",
    "AZN": "₼",
    "BYN": "Br",
    "KGS": "с",
    "UZS": "сум",
    "TJS": "сомони",
    "MDL": "L",
    "TMT": "m",
}


def format_amount(value: int | float) -> str:
    formatted = f"{float(value):,.2f}".replace(",", " ")
    if formatted.endswith(".00"):
        return formatted[:-3]
    return formatted.rstrip("0").rstrip(".")


def format_money(amount: int | float, currency: str | None = DEFAULT_CURRENCY) -> str:
    code = (currency or DEFAULT_CURRENCY).upper()
    symbol = CURRENCY_SYMBOLS.get(code, code)
    return f"{format_amount(amount)} {symbol}"


def format_money_with_currency(value: float, currency: str | None) -> str:
    return format_money(value, currency)

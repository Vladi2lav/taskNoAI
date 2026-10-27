import re
from decimal import Decimal, InvalidOperation

QUOTES = re.compile(r'[«»"\'“”„`]')
NON_DIGITS = re.compile(r'\D')
TRAILING_BIN = re.compile(r'\s*(\d{12})\s*$')
EMPTY_MARKS = {'', '-', '—'}

UNITS = [
    (re.compile(r'(?<!/)\b(тонн[аы]?|тн|tonna)\b', re.I), 'т'),
    (re.compile(r'(?<!/)\b(килограмм\w*|кг)\b', re.I), 'кг'),
    (re.compile(r'(?<!/)\b(литр\w*|л)\b', re.I), 'л'),
    (re.compile(r'(?<!/)(м3|м³|куб\.?\s*м)', re.I), 'м³'),
    (re.compile(r'(?<!/)\b(штук\w*|шт)\b', re.I), 'шт'),
]


def clean(value) -> str | None:
    if value is None:
        return None
    text = ' '.join(str(value).split())
    return None if text in EMPTY_MARKS else text


def norm_text(value) -> str:
    text = clean(value)
    if not text:
        return ''
    text = text.replace('ё', 'е').replace('Ё', 'Е')
    text = QUOTES.sub('', text)
    return ' '.join(text.split()).lower()


def to_decimal(value) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    text = clean(value)
    if text is None:
        return None
    text = text.replace('\xa0', '').replace(' ', '').replace(',', '.')
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_int(value) -> int | None:
    number = to_decimal(value)
    return int(number) if number is not None else None


def norm_bin(value) -> str | None:
    digits = NON_DIGITS.sub('', str(value or ''))
    return digits if len(digits) == 12 else None


def split_name_bin(value) -> tuple[str | None, str | None]:
    text = clean(value)
    if not text:
        return None, None
    match = TRAILING_BIN.search(text)
    if not match:
        return text, None
    return clean(text[:match.start()]), match.group(1)


def norm_tnved(value) -> str | None:
    digits = NON_DIGITS.sub('', str(clean(value) or ''))
    return digits or None


def detect_unit(name: str | None) -> str | None:
    if not name:
        return None
    for pattern, unit in UNITS:
        if pattern.search(name):
            return unit
    return None


def split_kz_ru(name) -> tuple[str | None, str | None]:
    text = clean(name)
    if not text or '/' not in text:
        return text, None
    kz, ru = text.split('/', 1)
    return clean(ru) or clean(kz), clean(kz)

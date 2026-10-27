import time
from datetime import date, datetime, timedelta
from decimal import Decimal

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app.utils.normalize import (clean, detect_unit, norm_tnved, split_name_bin,
                                 to_decimal, to_int)

BASE_URL = 'https://ccx.kz/trading-and-analytics/trading-results'
PAGE_TIMEOUT = 20
PAUSE = 1.5
MAX_PAGES = 500

COLUMNS = {
    'date': 'дата',
    'tnved': 'тн вэд',
    'good': 'наименование товара',
    'price_open': 'цена открытия',
    'price_close': 'цена закрытия',
    'price_max': 'макс. цена',
    'price_min': 'мин. цена',
    'price_avg': 'средневзвеш',
    'amount': 'сумма сделки',
    'buyer_broker': 'брокер покупателя',
    'buyer': 'наименование покупателя',
    'seller_broker': 'брокер продавца',
    'seller': 'наименование продавца',
    'deals_count': 'кол-во заключенных сделок',
    'delivery_terms': 'условие поставки',
}
REQUIRED = {'date', 'good', 'buyer', 'seller'}

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (trades-portal parser)'})


def cell_text(td) -> str:
    full = td.select_one('[title]')
    if full and full['title'].strip():
        return full['title'].strip()
    return td.get_text(' ', strip=True)


def get_page(params: dict) -> list[dict]:
    time.sleep(PAUSE)
    response = session.get(BASE_URL, params={**params, 'lang': 'ru'}, timeout=PAGE_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    table = soup.select_one('table.custom-table-flexible')
    if table is None:
        if soup.select_one('.empty-state'):
            return []
        raise ValueError('На странице нет ни таблицы, ни сообщения «Нет данных»')

    headers = [th.get_text(' ', strip=True).lower() for th in table.select('thead th')]
    columns = {}
    for key, needle in COLUMNS.items():
        for index, header in enumerate(headers):
            if needle in header:
                columns[key] = index
                break

    missing = REQUIRED - columns.keys()
    if missing:
        raise ValueError(f'В таблице Каспия нет колонок: {", ".join(sorted(missing))}')

    rows = []
    for tr in table.select('tbody tr'):
        cells = [cell_text(td) for td in tr.select('td')]
        rows.append({key: cells[index] if index < len(cells) else None
                     for key, index in columns.items()})
    return rows


def pages(params: dict):
    previous = None
    for page in range(1, MAX_PAGES + 1):
        rows = get_page({**params, 'page': page})
        signature = sorted(tuple(row.values()) for row in rows)
        if not rows or signature == previous:
            return
        yield rows
        previous = signature
    raise ValueError(f'Больше {MAX_PAGES} страниц, пагинация не заканчивается')


def parse_date(text: str) -> date:
    return datetime.strptime(text, '%d.%m.%Y').date()


def day_url(trade_date: date) -> str:
    day = trade_date.isoformat()
    return f'{BASE_URL}?date_from={day}&date_to={day}&lang=ru'


def list_days() -> list[tuple[date, str]]:
    first = date.fromisoformat(current_app.config['CCX_HISTORY_FROM'])
    total = (date.today() - first).days + 1
    days = [first + timedelta(days=i) for i in range(total)]
    return [(day, day_url(day)) for day in days]


def is_deal(row: dict) -> bool:
    return bool(clean(row.get('seller')) or clean(row.get('buyer')))


def to_record(row: dict, trade_date: date) -> dict:
    seller, seller_bin = split_name_bin(row.get('seller'))
    buyer, buyer_bin = split_name_bin(row.get('buyer'))
    good = clean(row['good'])
    amount = to_decimal(row.get('amount'))
    price_avg = to_decimal(row.get('price_avg'))

    return {
        'trade_date': trade_date,
        'good_name_ru': good,
        'good_name_kz': None,
        'good_code': None,
        'tnved': norm_tnved(row.get('tnved')),
        'unit': detect_unit(good),
        'seller': seller,
        'seller_bin': seller_bin,
        'buyer': buyer,
        'buyer_bin': buyer_bin,
        'seller_broker': clean(row.get('seller_broker')),
        'buyer_broker': clean(row.get('buyer_broker')),
        'deals_count': to_int(row.get('deals_count')),
        'price_open': to_decimal(row.get('price_open')),
        'price_close': to_decimal(row.get('price_close')),
        'price_max': to_decimal(row.get('price_max')),
        'price_min': to_decimal(row.get('price_min')),
        'price_avg': price_avg,
        'amount': amount,
        'volume': (amount / price_avg).quantize(Decimal('0.001'))
                  if amount is not None and price_avg else None,
        'delivery_terms': clean(row.get('delivery_terms')),
    }


def fetch_day(source: str, trade_date: date) -> list[dict]:
    day = trade_date.isoformat()
    seen = set()
    records = []

    for rows in pages({'date_from': day, 'date_to': day}):
        for row in rows:
            key = tuple(row.values())
            if key in seen or not is_deal(row):
                continue
            seen.add(key)

            if parse_date(row['date']) != trade_date:
                raise ValueError(f'Каспий вернул дату {row["date"]} вместо {trade_date}')
            records.append(to_record(row, trade_date))

    return records

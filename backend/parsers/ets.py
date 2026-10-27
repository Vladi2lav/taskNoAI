import re
import time
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from urllib.parse import urljoin

import openpyxl
import requests
from bs4 import BeautifulSoup

from app.utils.normalize import (clean, detect_unit, norm_bin, norm_tnved,
                                 split_kz_ru, to_decimal, to_int)

ROOT_URL = 'https://ets.kz/documents/trading-results/'
PAGE_TIMEOUT = 10
FILE_TIMEOUT = 30
PAUSE = 1.5
MAX_DEPTH = 4

DATE_RE = re.compile(r'\d{2}\.\d{2}\.\d{4}')

COLUMNS = {
    'buyer': 'наименование покупателя',
    'buyer_bin': 'бин покупателя',
    'buyer_broker': 'брокера покупателя',
    'seller': 'наименование продавца',
    'seller_bin': 'бин продавца',
    'seller_broker': 'брокера продавца',
    'good': 'наименование товара',
    'tnved': 'тн вэд',
    'good_code': 'код товара',
    'deals_count': 'количество заключенных сделок',
    'price_open': 'цена открытия',
    'price_close': 'цена закрытия',
    'price_max': 'максимальная цена',
    'price_min': 'минимальная цена',
    'price_avg': 'средневзвеш',
    'amount': 'общая сумма',
}
REQUIRED = {'good', 'seller', 'buyer'}

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (trades-portal parser)'})


def fetch(url: str, timeout: int) -> requests.Response:
    time.sleep(PAUSE)
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response


def crawl(url: str = ROOT_URL, depth: int = 0, visited: set | None = None) -> list[tuple[date, str]]:
    if visited is None:
        visited = set()
    if url in visited or depth > MAX_DEPTH:
        return []
    visited.add(url)

    soup = BeautifulSoup(fetch(url, PAGE_TIMEOUT).text, 'lxml')
    files = files_on_page(soup, url)

    for a in soup.select('a[href]'):
        child = urljoin(url, a['href']).split('#')[0]
        if child.startswith(url) and child != url:
            files += crawl(child, depth + 1, visited)

    return files


def files_on_page(soup: BeautifulSoup, page_url: str) -> list[tuple[date, str]]:
    files = []
    for item in soup.select('div.i_documents_item'):
        link = item.select_one('a[href]')
        title = item.select_one('.i_documents_item_title')
        if link is None or title is None:
            raise ValueError(f'Изменилась вёрстка блока файла на {page_url}')
        if not link['href'].lower().endswith('.xlsx'):
            continue

        match = DATE_RE.search(title.get_text())
        if match is None:
            raise ValueError(f'Нет даты в названии «{title.get_text(strip=True)}» на {page_url}')

        trade_date = datetime.strptime(match.group(), '%d.%m.%Y').date()
        files.append((trade_date, urljoin(page_url, link['href'])))
    return files


def header_key(cell) -> str:
    text = ' '.join(str(cell or '').split()).lower()
    return text.rsplit('/', 1)[-1].strip()


def find_columns(rows: list[tuple]) -> tuple[int, dict[str, int]]:
    for row_index, row in enumerate(rows):
        headers = [header_key(cell) for cell in row]
        if not any(COLUMNS['good'] in header for header in headers):
            continue

        columns = {}
        for key, needle in COLUMNS.items():
            for col_index, header in enumerate(headers):
                if needle in header:
                    columns[key] = col_index
                    break

        missing = REQUIRED - columns.keys()
        if missing:
            raise ValueError(f'В заголовке нет колонок: {", ".join(sorted(missing))}')
        return row_index, columns

    raise ValueError('Не найдена строка заголовков (нет колонки «Наименование товара»)')


def parse_xlsx(content: bytes, trade_date: date) -> list[dict]:
    workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    rows = list(workbook.worksheets[0].iter_rows(values_only=True))
    workbook.close()

    header_row, columns = find_columns(rows)

    def cell(row, key):
        index = columns.get(key)
        return row[index] if index is not None and index < len(row) else None

    records = []
    for row in rows[header_row + 1:]:
        has_participant = clean(cell(row, 'seller')) or clean(cell(row, 'buyer'))
        if not clean(cell(row, 'good')) or not has_participant:
            continue

        name_ru, name_kz = split_kz_ru(cell(row, 'good'))
        amount = to_decimal(cell(row, 'amount'))
        price_avg = to_decimal(cell(row, 'price_avg'))

        records.append({
            'trade_date': trade_date,
            'good_name_ru': name_ru,
            'good_name_kz': name_kz,
            'good_code': clean(cell(row, 'good_code')),
            'tnved': norm_tnved(cell(row, 'tnved')),
            'unit': detect_unit(name_ru),
            'seller': clean(cell(row, 'seller')),
            'seller_bin': norm_bin(cell(row, 'seller_bin')),
            'buyer': clean(cell(row, 'buyer')),
            'buyer_bin': norm_bin(cell(row, 'buyer_bin')),
            'seller_broker': clean(cell(row, 'seller_broker')),
            'buyer_broker': clean(cell(row, 'buyer_broker')),
            'deals_count': to_int(cell(row, 'deals_count')),
            'price_open': to_decimal(cell(row, 'price_open')),
            'price_close': to_decimal(cell(row, 'price_close')),
            'price_max': to_decimal(cell(row, 'price_max')),
            'price_min': to_decimal(cell(row, 'price_min')),
            'price_avg': price_avg,
            'amount': amount,
            'volume': (amount / price_avg).quantize(Decimal('0.001'))
                      if amount is not None and price_avg else None,
            'delivery_terms': None,
        })
    return records


def fetch_day(file_url: str, trade_date: date) -> list[dict]:
    records = parse_xlsx(fetch(file_url, FILE_TIMEOUT).content, trade_date)
    if not records:
        raise ValueError(f'В файле за {trade_date} не найдено ни одной сделки')
    return records

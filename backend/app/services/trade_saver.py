import hashlib
import logging
from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.extensions import db
from app.models import Broker, Exchange, Good, Participant, ParserRun, Trade, TradingDay
from app.utils.normalize import norm_text

log = logging.getLogger(__name__)


class Lookup:
    def __init__(self):
        self.cache = {}

    def _cached(self, key, find, create):
        if key in self.cache:
            return self.cache[key]
        obj = find()
        if obj is None:
            obj = create()
            db.session.add(obj)
            db.session.flush()
        self.cache[key] = obj
        return obj

    def good(self, record) -> Good:
        code = record.get('good_code')
        norm = norm_text(record['good_name_ru'])

        def find():
            if code:
                return db.session.scalar(db.select(Good).filter_by(ets_code=code))
            return db.session.scalar(db.select(Good).filter_by(name_norm=norm).limit(1))

        def create():
            return Good(name_ru=record['good_name_ru'], name_kz=record.get('good_name_kz'),
                        name_norm=norm, ets_code=code, tnved=record.get('tnved'),
                        unit=record.get('unit'))

        good = self._cached(('good', code or norm), find, create)
        good.name_kz = good.name_kz or record.get('good_name_kz')
        good.tnved = good.tnved or record.get('tnved')
        good.unit = good.unit or record.get('unit')
        return good

    def participant(self, name, bin_) -> Participant | None:
        norm = norm_text(name)
        if not norm and not bin_:
            return None

        def find():
            if bin_:
                return db.session.scalar(db.select(Participant).filter_by(bin=bin_))
            return db.session.scalar(db.select(Participant).filter_by(name_norm=norm).limit(1))

        def create():
            return Participant(name=name or bin_, name_norm=norm or bin_, bin=bin_)

        return self._cached(('participant', bin_ or norm), find, create)

    def broker(self, name) -> Broker | None:
        norm = norm_text(name)
        if not norm:
            return None

        def find():
            return db.session.scalar(db.select(Broker).filter_by(name_norm=norm))

        return self._cached(('broker', norm), find, lambda: Broker(name=name, name_norm=norm))


def make_hash(exchange_code: str, record: dict, occurrence: int) -> str:
    parts = [
        exchange_code,
        str(record['trade_date']),
        record.get('good_code') or norm_text(record['good_name_ru']),
        record.get('seller_bin') or norm_text(record.get('seller')),
        record.get('buyer_bin') or norm_text(record.get('buyer')),
        norm_text(record.get('seller_broker')),
        norm_text(record.get('buyer_broker')),
        str(record.get('deals_count') or ''),
        str(record.get('price_avg') or ''),
        str(record.get('amount') or ''),
        str(occurrence),
    ]
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()


def get_exchange(code: str) -> Exchange:
    exchange = db.session.scalar(db.select(Exchange).filter_by(code=code))
    if exchange is None:
        raise ValueError(f'Биржа {code} не найдена, выполните flask seed')
    return exchange


def save_day(exchange: Exchange, trade_date: date, source_url: str,
             records: list[dict], run: ParserRun) -> tuple[int, int]:
    lookup = Lookup()
    repeats = Counter()
    rows = []

    for record in records:
        base_hash = make_hash(exchange.code, record, 0)
        repeats[base_hash] += 1

        good = lookup.good(record)
        seller = lookup.participant(record.get('seller'), record.get('seller_bin'))
        buyer = lookup.participant(record.get('buyer'), record.get('buyer_bin'))
        seller_broker = lookup.broker(record.get('seller_broker'))
        buyer_broker = lookup.broker(record.get('buyer_broker'))

        rows.append({
            'exchange_id': exchange.id,
            'trade_date': trade_date,
            'good_id': good.id,
            'seller_id': seller.id if seller else None,
            'buyer_id': buyer.id if buyer else None,
            'seller_broker_id': seller_broker.id if seller_broker else None,
            'buyer_broker_id': buyer_broker.id if buyer_broker else None,
            'deals_count': record.get('deals_count'),
            'price_open': record.get('price_open'),
            'price_close': record.get('price_close'),
            'price_max': record.get('price_max'),
            'price_min': record.get('price_min'),
            'price_avg': record.get('price_avg'),
            'amount': record.get('amount'),
            'volume': record.get('volume'),
            'delivery_terms': record.get('delivery_terms'),
            'parser_run_id': run.id,
            'dedup_hash': make_hash(exchange.code, record, repeats[base_hash] - 1),
        })

    day_trades = (Trade.exchange_id == exchange.id) & (Trade.trade_date == trade_date)
    old_hashes = set(db.session.scalars(db.select(Trade.dedup_hash).where(day_trades)))
    new_hashes = {row['dedup_hash'] for row in rows}

    db.session.execute(db.delete(Trade).where(day_trades))
    if rows:
        db.session.execute(insert(Trade).values(rows).on_conflict_do_nothing(index_elements=['dedup_hash']))

    removed = len(old_hashes - new_hashes)
    if removed:
        log.info('%s %s: биржа убрала %d записей', exchange.code, trade_date, removed)

    mark_day(exchange, trade_date, source_url, 'loaded', rows_count=len(rows))
    db.session.commit()
    return len(new_hashes - old_hashes), len(new_hashes & old_hashes)


def mark_day(exchange: Exchange, trade_date: date, source_url: str, status: str,
             rows_count: int | None = None) -> None:
    day = db.session.scalar(
        db.select(TradingDay).filter_by(exchange_id=exchange.id, trade_date=trade_date)
    )
    if day is None:
        day = TradingDay(exchange_id=exchange.id, trade_date=trade_date)
        db.session.add(day)
    day.source_url = source_url
    day.status = status
    day.rows_count = rows_count
    day.loaded_at = datetime.now(timezone.utc)

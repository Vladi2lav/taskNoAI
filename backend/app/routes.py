import logging
import threading
from datetime import date, datetime, timedelta, timezone
from io import BytesIO

from flask import Blueprint, current_app, jsonify, request, send_file
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Broker, Exchange, Good, Participant, ParserRun, Trade, TradingDay
from app.utils.normalize import norm_bin, norm_text, to_decimal

bp = Blueprint('api', __name__, url_prefix='/api')
log = logging.getLogger(__name__)

EXCHANGE_CODES = ['ets', 'ccx']
EXPORT_LIMIT = 100_000
EXPORT_COLUMNS = [
    ('Дата торгов', 12), ('Биржа', 8), ('Товар', 60), ('ТН ВЭД', 12), ('Ед.', 6),
    ('Продавец', 35), ('БИН продавца', 14), ('Покупатель', 35), ('БИН покупателя', 14),
    ('Брокер продавца', 30), ('Брокер покупателя', 30), ('Кол-во сделок', 8),
    ('Объём', 12), ('Цена за ед., тг', 14), ('Сумма сделки, тг', 16), ('Условие поставки', 14),
]

SORT_COLUMNS = {
    'trade_date': Trade.trade_date,
    'amount': Trade.amount,
    'price_avg': Trade.price_avg,
    'volume': Trade.volume,
}


def num(value):
    return float(value) if value is not None else None


def parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def trade_to_dict(t: Trade) -> dict:
    return {
        'id': t.id,
        'trade_date': t.trade_date.isoformat(),
        'exchange': t.exchange.name,
        'good': t.good.name_ru,
        'tnved': t.good.tnved,
        'unit': t.good.unit,
        'seller': t.seller.name if t.seller else None,
        'seller_bin': t.seller.bin if t.seller else None,
        'buyer': t.buyer.name if t.buyer else None,
        'buyer_bin': t.buyer.bin if t.buyer else None,
        'seller_broker': t.seller_broker.name if t.seller_broker else None,
        'buyer_broker': t.buyer_broker.name if t.buyer_broker else None,
        'deals_count': t.deals_count,
        'price_avg': num(t.price_avg),
        'amount': num(t.amount),
        'volume': num(t.volume),
        'delivery_terms': t.delivery_terms,
    }


def trade_filters(args) -> list:
    conditions = []

    exchange = args.get('exchange')
    if exchange:
        conditions.append(Trade.exchange.has(Exchange.code == exchange))

    date_from = parse_date(args.get('date_from'))
    date_to = parse_date(args.get('date_to'))
    if date_from:
        conditions.append(Trade.trade_date >= date_from)
    if date_to:
        conditions.append(Trade.trade_date <= date_to)

    good = norm_text(args.get('good'))
    if good:
        conditions.append(Trade.good.has(or_(
            Good.name_norm.contains(good, autoescape=True),
            Good.tnved.startswith(good.replace(' ', ''), autoescape=True),
        )))

    participant = norm_text(args.get('participant'))
    if participant:
        bin_ = norm_bin(participant)
        matches = Participant.bin == bin_ if bin_ else Participant.name_norm.contains(participant, autoescape=True)
        ids = db.select(Participant.id).where(matches)
        conditions.append(or_(Trade.seller_id.in_(ids), Trade.buyer_id.in_(ids)))

    broker = norm_text(args.get('broker'))
    if broker:
        ids = db.select(Broker.id).where(Broker.name_norm.contains(broker, autoescape=True))
        conditions.append(or_(Trade.seller_broker_id.in_(ids), Trade.buyer_broker_id.in_(ids)))

    amount_from = to_decimal(args.get('amount_from'))
    amount_to = to_decimal(args.get('amount_to'))
    if amount_from is not None:
        conditions.append(Trade.amount >= amount_from)
    if amount_to is not None:
        conditions.append(Trade.amount <= amount_to)

    delivery = (args.get('delivery') or '').strip()
    if delivery:
        conditions.append(or_(
            Trade.delivery_terms.icontains(delivery, autoescape=True),
            Trade.good.has(Good.name_norm.contains(norm_text(delivery), autoescape=True)),
        ))

    return conditions


def summary(conditions: list) -> dict:
    totals = db.session.execute(
        db.select(func.count(Trade.id), func.sum(Trade.amount), func.count(func.distinct(Trade.good_id)))
        .where(*conditions)
    ).one()

    by_exchange = db.session.execute(
        db.select(Exchange.name, func.count(Trade.id), func.sum(Trade.amount))
        .join(Trade.exchange)
        .where(*conditions)
        .group_by(Exchange.name)
        .order_by(Exchange.name)
    ).all()

    return {
        'trades': totals[0],
        'amount': num(totals[1]),
        'goods': totals[2],
        'by_exchange': [{'exchange': name, 'trades': count, 'amount': num(amount)}
                        for name, count, amount in by_exchange],
    }


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'})


def trades_query(args):
    sort_column = SORT_COLUMNS.get(args.get('sort'), Trade.trade_date)
    order = sort_column.asc() if args.get('order') == 'asc' else sort_column.desc()
    return (
        db.select(Trade)
        .where(*trade_filters(args))
        .options(joinedload(Trade.exchange), joinedload(Trade.good),
                 joinedload(Trade.seller), joinedload(Trade.buyer),
                 joinedload(Trade.seller_broker), joinedload(Trade.buyer_broker))
        .order_by(order.nulls_last(), Trade.id.desc())
    )


@bp.get('/trades')
def get_trades():
    page = max(request.args.get('page', 1, type=int), 1)
    per_page = min(max(request.args.get('per_page', 50, type=int), 1), 500)
    stats = summary(trade_filters(request.args))

    trades = db.session.scalars(
        trades_query(request.args).limit(per_page).offset((page - 1) * per_page)
    ).all()

    return jsonify({
        'items': [trade_to_dict(t) for t in trades],
        'total': stats['trades'],
        'page': page,
        'per_page': per_page,
        'pages': (stats['trades'] + per_page - 1) // per_page,
        'summary': stats,
    })


def name_of(obj):
    return obj.name if obj else None


@bp.get('/trades/export')
def export_trades():
    trades = db.session.scalars(trades_query(request.args).limit(EXPORT_LIMIT))

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet('Сделки')
    sheet.freeze_panes = 'A2'
    for index, (_, width) in enumerate(EXPORT_COLUMNS, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width

    header = []
    for title, _ in EXPORT_COLUMNS:
        cell = WriteOnlyCell(sheet, value=title)
        cell.font = Font(bold=True)
        header.append(cell)
    sheet.append(header)

    for t in trades:
        sheet.append([
            t.trade_date, t.exchange.name, t.good.name_ru, t.good.tnved, t.good.unit,
            name_of(t.seller), t.seller.bin if t.seller else None,
            name_of(t.buyer), t.buyer.bin if t.buyer else None,
            name_of(t.seller_broker), name_of(t.buyer_broker), t.deals_count,
            t.volume, t.price_avg, t.amount, t.delivery_terms,
        ])

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'trades_{date.today().isoformat()}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


def run_in_background(app, codes, full, date_from, date_to):
    from parsers.run import run_parser

    with app.app_context():
        for code in codes:
            try:
                run_parser(code, trigger='manual', full=full, date_from=date_from, date_to=date_to)
            except Exception:
                log.exception('Ручной запуск %s завершился ошибкой', code)


@bp.post('/parse')
def start_parse():
    data = request.get_json(silent=True) or {}

    exchange = data.get('exchange') or 'all'
    codes = EXCHANGE_CODES if exchange == 'all' else [exchange]
    if not set(codes) <= set(EXCHANGE_CODES):
        return jsonify({'message': 'Неизвестная биржа'}), 400

    date_from = parse_date(data.get('date_from'))
    date_to = parse_date(data.get('date_to'))
    if date_from and date_to and date_from > date_to:
        return jsonify({'message': 'Дата начала позже даты окончания'}), 400
    if date_from and date_from > date.today():
        return jsonify({'message': 'Дата начала в будущем'}), 400

    recent = datetime.now(timezone.utc) - timedelta(hours=3)
    running = db.session.scalar(
        db.select(ParserRun).join(ParserRun.exchange)
        .where(ParserRun.status == 'running', ParserRun.started_at > recent, Exchange.code.in_(codes))
        .limit(1)
    )
    if running:
        return jsonify({'message': f'Уже идёт загрузка {running.exchange.name}, дождитесь окончания'}), 409

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=run_in_background,
        args=(app, codes, bool(data.get('full')), date_from, date_to),
        daemon=True,
    )
    thread.start()
    return jsonify({'message': 'Загрузка запущена'}), 202


def top_participants(role_column, conditions, limit=10) -> list[dict]:
    rows = db.session.execute(
        db.select(Participant.name, Participant.bin, func.sum(Trade.amount), func.count(Trade.id))
        .join(Participant, Participant.id == role_column)
        .where(*conditions, Trade.amount.is_not(None))
        .group_by(Participant.id)
        .order_by(func.sum(Trade.amount).desc())
        .limit(limit)
    ).all()
    return [{'name': name, 'bin': bin_, 'amount': num(amount), 'trades': count}
            for name, bin_, amount, count in rows]


@bp.get('/analytics')
def get_analytics():
    conditions = trade_filters(request.args)
    month = func.date_trunc('month', Trade.trade_date)

    turnover = {}
    for month_start, exchange, amount, count in db.session.execute(
        db.select(month, Exchange.name, func.sum(Trade.amount), func.count(Trade.id))
        .join(Trade.exchange)
        .where(*conditions)
        .group_by(month, Exchange.name)
        .order_by(month)
    ):
        key = month_start.strftime('%Y-%m')
        turnover.setdefault(key, {'month': key})
        turnover[key][exchange] = num(amount)
        turnover[key][f'{exchange}_trades'] = count

    prices = db.session.execute(
        db.select(month, func.sum(Trade.amount) / func.nullif(func.sum(Trade.volume), 0),
                  func.min(Trade.price_min), func.max(Trade.price_max))
        .where(*conditions, Trade.amount.is_not(None), Trade.volume.is_not(None))
        .group_by(month)
        .order_by(month)
    ).all()

    top_goods = db.session.execute(
        db.select(Good.name_ru, Good.unit, func.sum(Trade.amount), func.sum(Trade.volume), func.count(Trade.id))
        .join(Trade.good)
        .where(*conditions, Trade.amount.is_not(None))
        .group_by(Good.id)
        .order_by(func.sum(Trade.amount).desc())
        .limit(10)
    ).all()

    return jsonify({
        'turnover': list(turnover.values()),
        'prices': [{'month': m.strftime('%Y-%m'), 'avg': num(avg), 'min': num(low), 'max': num(high)}
                   for m, avg, low, high in prices],
        'top_goods': [{'name': name, 'unit': unit, 'amount': num(amount), 'volume': num(volume), 'trades': count}
                      for name, unit, amount, volume, count in top_goods],
        'top_sellers': top_participants(Trade.seller_id, conditions),
        'top_buyers': top_participants(Trade.buyer_id, conditions),
    })


def iso(value):
    return value.isoformat() if value else None


def run_to_dict(run: ParserRun) -> dict:
    return {
        'id': run.id,
        'exchange': run.exchange.name,
        'trigger': run.trigger,
        'status': run.status,
        'started_at': iso(run.started_at),
        'finished_at': iso(run.finished_at),
        'added': run.added,
        'skipped': run.skipped,
        'error_message': run.error_message,
    }


@bp.get('/status')
def get_status():
    exchanges = []
    for exchange in db.session.scalars(db.select(Exchange).order_by(Exchange.id)):
        count, first_date, last_date = db.session.execute(
            db.select(func.count(Trade.id), func.min(Trade.trade_date), func.max(Trade.trade_date))
            .where(Trade.exchange_id == exchange.id)
        ).one()

        days = dict(db.session.execute(
            db.select(TradingDay.status, func.count())
            .where(TradingDay.exchange_id == exchange.id)
            .group_by(TradingDay.status)
        ).all())

        last_update = db.session.scalar(
            db.select(func.max(TradingDay.loaded_at))
            .filter_by(exchange_id=exchange.id, status='loaded')
        )

        last_run = db.session.scalar(
            db.select(ParserRun).filter_by(exchange_id=exchange.id)
            .order_by(ParserRun.id.desc()).limit(1)
        )

        exchanges.append({
            'exchange': exchange.name,
            'trades_count': count,
            'first_trade_date': iso(first_date),
            'last_trade_date': iso(last_date),
            'last_update': iso(last_update),
            'days_loaded': days.get('loaded', 0),
            'days_error': days.get('error', 0),
            'last_run': run_to_dict(last_run) if last_run else None,
        })

    runs = db.session.scalars(
        db.select(ParserRun).options(joinedload(ParserRun.exchange))
        .order_by(ParserRun.id.desc()).limit(20)
    ).all()

    return jsonify({
        'exchanges': exchanges,
        'total_trades': sum(e['trades_count'] for e in exchanges),
        'runs': [run_to_dict(run) for run in runs],
    })

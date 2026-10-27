import logging
from datetime import date, datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models import ParserRun, TradingDay
from app.services.trade_saver import get_exchange, mark_day, save_day
from parsers import ccx, ets

log = logging.getLogger(__name__)

PARSERS = {
    'ets': (ets.crawl, ets.fetch_day),
    'ccx': (ccx.list_days, ccx.fetch_day),
}


def loaded_days(exchange_id: int) -> set:
    query = db.select(TradingDay.trade_date).filter_by(exchange_id=exchange_id, status='loaded')
    return set(db.session.scalars(query))


def run_parser(code: str, trigger: str = 'manual', full: bool = False, limit: int | None = None,
               date_from: date | None = None, date_to: date | None = None) -> ParserRun:
    list_days, fetch_day = PARSERS[code]
    exchange = get_exchange(code)

    run = ParserRun(exchange_id=exchange.id, trigger=trigger, status='running')
    db.session.add(run)
    db.session.commit()

    errors = []
    try:
        days = sorted(list_days(), reverse=True)
        if date_from:
            days = [(day, source) for day, source in days if day >= date_from]
        if date_to:
            days = [(day, source) for day, source in days if day <= date_to]
        if not full:
            done = loaded_days(exchange.id)
            recheck_from = date.today() - timedelta(days=current_app.config['RECHECK_DAYS'])
            days = [(day, source) for day, source in days
                    if day not in done or day >= recheck_from]
        if limit:
            days = days[:limit]
        log.info('%s: к загрузке %d дней', code, len(days))

        for trade_date, source in days:
            try:
                records = fetch_day(source, trade_date)
                added, skipped = save_day(exchange, trade_date, source, records, run)
                run.added += added
                run.skipped += skipped
                log.info('%s %s: +%d, дублей %d', code, trade_date, added, skipped)
            except Exception as e:
                db.session.rollback()
                log.exception('%s %s: ошибка', code, trade_date)
                errors.append(f'{trade_date}: {type(e).__name__}: {e}')
                mark_day(exchange, trade_date, source, 'error')
                db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.exception('%s: не удалось получить список дней', code)
        errors.append(f'{type(e).__name__}: {e}')

    run = db.session.get(ParserRun, run.id)
    run.status = 'error' if errors else 'success'
    run.error_message = '\n'.join(errors)[:5000] or None
    run.finished_at = datetime.now(timezone.utc)
    db.session.commit()
    return run

import logging

import click
from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.extensions import db, migrate

EXCHANGES = [('ets', 'ETS'), ('ccx', 'Каспий')]
EXCHANGE_CODES = [code for code, _ in EXCHANGES]


def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.ensure_ascii = False
    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)

    from app import models
    from app.routes import bp as api_bp
    app.register_blueprint(api_bp)

    @app.cli.command('seed', help='Заполнить справочник бирж')
    def seed():
        for code, name in EXCHANGES:
            if not db.session.scalar(db.select(models.Exchange).filter_by(code=code)):
                db.session.add(models.Exchange(code=code, name=name))
        db.session.commit()
        click.echo('Справочник бирж готов.')

    @app.cli.command('parse', help='Загрузить новые дни биржи: flask parse ets')
    @click.argument('exchange', type=click.Choice(EXCHANGE_CODES))
    @click.option('--full', is_flag=True, help='Перепроверить и уже загруженные дни')
    @click.option('--limit', type=int, help='Только N самых свежих дней')
    def parse(exchange, full, limit):
        from parsers.run import run_parser

        setup_logging()
        run = run_parser(exchange, trigger='manual', full=full, limit=limit)
        click.echo(f'{exchange}: {run.status}, добавлено {run.added}, дублей {run.skipped}')
        if run.error_message:
            click.echo(run.error_message)

    @app.cli.command('scheduler', help='Запускать парсеры по расписанию из PARSE_SCHEDULE')
    def scheduler():
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        from parsers.run import run_parser

        setup_logging()
        log = logging.getLogger('scheduler')

        def run_all():
            with app.app_context():
                for code in app.config['PARSE_EXCHANGES']:
                    run = run_parser(code.strip(), trigger='schedule')
                    log.info('%s: %s, добавлено %d', code, run.status, run.added)

        trigger = CronTrigger.from_crontab(app.config['PARSE_SCHEDULE'], timezone=app.config['PARSE_TIMEZONE'])
        jobs = BlockingScheduler()
        jobs.add_job(run_all, trigger, max_instances=1, coalesce=True)
        log.info('Расписание: %s (%s), биржи: %s', app.config['PARSE_SCHEDULE'],
                 app.config['PARSE_TIMEZONE'], ', '.join(app.config['PARSE_EXCHANGES']))
        jobs.start()

    return app

import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5433/postgres',
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv('SQL_ECHO') == '1'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'connect_args': {'connect_timeout': 5},
    }

    PARSE_SCHEDULE = os.getenv('PARSE_SCHEDULE', '0 7 * * *')
    PARSE_TIMEZONE = os.getenv('PARSE_TIMEZONE', 'Asia/Almaty')
    PARSE_EXCHANGES = os.getenv('PARSE_EXCHANGES', 'ets,ccx').split(',')
    RECHECK_DAYS = int(os.getenv('RECHECK_DAYS', '3'))
    CCX_HISTORY_FROM = os.getenv('CCX_HISTORY_FROM', '2025-02-01')

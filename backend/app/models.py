from sqlalchemy import func

from app.extensions import db


class Exchange(db.Model):
    __tablename__ = 'exchanges'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)


class Good(db.Model):
    __tablename__ = 'goods'

    id = db.Column(db.Integer, primary_key=True)
    name_ru = db.Column(db.String(1000), nullable=False)
    name_kz = db.Column(db.String(1000))
    name_norm = db.Column(db.String(1000), nullable=False, index=True)
    ets_code = db.Column(db.String(50), unique=True)
    tnved = db.Column(db.String(20), index=True)
    unit = db.Column(db.String(20))


class Participant(db.Model):
    __tablename__ = 'participants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500), nullable=False)
    name_norm = db.Column(db.String(500), nullable=False, index=True)
    bin = db.Column(db.String(12), unique=True)


class Broker(db.Model):
    __tablename__ = 'brokers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500), nullable=False)
    name_norm = db.Column(db.String(500), unique=True, nullable=False)


class ParserRun(db.Model):
    __tablename__ = 'parser_runs'

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('exchanges.id'), nullable=False, index=True)
    trigger = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='running')
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = db.Column(db.DateTime(timezone=True))
    added = db.Column(db.Integer, nullable=False, default=0)
    skipped = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text)

    exchange = db.relationship('Exchange')


class TradingDay(db.Model):
    __tablename__ = 'trading_days'
    __table_args__ = (
        db.UniqueConstraint('exchange_id', 'trade_date', name='uq_trading_days_exchange_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('exchanges.id'), nullable=False)
    trade_date = db.Column(db.Date, nullable=False)
    source_url = db.Column(db.String(1000))
    status = db.Column(db.String(20), nullable=False)
    rows_count = db.Column(db.Integer)
    loaded_at = db.Column(db.DateTime(timezone=True))

    exchange = db.relationship('Exchange')


class Trade(db.Model):
    __tablename__ = 'trades'
    __table_args__ = (
        db.Index('ix_trades_exchange_date', 'exchange_id', 'trade_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('exchanges.id'), nullable=False)
    trade_date = db.Column(db.Date, nullable=False, index=True)

    good_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('participants.id'), index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('participants.id'), index=True)
    seller_broker_id = db.Column(db.Integer, db.ForeignKey('brokers.id'), index=True)
    buyer_broker_id = db.Column(db.Integer, db.ForeignKey('brokers.id'), index=True)

    deals_count = db.Column(db.Integer)
    price_open = db.Column(db.Numeric(18, 2))
    price_close = db.Column(db.Numeric(18, 2))
    price_max = db.Column(db.Numeric(18, 2))
    price_min = db.Column(db.Numeric(18, 2))
    price_avg = db.Column(db.Numeric(18, 2))
    amount = db.Column(db.Numeric(18, 2), index=True)
    volume = db.Column(db.Numeric(18, 3))
    delivery_terms = db.Column(db.String(500))

    parser_run_id = db.Column(db.Integer, db.ForeignKey('parser_runs.id'))
    dedup_hash = db.Column(db.String(64), unique=True, nullable=False)

    exchange = db.relationship('Exchange')
    good = db.relationship('Good')
    seller = db.relationship('Participant', foreign_keys=[seller_id])
    buyer = db.relationship('Participant', foreign_keys=[buyer_id])
    seller_broker = db.relationship('Broker', foreign_keys=[seller_broker_id])
    buyer_broker = db.relationship('Broker', foreign_keys=[buyer_broker_id])
    parser_run = db.relationship('ParserRun')

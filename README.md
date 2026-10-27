# Итоги торгов ETS и Каспий

Система собирает итоги биржевых торгов с двух площадок в локальную базу и показывает их на веб-портале
с фильтрами, сортировкой и постраничным выводом.

| Источник | Адрес | Формат | История |
|---|---|---|---|
| ETS | https://ets.kz/documents/trading-results/ | xlsx-файл на каждый торговый день | с 01.07.2025 |
| Каспий | https://ccx.kz/trading-and-analytics/trading-results | HTML-таблица | с 04.02.2025 |

## Состав

| Часть | Технологии | Где |
|---|---|---|
| Парсеры | Python, requests, BeautifulSoup, openpyxl | `backend/parsers/` |
| База данных | PostgreSQL, SQLAlchemy, миграции Alembic | `backend/app/models.py`, `backend/migrations/` |
| API | Flask | `backend/app/routes.py` |
| Расписание | APScheduler | команда `flask scheduler`, сервис `scheduler` |
| Экспорт и графики | openpyxl, Recharts | `/api/trades/export`, страница «Аналитика» |
| Портал | React, React Router, Vite, nginx | `frontend/` |

## Запуск

Нужен только Docker (Docker Desktop на Windows/macOS).

```bash
git clone https://github.com/Vladi2lav/taskNoAI.git
cd taskNoAI
docker compose up -d --build
```

После запуска:

| Что | Адрес |
|---|---|
| Портал | http://localhost:3000 |
| API | http://localhost:4000/api/trades |
| PostgreSQL с компьютера | `localhost:5433`, пользователь и пароль `postgres` |

При старте контейнер `flaskapp` сам применяет миграции и заполняет справочник бирж.
База сначала пустая — загрузите данные (следующий раздел).

## Загрузка данных

Первая загрузка всей истории (ETS — около 10 минут, Каспий — около 20 минут):

```bash
docker compose exec flaskapp flask parse ets
docker compose exec flaskapp flask parse ccx
```

| Команда | Что делает |
|---|---|
| `flask parse ets` | загрузить дни ETS, которых ещё нет в базе |
| `flask parse ccx` | то же для Каспия |
| `flask parse ets --limit 3` | только 3 самых свежих незагруженных дня |
| `flask parse ets --full` | перепроверить все дни; дубли не создаются |

Повторный запуск не создаёт дублей и догружает дни, которые раньше завершились ошибкой.
Результат каждого запуска — на странице «Состояние данных» портала.

## Расписание

Сервис `scheduler` каждый день запускает оба парсера. Настройки — в `compose.yml`, блок `x-backend-env`:

| Переменная | По умолчанию | Значение |
|---|---|---|
| `PARSE_SCHEDULE` | `0 7 * * *` | расписание в формате cron (минута час день месяц день-недели) |
| `PARSE_TIMEZONE` | `Asia/Almaty` | часовой пояс расписания |
| `PARSE_EXCHANGES` | `ets,ccx` | какие биржи загружать |
| `RECHECK_DAYS` | `3` | сколько последних дней перепроверять при каждом запуске |
| `CCX_HISTORY_FROM` | `2025-02-01` | с какой даты перебирать дни Каспия |

После изменения: `docker compose up -d scheduler`.

## Портал

- **Сделки** — таблица с постраничным выводом и сортировкой по дате, объёму, цене и сумме
  (клик по заголовку). Фильтры работают в комбинации, без перезагрузки страницы:
  биржа, период, товар или код ТН ВЭД, продавец или покупатель (название или БИН), брокер,
  диапазон суммы, место поставки. Под таблицей — сводка по текущей выборке.
- **Аналитика** — оборот по месяцам (ETS и Каспий), динамика средневзвешенной цены, топ-10 товаров,
  продавцов и покупателей; те же фильтры, что у таблицы.
- **Состояние данных** — по каждой бирже: число записей, период, последнее обновление, загруженные дни
  и дни с ошибкой, последний запуск; журнал запусков. Кнопка **«Запустить загрузку»** открывает окно:
  биржа, дата начала, дата окончания, «перезагрузить уже загруженные». Загрузка идёт в фоне,
  страница сама обновляется, пока она не закончится.
- Кнопка **«Скачать Excel»** на странице сделок выгружает текущую выборку с фильтрами и сортировкой в .xlsx.

## API

| Запрос | Ответ |
|---|---|
| `GET /api/trades` | `items`, `total`, `page`, `per_page`, `pages`, `summary` |
| `GET /api/status` | состояние данных по биржам |
| `GET /api/trades/export` | xlsx-файл; те же параметры, что у `/api/trades` |
| `GET /api/analytics` | данные для графиков; параметры фильтров как у `/api/trades` |
| `POST /api/parse` | запуск загрузки в фоне: `{"exchange": "all|ets|ccx", "date_from", "date_to", "full"}` |
| `GET /api/health` | `{"status": "ok"}` |

Параметры `/api/trades`: `page`, `per_page` (до 500), `sort` (`trade_date`, `amount`, `price_avg`, `volume`),
`order` (`asc`/`desc`), `exchange` (`ets`/`ccx`), `date_from`, `date_to` (`ГГГГ-ММ-ДД`), `good`, `participant`,
`broker`, `amount_from`, `amount_to`, `delivery`.

## Разработка без Docker

PostgreSQL можно оставить в Docker: `docker compose up -d db`.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FLASK_APP = "run.py"
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5433/postgres"
flask db upgrade
flask seed
flask run --port 4000
```

```bash
cd frontend
npm install
npm run dev
```

Фронт в режиме разработки — http://localhost:3000, запросы `/api` проксируются на `localhost:4000`.

Изменение схемы БД: поменять `app/models.py` → `flask db migrate -m "описание"` (локально) →
проверить созданный файл в `migrations/versions/` → `flask db upgrade`.

## Дамп базы

В репозитории лежит дамп с собранными данными: [docs/dump.sql](docs/dump.sql)
(ETS 4 278 записей, Каспий 6 062 записи).

Загрузить его вместо парсинга (на пустую базу, до `docker compose up` бэкенда):

```bash
docker compose up -d db
docker compose exec -T db psql -U postgres postgres < docs/dump.sql
docker compose up -d --build
```

Сделать свежий дамп:

```bash
docker compose exec db pg_dump -U postgres --no-owner postgres > docs/dump.sql
```

## Документация

- [docs/PROBLEMS.md](docs/PROBLEMS.md) — особенности источников, отсутствующие поля, проблемы и принятые решения, ограничения
- [docs/GUIDE.md](docs/GUIDE.md) — как запустить и как устроен проект: каждая функция по разделам
- [docs/REPORT.md](docs/REPORT.md) — краткий отчёт по практике

## Структура базы данных

```
exchanges      биржи (ETS, Каспий)
goods          товары: название рус/каз, код товара ETS, ТН ВЭД, единица
participants   продавцы и покупатели: название, БИН
brokers        брокеры
trades         сделки: дата, биржа, товар, продавец, покупатель, брокеры,
               количество сделок, цены, сумма, объём, условие поставки, dedup_hash
trading_days   какие дни по какой бирже загружены и со статусом
parser_runs    журнал запусков парсеров
```

`trades` ссылается на все справочники. Уникальный `dedup_hash` защищает от повторной записи одной строки.
Индексы — по полям фильтров: дата, биржа+дата, сумма, товар, продавец, покупатель, брокеры.

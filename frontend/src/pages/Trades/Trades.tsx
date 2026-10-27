import { useEffect, useState } from 'react'
import { EMPTY_FILTERS, exportUrl, getTrades, type Filters, type TradesPage, type TradesQuery } from '../../api/trades'
import FiltersPanel from '../../components/FiltersPanel'
import Pager from '../../components/Pager'

const money = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 })
const formatMoney = (value: number | null) => (value != null ? money.format(value) : '—')

const SORTABLE: Record<string, string> = {
  trade_date: 'Дата торгов',
  volume: 'Объём',
  price_avg: 'Цена за ед.',
  amount: 'Сумма сделки',
}

const PER_PAGE_OPTIONS = [25, 50, 100, 200]

export default function Trades() {
  const [query, setQuery] = useState<TradesQuery>({
    ...EMPTY_FILTERS,
    page: 1,
    per_page: 50,
    sort: 'trade_date',
    order: 'desc',
  })
  const [data, setData] = useState<TradesPage | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError('')
    getTrades(query)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [query])

  const applyFilters = (filters: Filters) => setQuery((q) => ({ ...q, ...filters, page: 1 }))

  const sortBy = (column: string) =>
    setQuery((q) => ({
      ...q,
      page: 1,
      sort: column,
      order: q.sort === column && q.order === 'desc' ? 'asc' : 'desc',
    }))

  const header = (column: string) => (
    <th className="sortable" onClick={() => sortBy(column)}>
      {SORTABLE[column]}
      {query.sort === column ? (query.order === 'desc' ? ' ↓' : ' ↑') : ''}
    </th>
  )

  const summary = data?.summary

  return (
    <>
      <h1>Итоги торгов</h1>
      <FiltersPanel value={query} onApply={applyFilters} />

      {error && <p className="error">{error}</p>}

      <div className="table-top">
        <span>Найдено: {data ? data.total.toLocaleString('ru-RU') : '…'} сделок</span>
        <a className="button-link" href={exportUrl(query)} download>Скачать Excel</a>
        <label className="inline">
          Записей на странице
          <select
            value={query.per_page}
            onChange={(e) => setQuery((q) => ({ ...q, per_page: Number(e.target.value), page: 1 }))}
          >
            {PER_PAGE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>

      <div className="table-wrap">
        <table className={loading ? 'loading' : ''}>
          <thead>
            <tr>
              {header('trade_date')}
              <th>Биржа</th>
              <th>Брокер продавца / покупателя</th>
              <th>Товар</th>
              <th>Продавец</th>
              <th>Покупатель</th>
              {header('volume')}
              {header('price_avg')}
              {header('amount')}
              <th>Условие поставки</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((t) => (
              <tr key={t.id}>
                <td>{new Date(t.trade_date).toLocaleDateString('ru-RU')}</td>
                <td>{t.exchange}</td>
                <td>{t.seller_broker ?? '—'} / {t.buyer_broker ?? '—'}</td>
                <td className="good" title={t.good}>
                  {t.good}
                  {t.tnved && <div className="muted">ТН ВЭД {t.tnved}</div>}
                </td>
                <td>{t.seller ?? '—'}<div className="muted">{t.seller_bin}</div></td>
                <td>{t.buyer ?? '—'}<div className="muted">{t.buyer_bin}</div></td>
                <td className="num">{t.volume != null ? `${money.format(t.volume)} ${t.unit ?? ''}` : '—'}</td>
                <td className="num">{formatMoney(t.price_avg)}</td>
                <td className="num">{formatMoney(t.amount)}</td>
                <td>{t.delivery_terms ?? '—'}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={10} className="empty">Ничего не найдено</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && (
        <Pager page={data.page} pages={data.pages} onChange={(page) => setQuery((q) => ({ ...q, page }))} />
      )}

      {summary && (
        <>
          <h2>Сводка по выборке</h2>
          <table className="summary">
            <thead>
              <tr>
                <th></th>
                <th>Сделок</th>
                <th>Сумма, тг</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_exchange.map((e) => (
                <tr key={e.exchange}>
                  <td>{e.exchange}</td>
                  <td className="num">{e.trades.toLocaleString('ru-RU')}</td>
                  <td className="num">{formatMoney(e.amount)}</td>
                </tr>
              ))}
              <tr>
                <th>Всего</th>
                <th className="num">{summary.trades.toLocaleString('ru-RU')}</th>
                <th className="num">{formatMoney(summary.amount)}</th>
              </tr>
            </tbody>
          </table>
          <p>Товаров в выборке: {summary.goods.toLocaleString('ru-RU')}</p>
        </>
      )}
    </>
  )
}

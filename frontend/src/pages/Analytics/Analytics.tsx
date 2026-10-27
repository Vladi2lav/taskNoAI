import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { EMPTY_FILTERS, getAnalytics, type Analytics as AnalyticsData, type Filters, type TopParticipant } from '../../api/trades'
import FiltersPanel from '../../components/FiltersPanel'

const COLORS = { ETS: '#1f4e79', 'Каспий': '#c0792b' }

const compact = new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 })
const full = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const formatTooltip = (value: number) => full.format(value)

function ShareBar({ value, max }: { value: number; max: number }) {
  return <div className="share-bar" style={{ width: `${Math.max((value / max) * 100, 1)}%` }} />
}

function TopParticipants({ title, rows }: { title: string; rows: TopParticipant[] }) {
  const max = rows[0]?.amount ?? 1
  return (
    <div>
      <h3>{title}</h3>
      <table>
        <thead>
          <tr><th>Участник</th><th>Сделок</th><th>Сумма, тг</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.name}-${row.bin}`}>
              <td>
                {row.name}
                {row.bin && <div className="muted">{row.bin}</div>}
                <ShareBar value={row.amount} max={max} />
              </td>
              <td className="num">{full.format(row.trades)}</td>
              <td className="num">{full.format(row.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Analytics() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    getAnalytics(filters).then(setData).catch((e: Error) => setError(e.message))
  }, [filters])

  const exchanges = data
    ? (Object.keys(COLORS) as (keyof typeof COLORS)[]).filter((name) => data.turnover.some((row) => name in row))
    : []
  const maxGood = data?.top_goods[0]?.amount ?? 1

  return (
    <>
      <h1>Аналитика</h1>
      <FiltersPanel value={filters} onApply={setFilters} />
      {error && <p className="error">{error}</p>}

      {data && (
        <>
          <h2>Оборот по месяцам, тг</h2>
          <div className="chart">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.turnover}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" />
                <YAxis tickFormatter={(v) => compact.format(v)} width={70} />
                <Tooltip formatter={formatTooltip} />
                <Legend />
                {exchanges.map((name) => (
                  <Bar key={name} dataKey={name} stackId="turnover" fill={COLORS[name]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          <h2>Динамика цены за единицу, тг</h2>
          <p className="muted">
            Средневзвешенная цена за месяц (сумма / объём). Имеет смысл для одного товара —
            выберите его в фильтре «Товар или код ТН ВЭД».
          </p>
          <div className="chart">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.prices}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" />
                <YAxis tickFormatter={(v) => compact.format(v)} width={70} />
                <Tooltip formatter={formatTooltip} />
                <Legend />
                <Line dataKey="avg" name="Средняя" stroke="#1f4e79" strokeWidth={2} dot={false} />
                <Line dataKey="min" name="Минимум" stroke="#8fa9c4" strokeDasharray="4 4" dot={false} />
                <Line dataKey="max" name="Максимум" stroke="#c0792b" strokeDasharray="4 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <h2>Топ-10 товаров по сумме сделок</h2>
          <table>
            <thead>
              <tr><th>Товар</th><th>Сделок</th><th>Объём</th><th>Сумма, тг</th></tr>
            </thead>
            <tbody>
              {data.top_goods.map((good) => (
                <tr key={good.name}>
                  <td className="good">
                    {good.name}
                    <ShareBar value={good.amount} max={maxGood} />
                  </td>
                  <td className="num">{full.format(good.trades)}</td>
                  <td className="num">{good.volume != null ? `${full.format(good.volume)} ${good.unit ?? ''}` : '—'}</td>
                  <td className="num">{full.format(good.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="two-columns">
            <TopParticipants title="Топ-10 продавцов" rows={data.top_sellers} />
            <TopParticipants title="Топ-10 покупателей" rows={data.top_buyers} />
          </div>
        </>
      )}
    </>
  )
}

export type Trade = {
  id: number
  trade_date: string
  exchange: string
  good: string
  tnved: string | null
  unit: string | null
  seller: string | null
  seller_bin: string | null
  buyer: string | null
  buyer_bin: string | null
  seller_broker: string | null
  buyer_broker: string | null
  deals_count: number | null
  price_avg: number | null
  amount: number | null
  volume: number | null
  delivery_terms: string | null
}

export type Summary = {
  trades: number
  amount: number | null
  goods: number
  by_exchange: { exchange: string; trades: number; amount: number | null }[]
}

export type TradesPage = {
  items: Trade[]
  total: number
  page: number
  per_page: number
  pages: number
  summary: Summary
}

export type ParserRun = {
  id: number
  exchange: string
  trigger: string
  status: string
  started_at: string
  finished_at: string | null
  added: number
  skipped: number
  error_message: string | null
}

export type ExchangeStatus = {
  exchange: string
  trades_count: number
  first_trade_date: string | null
  last_trade_date: string | null
  last_update: string | null
  days_loaded: number
  days_error: number
  last_run: ParserRun | null
}

export type DataStatus = {
  exchanges: ExchangeStatus[]
  total_trades: number
  runs: ParserRun[]
}

export type Filters = {
  exchange: string
  date_from: string
  date_to: string
  good: string
  participant: string
  broker: string
  amount_from: string
  amount_to: string
  delivery: string
}

export const EMPTY_FILTERS: Filters = {
  exchange: '',
  date_from: '',
  date_to: '',
  good: '',
  participant: '',
  broker: '',
  amount_from: '',
  amount_to: '',
  delivery: '',
}

export type TradesQuery = Filters & {
  page: number
  per_page: number
  sort: string
  order: 'asc' | 'desc'
}

export type Analytics = {
  turnover: Record<string, string | number>[]
  prices: { month: string; avg: number | null; min: number | null; max: number | null }[]
  top_goods: { name: string; unit: string | null; amount: number; volume: number | null; trades: number }[]
  top_sellers: TopParticipant[]
  top_buyers: TopParticipant[]
}

export type TopParticipant = { name: string; bin: string | null; amount: number; trades: number }

export type ParseRequest = {
  exchange: string
  date_from: string
  date_to: string
  full: boolean
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.message || `Ошибка ${res.status}`)
  return data as T
}

function toParams(values: Record<string, string | number>) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== '') params.set(key, String(value))
  }
  return params
}

export const getTrades = (query: TradesQuery) => request<TradesPage>(`/api/trades?${toParams(query)}`)

export const exportUrl = (query: TradesQuery) => `/api/trades/export?${toParams(query)}`

export const getAnalytics = (filters: Filters) => request<Analytics>(`/api/analytics?${toParams(filters)}`)

export const getStatus = () => request<DataStatus>('/api/status')

export const startParse = (body: ParseRequest) =>
  request<{ message: string }>('/api/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

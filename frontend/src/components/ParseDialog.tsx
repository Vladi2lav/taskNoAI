import { useState, type FormEvent } from 'react'
import { startParse, type ParseRequest } from '../api/trades'

type Props = {
  onClose: () => void
  onStarted: () => void
}

const daysAgo = (days: number) => {
  const d = new Date()
  d.setDate(d.getDate() - days)
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${month}-${day}`
}

export default function ParseDialog({ onClose, onStarted }: Props) {
  const [form, setForm] = useState<ParseRequest>({
    exchange: 'all',
    date_from: daysAgo(7),
    date_to: daysAgo(0),
    full: false,
  })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSending(true)
    try {
      await startParse(form)
      onStarted()
      onClose()
    } catch (err) {
      setError((err as Error).message)
      setSending(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onSubmit={submit} onClick={(e) => e.stopPropagation()}>
        <h2>Запуск загрузки</h2>

        <label>
          Биржа
          <select value={form.exchange} onChange={(e) => setForm({ ...form, exchange: e.target.value })}>
            <option value="all">Обе</option>
            <option value="ets">ETS</option>
            <option value="ccx">Каспий</option>
          </select>
        </label>

        <div className="modal-row">
          <label>
            Дата начала
            <input type="date" value={form.date_from} max={form.date_to || undefined}
              onChange={(e) => setForm({ ...form, date_from: e.target.value })} />
          </label>
          <label>
            Дата окончания
            <input type="date" value={form.date_to} min={form.date_from || undefined}
              onChange={(e) => setForm({ ...form, date_to: e.target.value })} />
          </label>
        </div>

        <label className="checkbox">
          <input type="checkbox" checked={form.full}
            onChange={(e) => setForm({ ...form, full: e.target.checked })} />
          Перезагрузить уже загруженные дни
        </label>

        <p className="muted">
          Пустые даты — вся история. Без галочки загружаются только новые дни
          и последние дни для проверки исправлений. Загрузка идёт в фоне, ход — в журнале запусков.
        </p>

        {error && <p className="error">{error}</p>}

        <div className="modal-buttons">
          <button type="button" onClick={onClose}>Отмена</button>
          <button type="submit" disabled={sending}>{sending ? 'Запуск…' : 'Запустить'}</button>
        </div>
      </form>
    </div>
  )
}

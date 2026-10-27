import { useState, type FormEvent } from 'react'
import { EMPTY_FILTERS, type Filters } from '../api/trades'

type Props = {
  value: Filters
  onApply: (filters: Filters) => void
}

export default function FiltersPanel({ value, onApply }: Props) {
  const [draft, setDraft] = useState<Filters>(value)

  const set = (key: keyof Filters) => (e: { target: { value: string } }) =>
    setDraft({ ...draft, [key]: e.target.value })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    onApply(draft)
  }

  const reset = () => {
    setDraft(EMPTY_FILTERS)
    onApply(EMPTY_FILTERS)
  }

  return (
    <form className="filters" onSubmit={submit}>
      <label>
        Биржа
        <select value={draft.exchange} onChange={set('exchange')}>
          <option value="">Обе</option>
          <option value="ets">ETS</option>
          <option value="ccx">Каспий</option>
        </select>
      </label>

      <label>
        Период с
        <input type="date" value={draft.date_from} onChange={set('date_from')} />
      </label>
      <label>
        по
        <input type="date" value={draft.date_to} onChange={set('date_to')} />
      </label>

      <label className="wide">
        Товар или код ТН ВЭД
        <input value={draft.good} onChange={set('good')} placeholder="уголь, 1701…" />
      </label>

      <label className="wide">
        Продавец или покупатель
        <input value={draft.participant} onChange={set('participant')} placeholder="название или БИН" />
      </label>

      <label>
        Брокер
        <input value={draft.broker} onChange={set('broker')} />
      </label>

      <label>
        Сумма от
        <input type="number" min="0" value={draft.amount_from} onChange={set('amount_from')} />
      </label>
      <label>
        до
        <input type="number" min="0" value={draft.amount_to} onChange={set('amount_to')} />
      </label>

      <label>
        Место поставки
        <input value={draft.delivery} onChange={set('delivery')} placeholder="EXW, FCA, станция…" />
      </label>

      <div className="filters-buttons">
        <button type="submit">Применить</button>
        <button type="button" onClick={reset}>Сбросить</button>
      </div>
    </form>
  )
}

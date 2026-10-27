import { useCallback, useEffect, useState } from 'react'
import { getStatus, type DataStatus, type ParserRun } from '../../api/trades'
import ParseDialog from '../../components/ParseDialog'

const STATUS_TEXT: Record<string, string> = {
  running: 'выполняется',
  success: 'успешно',
  error: 'с ошибками',
}

const TRIGGER_TEXT: Record<string, string> = {
  manual: 'вручную',
  schedule: 'по расписанию',
}

const formatDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('ru-RU') : '—')
const formatDateTime = (iso: string | null) => (iso ? new Date(iso).toLocaleString('ru-RU') : '—')
const formatNumber = (value: number) => value.toLocaleString('ru-RU')

function RunStatus({ run }: { run: ParserRun }) {
  const className = run.status === 'error' ? 'status-error' : run.status === 'success' ? 'status-ok' : ''
  return <span className={className}>{STATUS_TEXT[run.status] ?? run.status}</span>
}

export default function Status() {
  const [data, setData] = useState<DataStatus | null>(null)
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)

  const load = useCallback(() => {
    getStatus().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  const running = data?.runs.some((run) => run.status === 'running') ?? false

  useEffect(load, [load])

  useEffect(() => {
    if (!running) return
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [running, load])

  if (error) return <p className="error">{error}</p>
  if (!data) return <p>Загрузка…</p>

  return (
    <>
      <div className="page-head">
        <h1>Состояние данных</h1>
        <button onClick={() => setDialogOpen(true)} disabled={running}>
          {running ? 'Идёт загрузка…' : 'Запустить загрузку'}
        </button>
      </div>

      {dialogOpen && <ParseDialog onClose={() => setDialogOpen(false)} onStarted={() => setTimeout(load, 1000)} />}

      <table>
        <thead>
          <tr>
            <th>Биржа</th>
            <th>Записей</th>
            <th>Период данных</th>
            <th>Последнее обновление</th>
            <th>Загружено дней</th>
            <th>Дней с ошибкой</th>
            <th>Последний запуск</th>
          </tr>
        </thead>
        <tbody>
          {data.exchanges.map((e) => (
            <tr key={e.exchange}>
              <td>{e.exchange}</td>
              <td className="num">{formatNumber(e.trades_count)}</td>
              <td>{formatDate(e.first_trade_date)} — {formatDate(e.last_trade_date)}</td>
              <td>{formatDateTime(e.last_update)}</td>
              <td className="num">{formatNumber(e.days_loaded)}</td>
              <td className={`num ${e.days_error ? 'status-error' : ''}`}>{formatNumber(e.days_error)}</td>
              <td>
                {e.last_run ? (
                  <>
                    <RunStatus run={e.last_run} />, {formatDateTime(e.last_run.started_at)},
                    добавлено {formatNumber(e.last_run.added)}
                    {e.last_run.error_message && <pre className="error">{e.last_run.error_message}</pre>}
                  </>
                ) : 'не запускался'}
              </td>
            </tr>
          ))}
          <tr>
            <th>Всего</th>
            <th className="num">{formatNumber(data.total_trades)}</th>
            <th colSpan={5}></th>
          </tr>
        </tbody>
      </table>

      <h2>Журнал запусков</h2>
      <table>
        <thead>
          <tr>
            <th>Начало</th>
            <th>Окончание</th>
            <th>Биржа</th>
            <th>Запуск</th>
            <th>Результат</th>
            <th>Добавлено</th>
            <th>Без изменений</th>
            <th>Ошибки</th>
          </tr>
        </thead>
        <tbody>
          {data.runs.map((run) => (
            <tr key={run.id}>
              <td>{formatDateTime(run.started_at)}</td>
              <td>{formatDateTime(run.finished_at)}</td>
              <td>{run.exchange}</td>
              <td>{TRIGGER_TEXT[run.trigger] ?? run.trigger}</td>
              <td><RunStatus run={run} /></td>
              <td className="num">{formatNumber(run.added)}</td>
              <td className="num">{formatNumber(run.skipped)}</td>
              <td>
                {run.error_message && (
                  <details>
                    <summary className="error">Ошибок: {run.error_message.split('\n').length}</summary>
                    <pre className="error">{run.error_message}</pre>
                  </details>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

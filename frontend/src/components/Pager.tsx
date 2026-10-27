type Props = {
  page: number
  pages: number
  onChange: (page: number) => void
}

function visiblePages(page: number, pages: number): (number | '…')[] {
  const result: (number | '…')[] = []
  for (let p = 1; p <= pages; p++) {
    if (p === 1 || p === pages || Math.abs(p - page) <= 2) {
      result.push(p)
    } else if (result[result.length - 1] !== '…') {
      result.push('…')
    }
  }
  return result
}

export default function Pager({ page, pages, onChange }: Props) {
  if (pages <= 1) return null

  return (
    <div className="pager">
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>‹</button>
      {visiblePages(page, pages).map((p, i) =>
        p === '…' ? (
          <span key={`gap-${i}`}>…</span>
        ) : (
          <button key={p} className={p === page ? 'current' : ''} onClick={() => onChange(p)}>
            {p}
          </button>
        ),
      )}
      <button disabled={page >= pages} onClick={() => onChange(page + 1)}>›</button>
      <span className="muted">Стр. {page} из {pages}</span>
    </div>
  )
}

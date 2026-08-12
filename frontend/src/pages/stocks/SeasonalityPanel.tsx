import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { seasonalityApi } from '@/lib/api/seasonality'
import { Skeleton, SkeletonTable } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { formatChange, formatPct } from '@/lib/format'

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

/** A month with fewer than this many yearly observations is statistically thin:
 *  its return columns are de-emphasised and marked, so a 1–4 year sample can't
 *  read as a reliable edge (ui.md — data colour must reflect reliability). */
const THIN_YEARS = 5

function monthLabel(iso: string | null): string {
  if (!iso) return '—'
  const [y, m] = iso.split('-')
  return `${MONTHS[Number(m) - 1]} ${y}`
}

/** Colour a signed value by its own sign. Thin-sample cells are forced to the
 *  muted token so a low-year cell never renders as a confident profit/loss;
 *  direction still comes from the +/- glyph, never colour alone (ui.md §5.2). */
function signColor(v: number | null, thin: boolean): string | undefined {
  if (thin || v === null || v === 0) return 'var(--color-text-muted)'
  return v > 0 ? 'var(--color-profit)' : 'var(--color-loss)'
}

export function SeasonalityPanel({ stockId }: { stockId: number }) {
  const { accessToken } = useAuth()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['seasonality', stockId],
    queryFn: () => seasonalityApi.get(stockId, accessToken!),
    enabled: !!accessToken && !!stockId,
  })

  if (isLoading) {
    return (
      <div className="card space-y-3">
        <Skeleton className="h-5 w-64" />
        <SkeletonTable rows={12} cols={6} />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <EmptyState
        title="Couldn't load seasonality"
        description="There was a problem computing the monthly return history."
        action={
          <Button variant="ghost" size="sm" onClick={() => void refetch()}>
            Retry
          </Button>
        }
      />
    )
  }

  if (data.total_observations === 0) {
    return (
      <EmptyState
        title="Not enough history"
        description="Seasonality needs at least two consecutive month-end closes. None are ingested for this stock yet."
      />
    )
  }

  const hasThin = data.months.some((mo) => mo.n > 0 && mo.n < THIN_YEARS)

  return (
    <div className="card">
      <div className="mb-3">
        <p className="text-sm text-(--color-text)">
          Monthly return bias — {data.total_observations} monthly returns across{' '}
          {data.years_covered} year{data.years_covered === 1 ? '' : 's'} ({monthLabel(data.first_month)} – {monthLabel(data.last_month)}).
        </p>
        <p className="text-xs text-(--color-text-muted) mt-0.5">
          Context only — a seasonal tilt is a soft modifier, never a signal.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr className="border-b border-(--color-border) bg-(--color-surface-2)">
              {['Month', 'Yrs', '% Up', 'Avg', 'Best', 'Worst'].map((h, i) => (
                <th
                  key={h}
                  className={`px-3 py-2 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) ${
                    i === 0 ? 'text-left' : 'text-right'
                  }`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.months.map((mo) => {
              const thin = mo.n > 0 && mo.n < THIN_YEARS
              return (
                <tr
                  key={mo.month}
                  data-thin={thin || undefined}
                  className="border-b border-(--color-border) hover:bg-(--color-surface-hover)"
                >
                  <td className="px-3 py-2 text-(--color-text) font-medium">{MONTHS[mo.month - 1]}</td>
                  {mo.n === 0 ? (
                    <td className="px-3 py-2 text-right text-(--color-text-muted)" colSpan={5}>
                      no data
                    </td>
                  ) : (
                    <>
                      <td className="px-3 py-2 text-right tabular-nums text-(--color-text-muted)">
                        {mo.n}
                        {thin && (
                          <>
                            <sup aria-hidden="true" className="ml-0.5">*</sup>
                            <span className="sr-only"> (thin sample — not tradeable)</span>
                          </>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-(--color-text)">
                        {formatPct(mo.pct_positive ?? 0, { signed: false })}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums font-medium" style={{ color: signColor(mo.avg_return_pct, thin) }}>
                        {formatChange(mo.avg_return_pct ?? 0)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums" style={{ color: signColor(mo.best_return_pct, thin) }}>
                        {formatChange(mo.best_return_pct ?? 0)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums" style={{ color: signColor(mo.worst_return_pct, thin) }}>
                        {formatChange(mo.worst_return_pct ?? 0)}
                      </td>
                    </>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {hasThin && (
        <p className="text-xs text-(--color-text-muted) mt-2">
          <span aria-hidden="true">*</span> Fewer than {THIN_YEARS} years of data — treat as noise, not a tradeable edge.
        </p>
      )}
    </div>
  )
}

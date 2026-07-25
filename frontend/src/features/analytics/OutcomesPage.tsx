import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { analyticsApi, type OutcomeStyleStats } from '@/lib/api/analytics'
import { PageHeader } from '@/components/layout/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { formatPct } from '@/lib/format'

const STYLE_LABEL: Record<string, string> = {
  intraday: 'Intraday', swing: 'Swing', fno: 'F&O', investment: 'Investment',
}

function OutcomeCard({ s }: { s: OutcomeStyleStats }) {
  const hitColor = s.hit_rate == null
    ? 'var(--color-text-muted)'
    : s.hit_rate >= 0.5 ? 'var(--color-bull)' : 'var(--color-bear)'
  const expColor = s.avg_return_pct == null
    ? 'var(--color-text-muted)'
    : s.avg_return_pct >= 0 ? 'var(--color-bull)' : 'var(--color-bear)'
  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-(--color-text)">{STYLE_LABEL[s.style] ?? s.style}</span>
        <span className="text-[10px] text-(--color-text-muted)">n={s.sample}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-xl font-bold font-mono tabular-nums" style={{ color: hitColor }}>
            {s.hit_rate == null ? '—' : formatPct(s.hit_rate * 100, { signed: false })}
          </div>
          <div className="text-[10px] text-(--color-text-muted) uppercase tracking-wide">Hit rate</div>
        </div>
        <div>
          <div className="text-xl font-bold font-mono tabular-nums" style={{ color: expColor }}>
            {s.avg_return_pct == null ? '—' : formatPct(s.avg_return_pct)}
          </div>
          <div className="text-[10px] text-(--color-text-muted) uppercase tracking-wide">Expectancy</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] tabular-nums">
        <span style={{ color: 'var(--color-bull)' }}>{s.wins} win</span>
        <span style={{ color: 'var(--color-bear)' }}>{s.losses} loss</span>
        <span className="text-(--color-text-muted)">{s.no_entry} no-entry</span>
        <span className="text-(--color-text-muted)">{s.timed_out} timed-out</span>
        <span className="text-(--color-text-muted)">{s.pending} pending</span>
      </div>
    </div>
  )
}

export function OutcomesPage() {
  const { accessToken } = useAuth()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['outcome-analytics'],
    queryFn: () => analyticsApi.getOutcomes(accessToken!),
    enabled: !!accessToken,
    staleTime: 60_000,
  })

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Outcome analytics"
        subtitle="Per-style hit-rate & expectancy from recorded signal outcomes — observability only, never feeds scoring or sizing."
      />

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3" aria-label="loading analytics">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32 w-full" />)}
        </div>
      )}

      {isError && (
        <div className="p-4 text-sm text-(--color-text-muted) bg-(--color-surface-2) border border-(--color-border) rounded-lg">
          Could not load outcome analytics.{' '}
          <Button variant="link" size="sm" onClick={() => void refetch()}>Retry</Button>
        </div>
      )}

      {data && (
        <>
          {data.total_outcomes === 0 && (
            <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 text-sm text-(--color-text-muted)">
              No signal outcomes recorded yet — hit-rates accrue from live trading days
              (since the 2026-07-19 outcome epoch). The grid below populates as tick-level
              first-touch outcomes land.
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.styles.map((s) => <OutcomeCard key={s.style} s={s} />)}
          </div>
        </>
      )}
    </div>
  )
}

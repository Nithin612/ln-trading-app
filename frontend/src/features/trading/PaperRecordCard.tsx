import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Flame, Trophy, CalendarCheck, RotateCcw } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi } from '@/lib/api/trading'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatPct } from '@/lib/format'

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: 'bull' | 'bear' }) {
  const color =
    tone === 'bull' ? 'var(--color-bull)' : tone === 'bear' ? 'var(--color-bear)' : 'var(--color-text)'
  return (
    <div>
      <div className="text-lg font-bold font-mono tabular-nums" style={{ color }}>{value}</div>
      <div className="text-[10px] text-(--color-text-muted) uppercase tracking-wide mt-0.5">{label}</div>
    </div>
  )
}

export function PaperRecordCard() {
  const { accessToken } = useAuth()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['paper-record'],
    queryFn: () => tradingApi.getPaperRecord(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 60_000,
  })

  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const resetMutation = useMutation({
    mutationFn: () => tradingApi.resetPaperClock(accessToken!),
    onSuccess: (fresh) => {
      queryClient.setQueryData(['paper-record'], fresh)
      setConfirming(false)
    },
  })

  if (isLoading) return <Skeleton className="h-40 w-full rounded-lg" />

  if (isError) {
    return (
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 text-sm text-(--color-text-muted)">
        Could not load the paper record.{' '}
        <Button variant="link" size="sm" onClick={() => void refetch()}>Retry</Button>
      </div>
    )
  }

  if (!data) return null

  // clock_started_at is a raw instant; render it in IST to match the card's
  // other dates (start_date / day rows are all IST YYYY-MM-DD).
  const countingSince = data.clock_started_at
    ? new Date(data.clock_started_at).toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })
    : null

  const total = parseFloat(data.total_realized_pnl)
  const progressPct = Math.min(100, (data.profitable_days / data.target_days) * 100)

  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <CalendarCheck size={14} style={{ color: 'var(--color-text-muted)' }} />
          <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Paper Record
          </span>
        </div>
        <span className="text-[10px] text-(--color-text-muted)">net of costs</span>
      </div>

      {data.total_days_traded === 0 ? (
        <p className="text-sm text-(--color-text-muted) py-4">
          No closed paper trades yet — the 30-day clock starts when you close your first trade.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3 mb-3">
            <Stat
              label="Net P&L"
              value={`${total >= 0 ? '+' : ''}${formatCurrency(total)}`}
              tone={total >= 0 ? 'bull' : 'bear'}
            />
            <Stat
              label="Profit days"
              value={`${data.profitable_days}/${data.target_days}`}
            />
            <Stat
              label="Streak"
              value={<span className="inline-flex items-center gap-1"><Flame size={13} />{data.current_streak}</span>}
              tone={data.current_streak > 0 ? 'bull' : undefined}
            />
            <Stat label="Win rate" value={formatPct(parseFloat(data.win_rate_pct), { signed: false })} />
          </div>

          {/* Progress toward the 30 profitable-day target */}
          <div className="mb-3">
            <div className="flex justify-between text-[10px] text-(--color-text-muted) mb-1">
              <span>Toward 30 profitable days</span>
              <span className="inline-flex items-center gap-1">
                <Trophy size={10} /> best {data.best_streak}
              </span>
            </div>
            <div className="h-1.5 bg-(--color-surface-3) rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all"
                style={{ width: `${progressPct}%`, background: 'var(--color-bull)' }} />
            </div>
          </div>

          {/* Per-day strip (oldest → newest): ▲ up day, ▼ down day — glyph + colour,
              never colour alone (UI_GUIDELINES §5.2). */}
          <div className="flex items-center gap-px overflow-x-auto" title="Daily result — ▲ up day, ▼ down day (oldest to newest)">
            {data.days.map((d) => (
              <span
                key={d.date}
                className="shrink-0 w-2.5 text-center text-[10px] leading-none font-bold"
                title={`${d.date}: ${parseFloat(d.realized_pnl) >= 0 ? '+' : ''}${formatCurrency(parseFloat(d.realized_pnl))} (${d.trades} trade${d.trades !== 1 ? 's' : ''})`}
                style={{ color: d.profitable ? 'var(--color-bull)' : 'var(--color-bear)' }}
              >
                {d.profitable ? '▲' : '▼'}
              </span>
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-(--color-text-muted) mt-2">
            <span>{data.total_days_traded} trading days · {data.total_trades} trades</span>
            <span>costs {formatCurrency(parseFloat(data.total_charges))}</span>
          </div>
        </>
      )}

      {/* Clock reset — restart the 30-day count under the current fill model.
          Two-step confirm; past trades stay in the DB, they just stop counting. */}
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-(--color-border)">
        <span className="text-[10px] text-(--color-text-muted)">
          {countingSince ? `counting since ${countingSince}` : 'counting all paper history'}
        </span>
        {confirming ? (
          <span className="inline-flex items-center gap-2">
            <span className="text-[10px] text-(--color-text-muted)">Restart the 30-day clock?</span>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={resetMutation.isPending}
              onClick={() => resetMutation.mutate()}
            >
              {resetMutation.isPending ? 'Resetting…' : 'Confirm reset'}
            </Button>
          </span>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 text-(--color-text-muted)"
            onClick={() => setConfirming(true)}
          >
            <RotateCcw size={12} /> Reset clock
          </Button>
        )}
      </div>
    </div>
  )
}

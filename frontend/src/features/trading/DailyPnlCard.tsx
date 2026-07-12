import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi } from '@/lib/api/trading'
import { Skeleton } from '@/components/ui/skeleton'

function fmt(val: string): string {
  const n = parseFloat(val)
  const sign = n >= 0 ? '+' : '-'
  return `${sign}₹${Math.abs(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function DailyPnlCard() {
  const { accessToken } = useAuth()

  const { data, isLoading } = useQuery({
    queryKey: ['daily-pnl'],
    queryFn: () => tradingApi.getDailyPnl(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 60_000,
  })

  if (isLoading) return <Skeleton className="h-24 w-full rounded-lg" />

  if (!data) return null

  const pnl = parseFloat(data.realized_pnl)
  const limit = parseFloat(data.daily_loss_limit_inr)
  const usedPct = limit > 0 ? Math.min(100, (Math.abs(Math.min(0, pnl)) / limit) * 100) : 0

  return (
    <div
      className="bg-(--color-surface-2) border rounded-lg p-4"
      style={{ borderColor: data.circuit_breaker_triggered ? 'var(--color-bear)' : 'var(--color-border)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp size={14} style={{ color: 'var(--color-text-muted)' }} />
          <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Today's P&amp;L
          </span>
        </div>
        {data.circuit_breaker_triggered ? (
          <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full"
            style={{ background: 'rgba(220,38,38,0.15)', color: 'var(--color-bear)' }}>
            <AlertTriangle size={10} /> BREAKER ON
          </span>
        ) : (
          <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full"
            style={{ background: 'rgba(22,163,74,0.12)', color: 'var(--color-bull)' }}>
            <CheckCircle size={10} /> OK
          </span>
        )}
      </div>

      <div className="text-xl font-bold font-mono mb-2"
        style={{ color: pnl >= 0 ? 'var(--color-bull)' : 'var(--color-bear)' }}>
        {fmt(data.realized_pnl)}
      </div>

      {/* Loss limit bar */}
      <div className="mb-2">
        <div className="flex justify-between text-[10px] text-(--color-text-muted) mb-1">
          <span>Loss used</span>
          <span>{usedPct.toFixed(0)}% of ₹{limit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
        </div>
        <div className="h-1.5 bg-(--color-surface-3) rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${usedPct}%`,
              background: usedPct >= 90 ? 'var(--color-bear)' : usedPct >= 70 ? '#f59e0b' : 'var(--color-bull)',
            }}
          />
        </div>
      </div>

      <div className="flex justify-between text-[10px] text-(--color-text-muted)">
        <span>{data.open_count} open · {data.closed_count} closed</span>
        <span>{data.trades_taken_today}/{data.max_trades_per_day} trades</span>
      </div>
    </div>
  )
}

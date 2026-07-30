import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi, type PositionOut, type ShadowComparison } from '@/lib/api/trading'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Pagination } from '@/components/ui/pagination'
import { DailyPnlCard } from './DailyPnlCard'
import { formatINR, formatInt } from '@/lib/format'

const PAGE_SIZE = 20

function pnlCell(val: string): React.ReactNode {
  const n = parseFloat(val)
  const sign = n >= 0 ? '+' : '-'
  return (
    <span style={{ color: n >= 0 ? 'var(--color-bull)' : 'var(--color-bear)', fontWeight: 600 }}>
      {sign}₹{formatINR(Math.abs(n))}
    </span>
  )
}

function priceFmt(val: string | null): string {
  if (!val) return '—'
  return `₹${formatINR(parseFloat(val))}`
}

// sl_hit/tp_hit are auto-closes by the position monitor; manual is a REST
// close by the user. Older rows (pre-migration) have no reason → em dash.
function ExitReason({ reason }: { reason: PositionOut['exit_reason'] }) {
  const map: Record<string, { text: string; auto: boolean }> = {
    sl_hit: { text: 'Stop loss', auto: true },
    tp_hit: { text: 'Target', auto: true },
    manual: { text: 'Manual', auto: false },
  }
  const r = reason ? map[reason] : undefined
  if (!r) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  return (
    <span>
      <span style={{ color: 'var(--color-text)' }}>{r.text}</span>
      <span className="text-(--color-text-muted)"> · {r.auto ? 'auto' : 'manual'}</span>
    </span>
  )
}

function pctFmt(x: number | null): string {
  if (x == null) return '—'
  return `${Math.round(x * 100)}%`
}

// Max favourable excursion (gross) reached while the trade was open. Only
// meaningful when the trade actually went into profit at some point.
function PeakCell({ cmp }: { cmp: ShadowComparison | undefined }) {
  const n = cmp?.peak_gross != null ? parseFloat(cmp.peak_gross) : null
  if (n == null || n <= 0) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  return <span className="font-mono">₹{formatINR(n)}</span>
}

const OFF_TAPE_TITLE =
  'Closed on a stale/pre-open price that never actually traded — this realised ' +
  'P&L is unreliable. See “After-lock” for the real-tape outcome.'

// How much of the peak (gross) the realised (net) exit kept. When the trade
// closed off-tape (stale price), realised P&L is fictional → no % is shown.
function CaptureCell({ cmp }: { cmp: ShadowComparison | undefined }) {
  if (cmp?.actual_exit_off_tape) {
    return (
      <span style={{ color: 'var(--color-warning)' }} title={OFF_TAPE_TITLE}>
        ⚠ off-tape
      </span>
    )
  }
  const actual = cmp?.actual_capture_pct
  if (actual == null) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const col =
    actual >= 0.6 ? 'var(--color-bull)' : actual >= 0.3 ? 'var(--color-warning)' : 'var(--color-bear)'
  return <span style={{ color: col, fontWeight: 600 }}>{pctFmt(actual)}</span>
}

// "Realistic value after giveback" — the ₹ the Layered Ratchet Stop would have
// kept, replayed on the real 1m tape. Robust even when the recorded exit is
// off-tape (that's the whole point: it shows the true-price outcome).
function AfterLockCell({ cmp }: { cmp: ShadowComparison | undefined }) {
  const layered = cmp?.policies.find((p) => p.policy === 'layered')
  if (!layered || layered.exit_net == null) {
    return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  }
  const n = parseFloat(layered.exit_net)
  return (
    <span className="whitespace-nowrap">
      <span style={{ color: n >= 0 ? 'var(--color-bull)' : 'var(--color-bear)', fontWeight: 600 }}>
        {n >= 0 ? '+' : '-'}₹{formatINR(Math.abs(n))}
      </span>
      {layered.capture_pct != null && (
        <span className="text-(--color-text-muted)"> · {pctFmt(layered.capture_pct)}</span>
      )}
    </span>
  )
}

// Realised P&L with an off-tape warning marker (the ₹ figure is fictional then).
function RealizedCell({ val, offTape }: { val: string; offTape: boolean }) {
  return (
    <span className="whitespace-nowrap">
      {pnlCell(val)}
      {offTape && (
        <span style={{ color: 'var(--color-warning)' }} title={OFF_TAPE_TITLE}>
          {' '}⚠
        </span>
      )}
    </span>
  )
}

export function TradeHistoryPage() {
  const { accessToken } = useAuth()
  const [page, setPage] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ['trade-history', page],
    queryFn: () => tradingApi.getHistory({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }, accessToken!),
    enabled: !!accessToken,
  })

  // Shadow comparison (peak / capture %) for recent closed trades — replayed
  // from 1m candles server-side; cached, not re-fetched per page.
  const { data: shadow } = useQuery({
    queryKey: ['shadow-compare'],
    queryFn: () => tradingApi.getShadowCompare({ limit: 100 }, accessToken!),
    enabled: !!accessToken,
    staleTime: 300_000,
  })
  const shadowById = new Map<string, ShadowComparison>(
    (shadow?.comparisons ?? []).map((c) => [c.position_id, c]),
  )

  const positions = data?.positions ?? []
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  // Running totals
  const totalPnl = positions.reduce((sum, p) => sum + parseFloat(p.realized_pnl), 0)
  const wins = positions.filter((p) => parseFloat(p.realized_pnl) > 0).length
  const winRate = positions.length > 0 ? Math.round((wins / positions.length) * 100) : null

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1">
          <DailyPnlCard />
        </div>

        {/* Summary cards */}
        {data && positions.length > 0 && (
          <>
            <SummaryCard label="Page P&L" value={pnlCell(String(totalPnl))} />
            <SummaryCard label="Win Rate" value={winRate != null ? `${winRate}%` : '—'} />
            <SummaryCard label="Trades" value={data.total} />
          </>
        )}
      </div>

      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border)">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
              Trade History
            </span>
            {data && (
              <span className="text-xs text-(--color-text-muted)">{data.total} trades</span>
            )}
          </div>
          <p className="text-[11px] text-(--color-text-muted) mt-1">
            Peak = best unrealised profit reached (real 1m tape) · Capture = realised ÷ peak ·
            {' '}After-lock = what the Layered Ratchet Stop would realistically have kept (shadow, not live).
            {' '}⚠ = closed on a stale/off-tape price, so realised P&L is unreliable.
          </p>
        </div>

        {isLoading && <div className="p-4"><Skeleton className="h-48 w-full" /></div>}

        {!isLoading && positions.length === 0 && (
          <EmptyState
            title="No trade history"
            description="Closed paper trades appear here."
          />
        )}

        {!isLoading && positions.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="border-b border-(--color-border)">
                  {['Symbol', 'Side', 'Qty', 'Entry', 'Exit', 'Reason', 'Realized P&L', 'Peak', 'Capture', 'After-lock', 'Opened', 'Closed'].map((h) => (
                    <th
                      key={h}
                      className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium whitespace-nowrap"
                      style={{ color: 'var(--color-text-muted)', textAlign: h === 'Symbol' ? 'left' : 'right' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((pos) => (
                  <tr key={pos.id} className="border-b border-(--color-border) hover:bg-(--color-surface-hover)">
                    <td className="px-3 py-2">
                      <Link
                        to={`/stocks/${pos.stock_id}`}
                        className="font-mono font-bold text-(--color-accent) hover:text-(--color-accent-hover)"
                        style={{ textDecoration: 'none' }}
                      >
                        {pos.symbol}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span style={{
                        padding: '2px 6px', borderRadius: '4px', fontWeight: 700, fontSize: '0.7rem',
                        background: pos.side === 'LONG' ? 'var(--color-profit-bg)' : 'var(--color-loss-bg)',
                        color: pos.side === 'LONG' ? 'var(--color-bull)' : 'var(--color-bear)',
                      }}>
                        {pos.side}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{formatInt(pos.quantity)}</td>
                    <td className="px-3 py-2 text-right font-mono">{priceFmt(pos.avg_entry_price)}</td>
                    <td className="px-3 py-2 text-right font-mono">{priceFmt(pos.exit_price)}</td>
                    <td className="px-3 py-2 text-right whitespace-nowrap"><ExitReason reason={pos.exit_reason} /></td>
                    <td className="px-3 py-2 text-right">
                      <RealizedCell val={pos.realized_pnl} offTape={!!shadowById.get(pos.id)?.actual_exit_off_tape} />
                    </td>
                    <td className="px-3 py-2 text-right"><PeakCell cmp={shadowById.get(pos.id)} /></td>
                    <td className="px-3 py-2 text-right"><CaptureCell cmp={shadowById.get(pos.id)} /></td>
                    <td className="px-3 py-2 text-right"><AfterLockCell cmp={shadowById.get(pos.id)} /></td>
                    <td className="px-3 py-2 text-right text-(--color-text-muted) whitespace-nowrap">
                      {new Date(pos.opened_at).toLocaleDateString('en-IN', {
                        timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: '2-digit',
                      })}
                    </td>
                    <td className="px-3 py-2 text-right text-(--color-text-muted) whitespace-nowrap">
                      {pos.closed_at
                        ? new Date(pos.closed_at).toLocaleString('en-IN', {
                          timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short',
                          hour: '2-digit', minute: '2-digit',
                        })
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="px-4 py-3 border-t border-(--color-border)">
            <Pagination
              page={page + 1}
              pages={totalPages}
              pageSize={PAGE_SIZE}
              total={data?.total ?? 0}
              onPageChange={(p) => setPage(p - 1)}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
      <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-1">{label}</p>
      <div className="text-xl font-bold font-mono text-(--color-text)">{value}</div>
    </div>
  )
}

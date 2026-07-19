/**
 * ProvisionalPanel — per-style provisional-confidence leaderboard
 * (Phase 3, slice 3.5).
 *
 * PROVISIONAL means: scored on the still-forming candle by the same
 * frozen engine, converging to the committed score at candle close.
 * Display-only observability — never a signal, never tradeable state —
 * and the panel labels it as such (the end-to-end labelling rule).
 *
 * Data: REST snapshot on mount/style change (reconciliation path), live
 * updates over the shared /ws/live socket (`subscribe_provisional`).
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { useAuth } from '@/hooks/useAuth'
import { useProvisionalStream } from '@/hooks/useProvisionalStream'
import { provisionalApi } from '@/lib/api/market_data'
import type { ProvisionalLeaderboard, ProvisionalRow } from '@/lib/api/market_data'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { formatPct } from '@/lib/format'

// All six published styles: the four profile styles + the legacy signal
// classifications — a holder's "setup no longer passes" preview must be
// reachable for every style the backend can publish (bug-hunter LOW).
const STYLES = ['intraday', 'swing', 'fno', 'investment', 'scalp', 'positional'] as const

function asOfLabel(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false, timeZone: 'Asia/Kolkata',
  })
}

function DirectionCell({ row }: { row: ProvisionalRow }) {
  if (row.gate === null) {
    // window unusable server-side — the score says NOTHING; never render
    // this as "your setup no longer passes"
    return (
      <span className="text-(--color-text-muted)" aria-label="no data">
        — no data
      </span>
    )
  }
  if (row.direction === null || row.confidence === null) {
    return (
      <span className="text-(--color-text-muted)" aria-label="below gate">
        — below gate
      </span>
    )
  }
  const bullish = row.direction === 'BUY'
  return (
    <span
      style={{ color: bullish ? 'var(--color-profit)' : 'var(--color-loss)' }}
      aria-label={bullish ? 'buy setup' : 'sell setup'}
    >
      {bullish ? '▲' : '▼'} {row.direction}
    </span>
  )
}

export function ProvisionalPanel() {
  const { accessToken } = useAuth()
  const [style, setStyle] = useState<(typeof STYLES)[number]>('intraday')
  const { boards, connected } = useProvisionalStream([...STYLES])

  const query = useQuery<ProvisionalLeaderboard>({
    queryKey: ['provisional-leaderboard', style],
    queryFn: () => provisionalApi.getLeaderboard(style, accessToken ?? ''),
    enabled: accessToken !== null,
    staleTime: 10_000,
  })

  // WS snapshot wins once it has arrived for the selected style; the REST
  // answer covers mount + reconnect gaps.
  const board = boards[style] ?? query.data
  const rows = board?.rows ?? []

  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg mb-4">
      <div className="px-4 py-3 border-b border-(--color-border) flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide">
          Live confidence
        </span>
        <span
          className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
          style={{
            background: 'var(--color-warning-bg, var(--color-surface-3))',
            color: 'var(--color-warning, var(--color-text-muted))',
          }}
        >
          Provisional
        </span>
        <span className="ml-auto flex items-center gap-1.5 text-xs" style={{ color: connected ? 'var(--color-bull)' : 'var(--color-text-muted)' }}>
          <span
            style={{
              width: '6px', height: '6px', borderRadius: '50%', display: 'inline-block',
              background: connected ? 'var(--color-bull)' : 'var(--color-text-muted)',
            }}
          />
          {connected ? 'Live' : 'Offline'}
        </span>
      </div>

      <div className="px-4 pt-3 flex gap-1" role="tablist" aria-label="Leaderboard style">
        {STYLES.map((s) => (
          <button
            key={s}
            role="tab"
            aria-selected={style === s}
            onClick={() => setStyle(s)}
            className="text-xs px-2.5 py-1.5 rounded capitalize focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
            style={{
              background: style === s ? 'var(--color-accent-bg)' : 'transparent',
              color: style === s ? 'var(--color-accent)' : 'var(--color-text-muted)',
              minHeight: '32px',
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="p-4 pt-3">
        {query.isLoading && !board ? (
          <div className="space-y-2" aria-label="loading leaderboard">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height="1.5rem" />
            ))}
          </div>
        ) : query.isError && !board ? (
          <EmptyState
            title="Leaderboard unavailable"
            description="Could not load provisional scores."
            action={
              <button
                onClick={() => void query.refetch()}
                className="text-xs px-3 py-2 rounded border border-(--color-border-strong) text-(--color-text) focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
                style={{ minHeight: '36px' }}
              >
                Retry
              </button>
            }
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No provisional scores"
            description="Nothing in the hot set passes this style's gate right now — or the market is closed."
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-(--color-text-muted)">
                <th className="text-left font-semibold pb-1.5">Symbol</th>
                <th className="text-left font-semibold pb-1.5">Setup</th>
                <th className="text-right font-semibold pb-1.5">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={`${row.stock_id}:${row.profile_key ?? row.signal_id ?? 'legacy'}`}
                  className="border-t border-(--color-border)"
                >
                  <td className="py-1.5 pr-2">
                    <span className="font-semibold" style={{ fontFamily: 'var(--font-mono)' }}>
                      {row.symbol}
                    </span>
                    {row.signal_id != null && (
                      <span className="ml-1.5 text-[10px] text-(--color-accent)" title="you hold an active signal on this stock">
                        signal
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 pr-2 text-xs">
                    <DirectionCell row={row} />
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {row.confidence !== null ? formatPct(row.confidence, { signed: false }) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {board?.as_of && (
          <div className="pt-2 text-[10px] text-(--color-text-muted)" aria-live="off">
            provisional · converges at candle close · as of {asOfLabel(board.as_of)} IST
          </div>
        )}
      </div>
    </div>
  )
}

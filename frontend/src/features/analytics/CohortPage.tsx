import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '@/hooks/useAuth'
import { analyticsApi, type CohortTrade } from '@/lib/api/analytics'
import { PageHeader } from '@/components/layout/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { formatPct, formatScore } from '@/lib/format'

// U20 — the trades a gate WOULD block, rendered as a contact sheet of mini price panels.
// Statistics say WHETHER a gate separates winners from losers; a sheet of charts says WHAT.
// The would-block set comes from the order path's own verdict (GET /analytics/cohort/{key}).

const OUTCOME: Record<string, { glyph: string; color: string }> = {
  tp_first: { glyph: '▲ target', color: 'var(--color-profit)' },
  sl_first: { glyph: '▼ stopped', color: 'var(--color-loss)' },
  entry_touched: { glyph: '◆ entered', color: 'var(--color-accent)' },
  expired_untouched: { glyph: '— no entry', color: 'var(--color-text-secondary)' },
  expired_open: { glyph: '— expired', color: 'var(--color-text-secondary)' },
  open: { glyph: '· open', color: 'var(--color-text-secondary)' },
}

function humanize(key: string): string {
  return key.replace(/_/g, ' ')
}

// A small OHLC candlestick with the entry/SL/TP levels drawn across it. Pure SVG (Decision C) —
// the point is to SEE the set, not tick fidelity.
function TradeSpark({ trade }: { trade: CohortTrade }) {
  const W = 200
  const H = 96
  const pad = 6
  const bars = trade.bars
  if (bars.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-[11px] text-(--color-text-secondary)"
        style={{ height: H }}
      >
        no price window
      </div>
    )
  }
  const levels = [trade.entry, trade.stop_loss, trade.take_profit]
  const pmin = Math.min(...bars.map((b) => b.low), ...levels)
  const pmax = Math.max(...bars.map((b) => b.h), ...levels)
  const range = pmax - pmin || 1
  const yFor = (p: number) => H - pad - ((p - pmin) / range) * (H - 2 * pad)
  const step = bars.length > 1 ? (W - 2 * pad) / (bars.length - 1) : 0
  const xFor = (i: number) => pad + i * step
  const bw = Math.max(1.5, Math.min(6, step * 0.6))
  const up = 'var(--color-bull)'
  const down = 'var(--color-bear)'

  // Each level is distinguished three ways — colour, a distinct dash, AND a text label — so it is
  // unambiguous for colour-blind viewers (SL vs TP is safety-critical). Labels use a neutral,
  // AA-safe token; the line keeps its semantic colour.
  const level = (p: number, color: string, key: string, dash: string | undefined, label: string) => (
    <g key={key}>
      <line
        x1={pad}
        x2={W - pad}
        y1={yFor(p)}
        y2={yFor(p)}
        stroke={color}
        strokeWidth={1}
        strokeDasharray={dash}
        opacity={0.9}
      />
      <text
        x={W - pad}
        y={yFor(p) - 1.5}
        textAnchor="end"
        fontSize="7"
        fontWeight="600"
        fill="var(--color-text-secondary)"
      >
        {label}
      </text>
    </g>
  )

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`${trade.symbol} ${trade.direction}: ${bars.length}-day price window with entry, stop and target`}
    >
      {bars.map((b, i) => {
        const cx = xFor(i)
        const bull = b.c >= b.o
        const color = bull ? up : down
        const bodyTop = yFor(Math.max(b.o, b.c))
        const bodyH = Math.max(1, Math.abs(yFor(b.o) - yFor(b.c)))
        return (
          <g key={i}>
            <line x1={cx} x2={cx} y1={yFor(b.h)} y2={yFor(b.low)} stroke={color} strokeWidth={1} />
            <rect x={cx - bw / 2} y={bodyTop} width={bw} height={bodyH} fill={color} />
          </g>
        )
      })}
      {level(trade.entry, 'var(--color-accent)', 'entry', undefined, 'E')}
      {level(trade.stop_loss, 'var(--color-loss)', 'sl', '4 2', 'SL')}
      {level(trade.take_profit, 'var(--color-profit)', 'tp', '1 2', 'TP')}
    </svg>
  )
}

function TradeCard({ trade }: { trade: CohortTrade }) {
  const tone = trade.outcome_status ? OUTCOME[trade.outcome_status] : undefined
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-surface-2) p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="font-mono font-bold text-sm text-(--color-text)">{trade.symbol}</span>
        <span
          className="text-[11px] font-medium"
          style={{ color: trade.direction === 'SELL' ? 'var(--color-loss)' : 'var(--color-profit)' }}
        >
          {trade.direction} · {trade.confidence_pct}%
        </span>
      </div>
      <TradeSpark trade={trade} />
      <div className="flex items-center justify-between text-[11px]">
        <span style={{ color: tone?.color ?? 'var(--color-text-secondary)' }}>
          {tone?.glyph ?? '· pending'}
        </span>
        {trade.realized_r != null && (
          <span
            className="font-mono"
            style={{ color: trade.realized_r >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}
          >
            {formatScore(trade.realized_r, 2)}R
          </span>
        )}
      </div>
      <p className="text-[11px] text-(--color-text-secondary) line-clamp-2" title={trade.reason}>
        {trade.reason}
      </p>
    </div>
  )
}

export function CohortPage() {
  const { gateKey = '' } = useParams()
  const { accessToken } = useAuth()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['gate-cohort', gateKey],
    queryFn: () => analyticsApi.getGateCohort(gateKey, accessToken!),
    enabled: !!accessToken && !!gateKey,
    staleTime: 60_000,
  })

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={`Would-block cohort — ${humanize(gateKey)}`}
        subtitle="The trades this gate would suppress, as charts. Statistics say whether a gate separates winners from losers; a contact sheet says what. Read-only."
      />

      <Link
        to="/analytics/registry"
        className="text-xs text-(--color-text-secondary) hover:text-(--color-text) w-fit rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--color-bg)"
      >
        ← Back to the gate register
      </Link>

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" aria-label="loading cohort">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {isError && (
        <div className="p-4 text-sm text-(--color-text-secondary) bg-(--color-surface-2) border border-(--color-border) rounded-lg">
          Could not load the cohort.{' '}
          <Button variant="link" size="sm" onClick={() => void refetch()}>
            Retry
          </Button>
        </div>
      )}

      {data && !data.supported && (
        <div className="p-4 text-sm text-(--color-text-secondary) bg-(--color-surface-2) border border-(--color-border) rounded-lg">
          No signal-only cohort for <span className="font-mono">{gateKey}</span>
          {data.gate_status ? ` (${data.gate_status})` : ''}. {data.reason}
        </div>
      )}

      {data && data.supported && (
        <>
          {/* Cohort summary — sample size travels with its statistic (H11/A24). */}
          <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm">
            <span>
              <span className="font-bold font-mono text-(--color-text)">{data.cohort_count}</span>
              <span className="ml-2 text-[11px] text-(--color-text-secondary) uppercase tracking-wide">
                would-block trades (of {data.scanned} scanned)
              </span>
            </span>
            {data.cohort_realized_r != null && (
              <span
                className="font-mono font-bold"
                style={{ color: data.cohort_realized_r >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}
              >
                {formatScore(data.cohort_realized_r, 2)}R total
              </span>
            )}
            {data.cohort_realized_pnl_pct != null && (
              <span className="text-(--color-text-secondary)">{formatPct(data.cohort_realized_pnl_pct)} P&amp;L</span>
            )}
          </div>

          {data.trades.length === 0 ? (
            <EmptyState
              title="No trades in the would-block cohort"
              description="This gate would not have suppressed any of the scanned signals (or none are recorded yet)."
            />
          ) : (
            <>
              {data.cohort_count > data.trades.length && (
                <p className="text-[11px] text-(--color-text-secondary)">
                  Showing the first {data.trades.length} of {data.cohort_count}.
                </p>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {data.trades.map((t) => (
                  <TradeCard key={t.signal_id} trade={t} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

/**
 * Opportunities — the persistent, live-priced, ranked signals list (user request 2026-08-21).
 *
 * Unlike the alert FEED below it (an ephemeral, session-only tick stream where rows vanish and the
 * price is frozen at trigger time), this is the durable view of what is tradeable RIGHT NOW: it is
 * sourced from `GET /signals/active` (server-side deduped into `sources_count`, only `active` +
 * non-expired — so a signal stays until it resolves/expires: "keep until no longer useful"), the
 * price is LIVE (`useLiveQuotes` → `PriceCell`), the anti-chase guardrail recomputes against that
 * live price, and the list is ranked by conviction with the top-N highlighted.
 *
 * Provisional-layer honesty is preserved: the trade button routes through the same paper order path
 * (risk-first sizing + circuit breaker) as everywhere else.
 */

import { memo, useCallback, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ShoppingCart, Star } from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { useToast } from '@/hooks/useToast'
import { signalsApi } from '@/lib/api/signals'
import { tradingApi } from '@/lib/api/trading'
import { useTradingHaltStore } from '@/store/tradingHaltStore'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { PriceCell } from '@/components/ui/PriceCell'
import { SkeletonTable } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { formatCurrency, formatPct, formatRatio } from '@/lib/format'
import { cn } from '@/lib/utils'
import { bestByLabel, chaseGuidance, signalAgeLabel, tradePlan, validityLabel } from './alertPresentation'
import { rankSignals, type Ranked, TOP_N } from './conviction'

const OppRow = memo(function OppRow({
  ranked,
  ltp,
  onTrade,
  isTrading,
  halted,
}: {
  ranked: Ranked
  ltp: number | undefined
  onTrade: (signalId: string, side: 'BUY' | 'SELL') => void
  isTrading: boolean
  halted: boolean
}) {
  const sig = ranked.signal
  const plan = tradePlan(sig)
  const chase = ltp !== undefined ? chaseGuidance(sig, ltp) : null // LIVE chase (recomputes on tick)
  const isBuy = sig.direction !== 'SELL'
  return (
    <TableRow
      className={ranked.isTop ? 'bg-(--color-accent-bg)' : undefined}
      style={{ opacity: sig.near_expiry || sig.choppy ? 0.7 : 1 }}
    >
      <TableCell>
        {ranked.isTop ? (
          <span
            className="flex items-center gap-1 text-(--color-accent) font-semibold text-[11px]"
            title={`Top conviction pick (v1 score ${Math.round(ranked.score)})`}
          >
            <Star size={11} aria-hidden="true" />
            Top
          </span>
        ) : (
          <span className="text-(--color-text-muted) text-[11px]">—</span>
        )}
      </TableCell>
      <TableCell>
        <Link
          to={`/stocks/${sig.stock_id}`}
          className="font-mono font-bold text-(--color-accent) hover:text-(--color-accent-hover)"
          style={{ textDecoration: 'none' }}
        >
          {sig.symbol}
        </Link>
        {sig.sources_count > 1 && (
          <span
            title={`${sig.sources_count} signals (base + profile) merged into one`}
            className="ml-1.5 text-[9px] px-1 rounded bg-(--color-surface-3) text-(--color-text-muted)"
          >
            ×{sig.sources_count}
          </span>
        )}
      </TableCell>
      <TableCell>
        <span
          className="flex items-center gap-1 font-medium"
          style={{ color: isBuy ? 'var(--color-bull)' : 'var(--color-bear)' }}
        >
          <span aria-hidden="true">{isBuy ? '▲' : '▼'}</span>
          {isBuy ? 'BUY' : 'SELL'}
        </span>
      </TableCell>
      <TableCell numeric className="font-mono text-(--color-text)">
        <PriceCell value={ltp} format={formatCurrency} />
      </TableCell>
      <TableCell>
        {chase ? (
          <span className="flex items-center gap-2 text-xs">
            <span className="text-(--color-text-muted) font-mono tabular-nums">
              @ {formatCurrency(chase.entry)}
            </span>
            {chase.extended ? (
              <span className="flex items-center gap-1 text-(--color-warning)">
                <span aria-hidden="true">⚠</span>
                chasing {formatPct(chase.pastEntryPct)} past entry
              </span>
            ) : (
              <span className="text-(--color-text-muted) font-mono tabular-nums">
                don&apos;t chase {chase.isBuy ? '>' : '<'} {formatCurrency(chase.limit)}
              </span>
            )}
          </span>
        ) : (
          <span className="text-(--color-text-muted) text-xs">—</span>
        )}
      </TableCell>
      <TableCell className="text-xs">
        {plan ? (
          <span className="flex items-center gap-2 font-mono tabular-nums text-(--color-text-muted)">
            <span>
              SL <span className="text-(--color-loss)">{formatCurrency(plan.sl)}</span>
            </span>
            <span>
              TP <span className="text-(--color-profit)">{formatCurrency(plan.tp)}</span>
            </span>
            {plan.rr !== null && <span>R:R {formatRatio(plan.rr)}</span>}
            <span>· {sig.confidence_pct}%</span>
          </span>
        ) : (
          <span className="text-(--color-text-muted)">—</span>
        )}
      </TableCell>
      <TableCell className="text-xs text-(--color-text-muted)">
        <span className="flex flex-col leading-tight">
          <span>
            signal {signalAgeLabel(sig.created_at)}
            {bestByLabel(sig) && <span className="text-(--color-text)"> · {bestByLabel(sig)}</span>}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="font-mono tabular-nums">{validityLabel(sig)}</span>
            {sig.near_expiry && (
              <span className="text-(--color-warning)">
                <span aria-hidden="true">⚠</span> stale
              </span>
            )}
            {sig.choppy && <span className="text-(--color-warning)">choppy</span>}
          </span>
        </span>
      </TableCell>
      <TableCell numeric>
        <Button
          variant="outline"
          size="xs"
          disabled={isTrading || halted}
          onClick={() => onTrade(sig.id, isBuy ? 'BUY' : 'SELL')}
          title={halted ? 'Trading is halted — release the kill switch on Go Live' : `Paper ${sig.direction} ${sig.symbol}`}
          aria-label={`Paper ${sig.direction} ${sig.symbol}`}
        >
          <ShoppingCart size={12} aria-hidden="true" />
          {isTrading ? '…' : isBuy ? '▲ Buy' : '▼ Sell'}
        </Button>
      </TableCell>
    </TableRow>
  )
})

export function OpportunitiesTable() {
  const { accessToken } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const halted = useTradingHaltStore((s) => s.halted)
  const [tradingId, setTradingId] = useState<string | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['opportunities-active'],
    // include_expiring so stale signals still show (flagged), never silently hidden.
    queryFn: () =>
      signalsApi.getActive({ minConfidence: 70, includeExpiring: true, limit: 100 }, accessToken!),
    enabled: accessToken !== null,
    refetchInterval: 60_000, // keep the persistent list fresh; resolved/expired signals drop off
    staleTime: 30_000,
  })

  const signals = useMemo(() => data?.signals ?? [], [data])
  const symbols = useMemo(() => signals.map((s) => s.symbol), [signals])
  const { quotes, connected } = useLiveQuotes(symbols)
  const ranked = useMemo(() => rankSignals(signals), [signals])

  const { mutate: placePaperOrder } = useMutation({
    mutationFn: ({ signalId, side }: { signalId: string; side: 'BUY' | 'SELL' }) =>
      tradingApi.placeOrder({ signal_id: signalId, side }, accessToken!),
    onSuccess: (order) => {
      toast.success(`Paper ${order.side} placed: ${order.filled_qty} × ${order.symbol}`)
      void qc.invalidateQueries({ queryKey: ['positions-open'] })
      void qc.invalidateQueries({ queryKey: ['daily-pnl'] })
      void qc.invalidateQueries({ queryKey: ['paper-record'] })
      setTradingId(null)
    },
    onError: (err: { message?: string }) => {
      toast.error(err.message ?? 'Order rejected')
      setTradingId(null)
    },
  })

  const handleTrade = useCallback(
    (signalId: string, side: 'BUY' | 'SELL') => {
      if (halted) {
        toast.error('Trading is halted — release the kill switch on Go Live.')
        return
      }
      setTradingId(signalId)
      placePaperOrder({ signalId, side })
    },
    [halted, toast, placePaperOrder],
  )

  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
      <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between gap-2 flex-wrap">
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
          Opportunities
          <span
            className={cn(
              'inline-block w-1.5 h-1.5 rounded-full',
              connected ? 'bg-(--color-profit)' : 'bg-(--color-text-muted)',
            )}
            title={connected ? 'Live prices' : 'Prices offline'}
            aria-hidden="true"
          />
          <span
            className="font-normal normal-case text-(--color-text-muted)"
            title="Live, deduped, active signals ranked by a v1 conviction score (confidence − age-decay − choppy). Top picks starred; the rest by most-recent + confidence."
          >
            live · ranked · top {TOP_N} starred
          </span>
        </span>
        {!isLoading && !isError && (
          <span className="text-xs text-(--color-text-muted)">
            {signals.length} active signal{signals.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {isLoading ? (
        // Column-structured skeleton matching the 8-column table (UI_GUIDELINES §4.8).
        <div aria-busy="true">
          <SkeletonTable rows={8} cols={8} />
        </div>
      ) : isError ? (
        <EmptyState
          title="Couldn't load signals"
          description="The active-signals request failed."
          action={
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              Retry
            </Button>
          }
        />
      ) : signals.length === 0 ? (
        <EmptyState
          title="No active signals"
          description="Nothing meets the confluence gate right now. Signals appear here as the engine commits them; they stay until they hit target/stop or expire."
        />
      ) : (
        <Table aria-label="Opportunities">
          <TableHeader>
            <TableRow>
              <TableHead>Rank</TableHead>
              <TableHead>Symbol</TableHead>
              <TableHead>Dir</TableHead>
              <TableHead numeric>Live price</TableHead>
              <TableHead>Entry discipline</TableHead>
              <TableHead>Plan</TableHead>
              <TableHead>Window</TableHead>
              <TableHead numeric>Trade</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ranked.map((r) => (
              <OppRow
                key={r.signal.id}
                ranked={r}
                ltp={quotes[r.signal.symbol]?.ltp}
                onTrade={handleTrade}
                isTrading={tradingId === r.signal.id}
                halted={halted}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

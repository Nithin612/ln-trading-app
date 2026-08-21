/**
 * AlertBell — topbar entry point for the live tick-trigger alert stream
 * (Phase 3.5). Bell + unseen badge; the panel lists session alerts newest
 * first with server-side style filtering. Provisional/observability layer
 * only — nothing here gates or modifies signals.
 */

import { memo, useCallback, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, ShoppingCart } from 'lucide-react'

import { useAlertStream, type LiveAlert } from '@/hooks/useAlertStream'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { type SignalOut } from '@/lib/api/signals'
import { tradingApi } from '@/lib/api/trading'
import { watchlistsApi } from '@/lib/api/watchlists'
import { useTradingHaltStore } from '@/store/tradingHaltStore'
import { Popover } from '@/components/ui/popover'
import { EmptyState } from '@/components/ui/empty-state'
import { SimpleSelect } from '@/components/ui/simple-select'
import { Checkbox } from '@/components/ui/checkbox'
import { formatCurrency, formatPct, formatRatio } from '@/lib/format'
import { cn } from '@/lib/utils'
import {
  ALERT_STYLES,
  SOURCE_LABEL,
  TAG_META,
  TONE_CLASS,
  bestByLabel,
  chaseGuidance,
  formatAlertTime,
  signalAgeLabel,
  tradePlan,
  validityLabel,
} from './alertPresentation'
import { ENTRY_SOURCE, useAlertContext } from './useAlertContext'

// "Entered zone" (source `entry_zone`) is the actionable buy/sell trigger:
// price re-entered the entry band of a signal the confluence engine already
// generated. The bell defaults to showing ONLY these — level crosses, S/R
// zone entries and volume bursts are context, hidden until the user opts in.
const ENTRY_ONLY_KEY = 'alertbell:entryOnly'

function loadEntryOnly(): boolean {
  try {
    const v = localStorage.getItem(ENTRY_ONLY_KEY)
    return v === null ? true : v === '1'
  } catch {
    return true
  }
}

export function AlertBell() {
  const { alerts, connected, authFailed, styles, setStyles, watchlist, setWatchlist } =
    useAlertStream()
  const { accessToken } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const halted = useTradingHaltStore((s) => s.halted)

  // Trade an alert directly (its originating signal) through the same paper
  // order path + circuit breaker the dashboard uses — so an alerted stock that
  // isn't on the (deduped, filtered, paginated) dashboard list is still tradable.
  const [tradingSignalId, setTradingSignalId] = useState<string | null>(null)
  const { mutate: placePaperOrder } = useMutation({
    mutationFn: ({ signalId, side }: { signalId: string; side: 'BUY' | 'SELL' }) =>
      tradingApi.placeOrder({ signal_id: signalId, side }, accessToken!),
    onSuccess: (order) => {
      toast.success(`Paper ${order.side} placed: ${order.filled_qty} × ${order.symbol}`)
      void qc.invalidateQueries({ queryKey: ['positions-open'] })
      void qc.invalidateQueries({ queryKey: ['daily-pnl'] })
      void qc.invalidateQueries({ queryKey: ['paper-record'] })
      setTradingSignalId(null)
    },
    onError: (err: { message?: string }) => {
      toast.error(err.message ?? 'Order rejected')
      setTradingSignalId(null)
    },
  })
  const handleTrade = useCallback(
    (signalId: string, side: 'BUY' | 'SELL') => {
      if (halted) {
        toast.error('Trading is halted — release the kill switch on Go Live.')
        return
      }
      setTradingSignalId(signalId)
      placePaperOrder({ signalId, side })
    },
    [halted, toast, placePaperOrder],
  )

  // Entry-only view (buy/sell zone triggers), persisted across sessions.
  const [entryOnly, setEntryOnlyState] = useState(loadEntryOnly)
  const setEntryOnly = (v: boolean) => {
    setEntryOnlyState(v)
    try {
      localStorage.setItem(ENTRY_ONLY_KEY, v ? '1' : '0')
    } catch {
      /* private mode / storage disabled — filter still works in-memory */
    }
  }
  const visibleAlerts = useMemo(
    () => (entryOnly ? alerts.filter((a) => a.source === ENTRY_SOURCE) : alerts),
    [alerts, entryOnly],
  )

  // Watchlist scope options — cached; the bell mounts once in AppShell.
  const { data: watchlists } = useQuery({
    queryKey: ['watchlists'],
    queryFn: () => watchlistsApi.list(accessToken ?? ''),
    enabled: accessToken !== null,
    staleTime: 60_000,
  })

  // Unseen = alerts newer than the newest one when the bell was last
  // clicked. Index math, not length math — the list is capped, so counts
  // derived from length drift once trimming starts.
  const [lastSeenId, setLastSeenId] = useState<string | null>(null)
  const unseen = useMemo(() => {
    if (visibleAlerts.length === 0) return 0
    if (lastSeenId === null) return visibleAlerts.length
    const idx = visibleAlerts.findIndex((a) => a.id === lastSeenId)
    return idx === -1 ? visibleAlerts.length : idx
  }, [visibleAlerts, lastSeenId])

  // sid → symbol and signalId → signal (for the anti-chase guardrail), both
  // immutable for an alert's life. Shared with the Live Signals page.
  const { symbolBySid, signalById } = useAlertContext(visibleAlerts, accessToken)

  const toggleStyle = (s: string) =>
    setStyles(styles.includes(s) ? styles.filter((x) => x !== s) : [...styles, s])

  return (
    <Popover
      align="end"
      className="w-[360px]"
      trigger={
        <button
          onClick={() => setLastSeenId(visibleAlerts[0]?.id ?? null)}
          className="relative p-1.5 rounded-md text-(--color-text-muted) hover:text-(--color-text) hover:bg-(--color-surface-3) transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)"
          aria-label={unseen > 0 ? `Live alerts, ${unseen} unseen` : 'Live alerts'}
          data-testid="alert-bell"
        >
          <Bell size={15} />
          {unseen > 0 && (
            <span
              className="absolute -top-1 -right-1 min-w-[16px] h-[16px] px-0.5 rounded-full bg-(--color-accent-bg) text-(--color-accent) text-[10px] font-bold leading-[16px] text-center"
              data-testid="alert-unseen"
            >
              {unseen > 99 ? '99+' : unseen}
            </span>
          )}
        </button>
      }
    >
      <div className="flex flex-col max-h-[70vh]">
        <div className="flex items-center justify-between px-3 pt-2.5 pb-2 border-b border-(--color-border)">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-(--color-text)">Live alerts</span>
            <span
              className={cn(
                'inline-block w-1.5 h-1.5 rounded-full',
                connected ? 'bg-(--color-profit)' : 'bg-(--color-text-muted)',
              )}
              title={connected ? 'Connected' : 'Disconnected'}
              aria-hidden="true"
            />
          </div>
          <span className="text-[10px] text-(--color-text-muted)">this session</span>
        </div>

        <div className="flex items-center gap-2 px-3 py-2 border-b border-(--color-border)">
          <Checkbox
            id="alert-entry-only"
            checked={entryOnly}
            onCheckedChange={setEntryOnly}
          />
          <label
            htmlFor="alert-entry-only"
            className="text-[11px] text-(--color-text) select-none cursor-pointer"
          >
            Entry signals only
            <span className="text-(--color-text-muted)"> · buy/sell zone triggers</span>
          </label>
        </div>

        <div className="flex flex-wrap gap-1 px-3 py-2 border-b border-(--color-border)">
          {ALERT_STYLES.map((s) => {
            const active = styles.includes(s)
            return (
              <button
                key={s}
                onClick={() => toggleStyle(s)}
                aria-pressed={active}
                className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded-full border transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)',
                  active
                    ? 'border-(--color-accent) text-(--color-accent)'
                    : 'border-(--color-border) text-(--color-text-muted) hover:text-(--color-text)',
                )}
                style={
                  active
                    ? { backgroundColor: 'color-mix(in srgb, var(--color-accent) 12%, transparent)' }
                    : {}
                }
              >
                {s}
              </button>
            )
          })}
        </div>

        {watchlists !== undefined && watchlists.length > 0 && (
          <div className="px-3 py-2 border-b border-(--color-border)">
            <SimpleSelect
              size="sm"
              className="w-full"
              value={watchlist === null ? 'all' : String(watchlist)}
              options={[
                { value: 'all', label: 'All stocks' },
                ...watchlists.map((w) => ({ value: String(w.id), label: w.name })),
              ]}
              onChange={(v) => setWatchlist(v === 'all' ? null : Number(v))}
            />
          </div>
        )}

        {authFailed && (
          <div className="px-3 py-2 text-xs text-(--color-warning) border-b border-(--color-border)">
            Session expired — sign in again to resume live alerts.
          </div>
        )}
        {!connected && !authFailed && (
          <div className="px-3 py-2 text-xs text-(--color-text-muted) border-b border-(--color-border)">
            Reconnecting…
          </div>
        )}

        {visibleAlerts.length === 0 ? (
          <EmptyState
            className="py-10 px-6"
            title={entryOnly && alerts.length > 0 ? 'No entry signals yet' : 'No alerts yet'}
            description={
              entryOnly && alerts.length > 0
                ? 'Only buy/sell entry-zone triggers are shown. Turn off “Entry signals only” to see level crosses and volume bursts.'
                : 'Tick-trigger alerts — entry-zone touches, level crosses, volume bursts — stream here in real time during market hours.'
            }
          />
        ) : (
          // Capped at 100 rows (hook-side) with memoized rows — small
          // enough for a popover without virtualization.
          <ul className="overflow-y-auto divide-y divide-(--color-border)" role="list">
            {visibleAlerts.map((a) => (
              <AlertRow
                key={a.id}
                alert={a}
                symbol={symbolBySid.get(a.sid)}
                signal={a.signalId ? signalById.get(a.signalId) : undefined}
                onTrade={handleTrade}
                isTrading={tradingSignalId !== null && tradingSignalId === a.signalId}
                halted={halted}
              />
            ))}
          </ul>
        )}
      </div>
    </Popover>
  )
}

const AlertRow = memo(function AlertRow({
  alert,
  symbol,
  signal,
  onTrade,
  isTrading,
  halted,
}: {
  alert: LiveAlert
  symbol: string | undefined
  signal: SignalOut | undefined
  onTrade?: (signalId: string, side: 'BUY' | 'SELL') => void
  isTrading?: boolean
  halted?: boolean
}) {
  const meta = TAG_META[alert.tag]
  const chase = signal ? chaseGuidance(signal, Number(alert.price)) : null
  const plan = signal ? tradePlan(signal) : null
  return (
    <li className="px-3 py-2 text-xs hover:bg-(--color-surface-3)">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-semibold text-(--color-text) truncate">
          {symbol ?? `#${alert.sid}`}
        </span>
        <span className="font-mono tabular-nums text-(--color-text) flex-shrink-0">
          {formatCurrency(Number(alert.price))}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2 mt-0.5">
        <span className={cn('flex items-center gap-1', meta ? TONE_CLASS[meta.tone] : 'text-(--color-text-muted)')}>
          <span aria-hidden="true">{meta?.glyph ?? '•'}</span>
          <span>{meta?.label ?? alert.tag}</span>
          {alert.source && (
            <span className="text-(--color-text-muted)">· {SOURCE_LABEL[alert.source] ?? alert.source}</span>
          )}
        </span>
        <span className="text-(--color-text-muted) flex-shrink-0">
          <span className="uppercase text-[10px] tracking-wide mr-1.5">{alert.style}</span>
          <time className="font-mono tabular-nums">{formatAlertTime(alert.ts)}</time>
        </span>
      </div>
      {chase && (
        // Anti-chase guardrail: direction + ideal entry on the left, the
        // don't-chase price on the right (warns when the trigger already ran
        // past it). Direction encoded by glyph + word + colour, never colour
        // alone (UI_GUIDELINES §colours).
        <div
          className="flex items-center justify-between gap-2 mt-1"
          title="Past a third of the trade's risk (entry→SL) beyond entry, the reward:risk is materially worse — this is chasing."
        >
          <span
            className="flex items-center gap-1 font-medium"
            style={{ color: chase.isBuy ? 'var(--color-bull)' : 'var(--color-bear)' }}
          >
            <span aria-hidden="true">{chase.isBuy ? '▲' : '▼'}</span>
            <span>{chase.isBuy ? 'BUY' : 'SELL'}</span>
            <span className="text-(--color-text-muted) font-normal font-mono tabular-nums">
              @ {formatCurrency(chase.entry)}
            </span>
          </span>
          {chase.extended ? (
            <span className="flex items-center gap-1 text-(--color-warning) flex-shrink-0">
              <span aria-hidden="true">⚠</span>
              <span>chasing {formatPct(chase.pastEntryPct)} past entry</span>
            </span>
          ) : (
            <span className="text-(--color-text-muted) font-mono tabular-nums flex-shrink-0">
              don&apos;t chase {chase.isBuy ? '>' : '<'} {formatCurrency(chase.limit)}
            </span>
          )}
        </div>
      )}
      {signal && plan && (
        // The trade plan the alert doesn't otherwise show: stop, target, and
        // the reward:risk the signal was committed at, plus confidence. SL/TP
        // carry loss/profit colour AND a text label (never colour alone,
        // UI_GUIDELINES §colours); numbers via lib/format.
        <div className="flex items-center justify-between gap-2 mt-1 text-[10px]">
          <span className="flex items-center gap-2 min-w-0 font-mono tabular-nums text-(--color-text-muted)">
            <span>
              SL <span className="text-(--color-loss)">{formatCurrency(plan.sl)}</span>
            </span>
            <span>
              TP <span className="text-(--color-profit)">{formatCurrency(plan.tp)}</span>
            </span>
            {plan.rr !== null && <span>R:R {formatRatio(plan.rr)}</span>}
          </span>
          <span className="text-(--color-text-muted) flex-shrink-0">
            conf {signal.confidence_pct}%
          </span>
        </div>
      )}
      {signal && (
        // "When generated / when to consider" — age since commit on the left,
        // remaining runway on the right; a stale (≥80% elapsed) or choppy-regime
        // signal is flagged in warning tone so a late, low-runway entry is
        // visible before the click.
        <div className="flex items-center justify-between gap-2 mt-0.5 text-[10px] text-(--color-text-muted)">
          <span className="flex items-center gap-1 min-w-0 truncate">
            <span aria-hidden="true">⏱</span>
            <span>signal {signalAgeLabel(signal.created_at)}</span>
            {bestByLabel(signal) && <span className="text-(--color-text)">· {bestByLabel(signal)}</span>}
          </span>
          <span className="flex items-center gap-1.5 flex-shrink-0">
            <span className="font-mono tabular-nums">{validityLabel(signal)}</span>
            {signal.near_expiry && (
              <span className="text-(--color-warning)">
                <span aria-hidden="true">⚠</span> stale
              </span>
            )}
            {signal.choppy && <span className="text-(--color-warning)">choppy</span>}
          </span>
        </div>
      )}
      {alert.shadow && (
        // Shadow profiles run for evidence only; the order path rejects their
        // signals with 409. Offering a trade action here would be a button that
        // cannot work, so the row states what it is instead.
        <div className="flex justify-end mt-1.5">
          <span
            className="text-[10px] uppercase tracking-wide text-(--color-text-muted)"
            title="Shadow profile — recorded and measured to outcome, not tradeable until forward evidence earns activation."
          >
            shadow · not tradeable
          </span>
        </div>
      )}
      {!alert.shadow && signal && onTrade && (
        // Trade the alert's originating signal directly — routes through the
        // paper order path (risk-first sizing from the actual fill + circuit
        // breaker), so an alerted stock that isn't on the dashboard list is
        // still one click from a paper trade.
        <div className="flex justify-end mt-1.5">
          <button
            onClick={() => onTrade(signal.id, signal.direction === 'SELL' ? 'SELL' : 'BUY')}
            disabled={isTrading || halted}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold transition-colors disabled:opacity-50 border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)"
            style={{
              color: signal.direction === 'SELL' ? 'var(--color-bear)' : 'var(--color-bull)',
              borderColor: signal.direction === 'SELL' ? 'var(--color-bear)' : 'var(--color-bull)',
            }}
            title={signal.direction === 'SELL' ? 'Paper Sell (open short)' : 'Paper Buy (open long)'}
            aria-label={`Paper ${signal.direction === 'SELL' ? 'sell' : 'buy'} ${symbol ?? alert.sid}`}
          >
            <ShoppingCart size={10} aria-hidden="true" />
            {isTrading ? '…' : signal.direction === 'SELL' ? 'Sell' : 'Buy'}
          </button>
        </div>
      )}
    </li>
  )
})

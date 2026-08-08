/**
 * Live Signals — the global alert feed / alert centre (Phase 5 slice 5.4).
 *
 * The topbar bell is a glanceable summary; this is the full-width feed you
 * leave open during a session: every tick-trigger alert, server-side style and
 * watchlist scoping, the anti-chase guardrail, one-click paper trade on the
 * originating signal, and opt-in desktop notifications.
 *
 * This is the **provisional/observability** layer end-to-end: alerts report
 * that a price touched a level, they are at-most-once (pub/sub can drop), and
 * the stream is tailed from "$" — new entries only. Nothing here creates or
 * gates a signal; the trade button routes through the same paper order path
 * (risk-first sizing from the actual fill + the non-disableable circuit
 * breaker) as everywhere else.
 *
 * Rows are memoised rather than virtualised: `useAlertStream` caps retention at
 * 100 alerts, so windowing would add machinery for a list that cannot grow
 * past the point where it pays off. The live-update cost is re-rendering rows
 * on every flush, which memoisation is what actually fixes.
 */

import { memo, useCallback, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing, BellOff, ShoppingCart } from 'lucide-react'

import { useAlertStream, type LiveAlert } from '@/hooks/useAlertStream'
import { useAuth } from '@/hooks/useAuth'
import { useBrowserNotifications } from '@/hooks/useBrowserNotifications'
import { useToast } from '@/hooks/useToast'
import { type SignalOut } from '@/lib/api/signals'
import { tradingApi } from '@/lib/api/trading'
import { watchlistsApi } from '@/lib/api/watchlists'
import { useTradingHaltStore } from '@/store/tradingHaltStore'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { SimpleSelect } from '@/components/ui/simple-select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { formatCurrency, formatPct } from '@/lib/format'
import { cn } from '@/lib/utils'
import {
  ALERT_STYLES, SOURCE_LABEL, TAG_META, TONE_CLASS, chaseGuidance, formatAlertTime,
} from './alertPresentation'
import { ENTRY_SOURCE, useAlertContext } from './useAlertContext'

/** Client-side source lenses over whatever the server is streaming. */
const SOURCE_FILTERS = [
  { value: 'all', label: 'All alerts' },
  { value: 'entry', label: 'Entry signals only' },
  { value: 'levels', label: 'Level crosses (PDH/PDL/S-R)' },
  { value: 'risk', label: 'Stop / target proximity' },
  { value: 'volume', label: 'Volume bursts' },
]

const LEVEL_SOURCES = new Set(['pdh', 'pdl', 'sr_support', 'sr_resistance'])
const RISK_SOURCES = new Set(['sl_near', 'tp_near'])

function matchesSource(a: LiveAlert, filter: string): boolean {
  switch (filter) {
    case 'entry':
      return a.source === ENTRY_SOURCE
    case 'levels':
      return LEVEL_SOURCES.has(a.source)
    case 'risk':
      return RISK_SOURCES.has(a.source)
    case 'volume':
      return a.source === 'vburst' || a.tag === 'volume_burst'
    default:
      return true
  }
}

const FeedRow = memo(function FeedRow({
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
  onTrade: (signalId: string, side: 'BUY' | 'SELL') => void
  isTrading: boolean
  halted: boolean
}) {
  const meta = TAG_META[alert.tag]
  const chase = signal ? chaseGuidance(signal, Number(alert.price)) : null

  return (
    <TableRow>
      <TableCell numeric className="text-(--color-text-muted)">
        <time className="font-mono tabular-nums">{formatAlertTime(alert.ts)}</time>
      </TableCell>
      <TableCell className="font-mono font-bold text-(--color-text)">
        {symbol ?? `#${alert.sid}`}
      </TableCell>
      <TableCell>
        <span
          className={cn(
            'flex items-center gap-1',
            meta ? TONE_CLASS[meta.tone] : 'text-(--color-text-muted)',
          )}
        >
          {/* Glyph + word, never colour alone. */}
          <span aria-hidden="true">{meta?.glyph ?? '•'}</span>
          <span>{meta?.label ?? alert.tag}</span>
        </span>
      </TableCell>
      <TableCell className="text-(--color-text-muted)">
        {SOURCE_LABEL[alert.source] ?? alert.source}
      </TableCell>
      <TableCell className="text-(--color-text-muted) uppercase text-[0.7rem] tracking-wide">
        {alert.style}
      </TableCell>
      <TableCell numeric className="font-semibold">
        {formatCurrency(Number(alert.price))}
      </TableCell>
      <TableCell>
        {chase ? (
          <span
            className="flex items-center gap-2 text-xs"
            title="Past a third of the trade's risk (entry→SL) beyond entry, the reward:risk you were shown is materially gone — this is chasing."
          >
            <span
              className="flex items-center gap-1 font-medium"
              style={{ color: chase.isBuy ? 'var(--color-bull)' : 'var(--color-bear)' }}
            >
              <span aria-hidden="true">{chase.isBuy ? '▲' : '▼'}</span>
              {chase.isBuy ? 'BUY' : 'SELL'}
              <span className="text-(--color-text-muted) font-normal font-mono tabular-nums">
                @ {formatCurrency(chase.entry)}
              </span>
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
      <TableCell numeric>
        {/* A shadow alert comes from a profile running for EVIDENCE only. The
            order path rejects a non-active signal with 409, so a Buy button
            here would be a button that cannot work — say why instead. */}
        {alert.shadow ? (
          <span
            className="text-(--color-text-muted) text-[0.7rem] uppercase tracking-wide"
            title="Shadow profile — recorded and measured, not tradeable until forward evidence earns activation."
          >
            shadow
          </span>
        ) : signal ? (
          <Button
            variant="outline"
            size="xs"
            disabled={isTrading || halted}
            onClick={() => onTrade(signal.id, signal.direction === 'SELL' ? 'SELL' : 'BUY')}
            title={
              halted
                ? 'Trading is halted — release the kill switch on Go Live'
                : `Paper ${signal.direction} ${symbol ?? ''}`.trim()
            }
            aria-label={`Paper ${signal.direction} ${symbol ?? `stock ${alert.sid}`}`}
          >
            <ShoppingCart size={12} />
            {isTrading ? '…' : signal.direction === 'SELL' ? '▼ Sell' : '▲ Buy'}
          </Button>
        ) : (
          <span className="text-(--color-text-muted) text-xs">—</span>
        )}
      </TableCell>
    </TableRow>
  )
})

export function LiveSignalsPage() {
  const { alerts, connected, authFailed, styles, setStyles, watchlist, setWatchlist } =
    useAlertStream()
  const { accessToken } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const halted = useTradingHaltStore((s) => s.halted)

  const [sourceFilter, setSourceFilter] = useState('all')
  const [tradingSignalId, setTradingSignalId] = useState<string | null>(null)

  const visible = useMemo(
    () => alerts.filter((a) => matchesSource(a, sourceFilter)),
    [alerts, sourceFilter],
  )

  const { symbolBySid, signalById } = useAlertContext(visible, accessToken)
  const notify = useBrowserNotifications(alerts)

  const { data: watchlists } = useQuery({
    queryKey: ['watchlists'],
    queryFn: () => watchlistsApi.list(accessToken ?? ''),
    enabled: accessToken !== null,
    staleTime: 60_000,
  })

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

  const toggleStyle = (s: string) =>
    setStyles(styles.includes(s) ? styles.filter((x) => x !== s) : [...styles, s])

  const watchlistOptions = useMemo(
    () => [
      { value: '', label: 'All stocks' },
      ...(watchlists ?? []).map((w) => ({ value: String(w.id), label: w.name })),
    ],
    [watchlists],
  )

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Live signals"
        subtitle="Every tick-trigger alert as it fires. Observability layer — alerts report a level touch, they never create or gate a signal."
      />

      <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg bg-(--color-surface-2) border border-(--color-border)">
        <span className="flex items-center gap-1.5 text-xs">
          <span
            className={cn(
              'inline-block w-1.5 h-1.5 rounded-full',
              connected ? 'bg-(--color-profit)' : 'bg-(--color-text-muted)',
            )}
            aria-hidden="true"
          />
          <span style={{ color: connected ? 'var(--color-bull)' : 'var(--color-text-muted)' }}>
            {connected ? 'Live' : 'Offline'}
          </span>
        </span>

        <div className="flex items-center gap-1" role="group" aria-label="Alert styles">
          {ALERT_STYLES.map((s) => {
            const on = styles.length === 0 || styles.includes(s)
            return (
              <button
                key={s}
                type="button"
                aria-pressed={styles.includes(s)}
                onClick={() => toggleStyle(s)}
                className="text-xs px-2 py-1 rounded capitalize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)"
                style={{
                  background: styles.includes(s) ? 'var(--color-accent-bg)' : 'transparent',
                  color: on ? 'var(--color-accent)' : 'var(--color-text-muted)',
                  minHeight: '28px',
                }}
                title={
                  styles.length === 0
                    ? 'No filter — all styles streaming. Click to scope to this style.'
                    : `Filtering: ${styles.join(', ')}`
                }
              >
                {s}
              </button>
            )
          })}
        </div>

        <SimpleSelect
          value={sourceFilter}
          onChange={setSourceFilter}
          options={SOURCE_FILTERS}
          size="sm"
          className="min-w-52"
          aria-label="Alert type"
        />

        <SimpleSelect
          value={watchlist === null ? '' : String(watchlist)}
          onChange={(v) => setWatchlist(v === '' ? null : Number(v))}
          options={watchlistOptions}
          size="sm"
          className="min-w-40"
          aria-label="Watchlist scope"
        />

        {/* Desktop notifications — opt-in only, never auto-requested. */}
        <div className="ml-auto flex items-center gap-2">
          {notify.supported ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => void notify.setEnabled(!notify.enabled)}
              disabled={notify.permission === 'denied'}
              aria-pressed={notify.enabled}
              title={
                notify.permission === 'denied'
                  ? 'Notifications are blocked for this site in your browser settings.'
                  : notify.enabled
                    ? 'Desktop notifications on — bursts collapse into one summary.'
                    : 'Get a desktop notification when an alert fires, even with this tab in the background.'
              }
            >
              {notify.enabled ? <BellRing size={13} /> : <BellOff size={13} />}
              {notify.permission === 'denied'
                ? 'Notifications blocked'
                : notify.enabled
                  ? 'Notifications on'
                  : 'Notify me'}
            </Button>
          ) : (
            <span className="text-xs text-(--color-text-muted)">
              Desktop notifications unsupported in this browser
            </span>
          )}
        </div>
      </div>

      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between gap-2 flex-wrap">
          <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Alert feed
            <span
              className="px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider"
              style={{
                background: 'var(--color-warning-bg, var(--color-surface-3))',
                color: 'var(--color-warning)',
              }}
              title="At-most-once observability: alerts can be dropped, and the stream is tailed from new entries only. Committed state is reconciled over REST."
            >
              PROVISIONAL
            </span>
          </span>
          <span className="text-xs text-(--color-text-muted)">
            {visible.length} alert{visible.length !== 1 ? 's' : ''} this session
          </span>
        </div>

        {authFailed ? (
          <EmptyState
            title="Alert stream signed out"
            description="The live connection was rejected (expired session). Reload the page to reconnect with a fresh token."
          />
        ) : visible.length === 0 ? (
          <EmptyState
            title="No alerts yet"
            description={
              connected
                ? 'The stream is live and tailing new alerts only — nothing has triggered since you connected. Alerts fire when price touches a tracked level during market hours.'
                : 'Not connected to the alert stream. It reconnects automatically; the live worker only publishes during market hours.'
            }
          />
        ) : (
          <Table aria-label="Live alert feed">
            <TableHeader>
              <TableRow>
                <TableHead numeric>Time (IST)</TableHead>
                <TableHead>Symbol</TableHead>
                <TableHead>Trigger</TableHead>
                <TableHead>Level</TableHead>
                <TableHead>Style</TableHead>
                <TableHead numeric>Price</TableHead>
                <TableHead>Entry discipline</TableHead>
                <TableHead numeric>Trade</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((a) => (
                <FeedRow
                  key={a.id}
                  alert={a}
                  symbol={symbolBySid.get(a.sid)}
                  signal={a.signalId ? signalById.get(a.signalId) : undefined}
                  onTrade={handleTrade}
                  isTrading={tradingSignalId === (a.signalId ?? '')}
                  halted={halted}
                />
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}

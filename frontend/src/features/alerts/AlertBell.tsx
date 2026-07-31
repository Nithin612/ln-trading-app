/**
 * AlertBell — topbar entry point for the live tick-trigger alert stream
 * (Phase 3.5). Bell + unseen badge; the panel lists session alerts newest
 * first with server-side style filtering. Provisional/observability layer
 * only — nothing here gates or modifies signals.
 */

import { memo, useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Bell } from 'lucide-react'

import { useAlertStream, type LiveAlert } from '@/hooks/useAlertStream'
import { useAuth } from '@/hooks/useAuth'
import { stocksApi } from '@/lib/api/stocks'
import { signalsApi, type SignalOut } from '@/lib/api/signals'
import { watchlistsApi } from '@/lib/api/watchlists'
import { Popover } from '@/components/ui/popover'
import { EmptyState } from '@/components/ui/empty-state'
import { SimpleSelect } from '@/components/ui/simple-select'
import { Checkbox } from '@/components/ui/checkbox'
import { formatCurrency, formatPct } from '@/lib/format'
import { cn } from '@/lib/utils'
import {
  ALERT_STYLES,
  SOURCE_LABEL,
  TAG_META,
  TONE_CLASS,
  chaseGuidance,
  formatAlertTime,
} from './alertPresentation'

// "Entered zone" (source `entry_zone`) is the actionable buy/sell trigger:
// price re-entered the entry band of a signal the confluence engine already
// generated. The bell defaults to showing ONLY these — level crosses, S/R
// zone entries and volume bursts are context, hidden until the user opts in.
const ENTRY_ONLY_KEY = 'alertbell:entryOnly'
const ENTRY_SOURCE = 'entry_zone'

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

  // sid → symbol, cached forever (stock identity is immutable intraday).
  const sids = useMemo(() => [...new Set(visibleAlerts.map((a) => a.sid))], [visibleAlerts])
  const stockQueries = useQueries({
    queries: sids.map((sid) => ({
      queryKey: ['alert-stock', sid],
      queryFn: () => stocksApi.get(sid, accessToken ?? ''),
      staleTime: Infinity,
      enabled: accessToken !== null,
    })),
  })
  const symbolBySid = useMemo(() => {
    const m = new Map<number, string>()
    for (const q of stockQueries) {
      if (q.data) m.set(q.data.id, q.data.symbol)
    }
    return m
  }, [stockQueries])

  // Entry-zone alerts carry the originating signal; fetch its entry/SL/direction
  // once (immutable once created) to render the anti-chase guardrail. Cached
  // forever, like symbols — only entry alerts trigger a lookup.
  const signalIds = useMemo(
    () => [
      ...new Set(
        visibleAlerts
          .filter((a) => a.source === ENTRY_SOURCE && a.signalId)
          .map((a) => a.signalId as string),
      ),
    ],
    [visibleAlerts],
  )
  const signalQueries = useQueries({
    queries: signalIds.map((id) => ({
      queryKey: ['alert-signal', id],
      queryFn: () => signalsApi.getById(id, accessToken ?? ''),
      staleTime: Infinity,
      enabled: accessToken !== null,
    })),
  })
  const signalById = useMemo(() => {
    const m = new Map<string, SignalOut>()
    for (const q of signalQueries) {
      if (q.data) m.set(q.data.id, q.data)
    }
    return m
  }, [signalQueries])

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
}: {
  alert: LiveAlert
  symbol: string | undefined
  signal: SignalOut | undefined
}) {
  const meta = TAG_META[alert.tag]
  const chase = signal ? chaseGuidance(signal, Number(alert.price)) : null
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
    </li>
  )
})

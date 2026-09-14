import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { X, Edit2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi, type PositionOut, type PositionHealth, type HealthReason } from '@/lib/api/trading'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/hooks/useToast'
import { DailyPnlCard } from './DailyPnlCard'
import { PaperRecordCard } from './PaperRecordCard'
import { ClosePositionDialog } from './ClosePositionDialog'
import { UpdateSlDialog } from './UpdateSlDialog'
import { formatINR, formatInt } from '@/lib/format'

function pnlFmt(val: string | null): React.ReactNode {
  if (val == null) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const n = parseFloat(val)
  const sign = n >= 0 ? '+' : ''
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

/**
 * V2 — how to render a mark given where it came from.
 *
 * The backend chain is live tick -> last COMPLETE 1m bar -> DAILY CLOSE, so
 * `current_price` almost never goes null. Before this, a position whose feed had died
 * rendered a plausible number from a previous session with nothing marking it — an
 * em-dash at least signals absence, a stale close signals nothing and looks live.
 *
 * Colour is NEVER the only carrier (ui.md): each degraded state has a text label.
 */
const PRICE_STATE: Record<
  PositionOut['price_state'],
  { label: string; tone: 'secondary' | 'warn' } | null
> = {
  live: null, // a live quote needs no annotation — that is the expected state
  minute: { label: 'last 1m close', tone: 'secondary' },
  daily: { label: 'prev session close', tone: 'warn' },
  none: { label: 'no price', tone: 'warn' },
}

// Renders nothing for a live quote; a one-line provenance label otherwise. Text carries
// the meaning, colour only reinforces it.
function PriceProvenance({ state }: { state: PositionOut['price_state'] }) {
  const meta = PRICE_STATE[state]
  if (!meta) return null
  // ⛔ NOT `--color-loss`, which fails AA on this row's surface in slate (the DEFAULT
  // theme, 3.96:1) and midnight (4.18:1) — and worse, it is the token for "this position
  // is losing money", used by the SL cell and the P&L cell on the same row. A stale mark
  // is a DEGRADED STATE, not a negative value; painting it red makes the two
  // indistinguishable at a glance. `--color-warning` on its own `-bg` is the pill idiom
  // `HealthBadge` below already uses, and a painted fill is immune to the row's hover
  // background changing underneath it.
  // ⛔ NOT `--color-text-muted` either: 2.34:1 in daybreak at this size.
  if (meta.tone === 'warn') {
    return (
      <div className="mt-0.5">
        <span
          className="inline-block rounded px-1 py-px text-[11px] font-sans font-normal"
          style={{ background: 'var(--color-warning-bg)', color: 'var(--color-warning)' }}
        >
          {meta.label}
        </span>
      </div>
    )
  }
  return (
    <div
      className="text-[11px] font-sans font-normal"
      style={{ color: 'var(--color-text-secondary)' }}
    >
      {meta.label}
    </div>
  )
}

const REASON_LABEL: Record<HealthReason['code'], string> = {
  thesis_break: 'stop broken',
  trend_dead: 'trend dead',
  rr_inverted: 'R:R inverted',
  deep_mae: 'deep in red',
  stale: 'expired',
}

// Advisory emergency-exit verdict. CUT = structurally dead, consider exiting;
// WATCH = one soft warning. Glyph + word + colour, never colour alone (UI §5.2).
// The full reasons ride in the title so hovering explains the "why".
function HealthBadge({ health }: { health: PositionHealth | null }) {
  if (!health || health.verdict === 'hold') {
    return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  }
  const isCut = health.verdict === 'cut'
  const color = isCut ? 'var(--color-bear)' : 'var(--color-warning)'
  const bg = isCut ? 'var(--color-loss-bg)' : 'var(--color-warning-bg)'
  const glyph = isCut ? '⚠' : '◆' // glyph + word + colour — never colour alone (UI §5.2)
  const primary = health.reasons[0]
  const title = health.reasons.map((r) => `• ${r.detail}`).join('\n')
  return (
    <span title={title} className="inline-flex items-center gap-1.5 justify-end whitespace-nowrap">
      <span
        style={{
          padding: '2px 6px', borderRadius: '4px', fontWeight: 700, fontSize: '0.7rem',
          background: bg, color,
        }}
      >
        <span aria-hidden="true">{glyph} </span>
        {isCut ? 'CUT' : 'WATCH'}
      </span>
      {primary && (
        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.68rem' }}>
          {REASON_LABEL[primary.code]}
          {health.reasons.length > 1 ? ` +${health.reasons.length - 1}` : ''}
        </span>
      )}
    </span>
  )
}

function healthEdge(health: PositionHealth | null): string {
  if (health?.verdict === 'cut') return 'var(--color-bear)'
  if (health?.verdict === 'watch') return 'var(--color-warning)'
  return 'transparent'
}

function TrailBadge({ state }: { state: string }) {
  if (state === 'none') return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const colors: Record<string, string> = {
    breakeven: 'var(--color-info)',
    trailing_1: 'var(--color-warning)',
    trailing_2: 'var(--color-bull)',
  }
  return (
    <span style={{ color: colors[state] ?? 'var(--color-text-muted)', fontSize: '0.7rem', fontWeight: 600 }}>
      {state.replace('_', ' ')}
    </span>
  )
}

export function PositionsPage() {
  const { accessToken } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()

  const [closeTarget, setCloseTarget] = useState<PositionOut | null>(null)
  const [slTarget, setSlTarget] = useState<PositionOut | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['positions-open'],
    queryFn: () => tradingApi.getOpenPositions(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 30_000,
  })

  const closeMutation = useMutation({
    mutationFn: ({ id, exitPrice }: { id: string; exitPrice?: string }) =>
      tradingApi.closePosition(id, exitPrice, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['positions-open'] })
      void qc.invalidateQueries({ queryKey: ['trade-history'] })
      void qc.invalidateQueries({ queryKey: ['daily-pnl'] })
      toast.success('Position closed')
      setCloseTarget(null)
    },
    onError: () => toast.error('Failed to close position'),
  })

  const positions = data?.positions ?? []
  // V2 — computed once; the banner and any future per-row treatment read the same list.
  const strandedPositions = positions.filter((p) => p.stranded)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1">
          <DailyPnlCard />
        </div>
        <div className="lg:col-span-3">
          <PaperRecordCard />
        </div>
      </div>

      {/*
        V2 — STRANDED is not a worse staleness, it is a different condition: the name has
        no tradable instrument, so it receives no ticks and, once live trading exists, no
        order can be routed for it. That is why it is a page-level banner and not a
        per-row age badge.

        ⚠ THE QUALIFIER IS LOAD-BEARING: "un-exitable" is true of the LIVE path only.
        `close_position` needs no instrument — it falls back to the last stored close and,
        failing that, to `avg_entry_price` ("flat trade"). So closing here SUCCEEDS and
        books a realized P&L from a stale or fabricated price. An earlier draft of this
        banner said "cannot be exited here", which is false, and the review that caught
        the contradiction proposed disabling the row's Close button — that would TRAP the
        user in the one position they most need to get out of. The honest fix is the
        opposite: keep the button, correct the claim, and warn at the point of action
        (see ClosePositionDialog).

        Measured 2026-09-14: 740 stocks have no EQ instrument and exactly ONE of them
        printed a bar in the latest session — so a stranded name's close is stale, not
        merely a moment old.
      */}
      {strandedPositions.length > 0 && (
        <div
          role="alert"
          className="rounded-lg border px-4 py-3 text-sm"
          style={{
            // ⛔ NOT the loss triplet: `--color-loss` encodes a NEGATIVE VALUE (§5.1) and
            // the rejected/hit_sl states (§5.3). Stranded is a degraded state — the same
            // distinction `PriceProvenance` above is built on. Applying that rule to the
            // small annotation and not to the loud banner was inconsistent.
            borderColor: 'var(--color-warning)',
            background: 'var(--color-warning-bg)',
            color: 'var(--color-text)',
          }}
        >
          <span className="font-semibold">
            {strandedPositions.length} position{strandedPositions.length !== 1 ? 's' : ''} {strandedPositions.length !== 1 ? 'have' : 'has'} no tradable instrument
          </span>
          {' — '}
          {strandedPositions.map((p) => p.symbol).join(', ')}
          {'. '}
          {strandedPositions.length !== 1 ? 'These names get' : 'This name gets'}
          {' no live price, so an exit here is booked against a stale close — or against '}
          {'your entry price if no close exists at all. '}
          {'Square off at the broker, or repair the instrument list.'}
        </div>
      )}

      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Open Positions
          </span>
          {data && (
            <span className="text-xs text-(--color-text-muted)">{data.total} position{data.total !== 1 ? 's' : ''}</span>
          )}
        </div>

        {isLoading && <div className="p-4"><Skeleton className="h-48 w-full" /></div>}

        {!isLoading && positions.length === 0 && (
          <EmptyState
            title="No open positions"
            description="Paper-buy a signal from the Dashboard to open a position."
          />
        )}

        {!isLoading && positions.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="border-b border-(--color-border)">
                  {['Symbol', 'Side', 'Qty', 'Entry', 'Current', 'SL', 'TP', 'Trail', 'Unreal. P&L', 'Health', 'Opened', ''].map((h) => (
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
                    <td className="px-3 py-2" style={{ borderLeft: `2px solid ${healthEdge(pos.health)}` }}>
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
                    <td className="px-3 py-2 text-right font-mono text-(--color-text)">
                      {priceFmt(pos.current_price)}
                      <PriceProvenance state={pos.price_state} />
                    </td>
                    <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--color-bear)' }}>{priceFmt(pos.current_sl)}</td>
                    <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--color-bull)' }}>{priceFmt(pos.current_tp)}</td>
                    <td className="px-3 py-2 text-right"><TrailBadge state={pos.trail_state} /></td>
                    <td className="px-3 py-2 text-right">{pnlFmt(pos.unrealized_pnl)}</td>
                    <td className="px-3 py-2 text-right"><HealthBadge health={pos.health} /></td>
                    <td className="px-3 py-2 text-right text-(--color-text-muted) whitespace-nowrap">
                      {new Date(pos.opened_at).toLocaleString('en-IN', {
                        timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => setSlTarget(pos)}
                          className="p-1 rounded text-(--color-text-muted) hover:text-(--color-text) hover:bg-(--color-surface-3) transition-colors"
                          title="Update SL"
                        >
                          <Edit2 size={12} />
                        </button>
                        <button
                          onClick={() => setCloseTarget(pos)}
                          className="p-1 rounded hover:bg-(--color-surface-3) transition-colors"
                          style={{ color: 'var(--color-bear)' }}
                          title="Close position"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {closeTarget && (
        <ClosePositionDialog
          position={closeTarget}
          isLoading={closeMutation.isPending}
          onConfirm={(exitPrice) => closeMutation.mutate({ id: closeTarget.id, exitPrice })}
          onClose={() => setCloseTarget(null)}
        />
      )}

      {slTarget && (
        <UpdateSlDialog
          position={slTarget}
          onClose={() => setSlTarget(null)}
          onUpdated={() => {
            void qc.invalidateQueries({ queryKey: ['positions-open'] })
            setSlTarget(null)
          }}
        />
      )}
    </div>
  )
}

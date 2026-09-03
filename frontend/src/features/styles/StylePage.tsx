/**
 * Style page v2 (Phase 5 slice 5.3) — one page per trading style.
 *
 * Layout mirrors the engine's own two layers, kept visually separate because
 * conflating them is a correctness problem, not a cosmetic one:
 *
 *  - **Committed** (the table): scored on COMPLETE candles, valid from the next
 *    candle, tradeable. This is what the one-click paper trade acts on.
 *  - **Forming** (the provisional leaderboard): the same frozen engine scoring
 *    the still-forming candle, converging at close. Display-only, labelled
 *    provisional end-to-end, never tradeable.
 *
 * F&O has its own page (chain ladder + option-selling candidates), so this page
 * serves intraday / swing / investment.
 */

import { memo, useCallback, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, TrendingUp, Layers, Landmark } from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { useVirtualRows } from '@/hooks/useVirtualRows'
import { analyticsApi } from '@/lib/api/analytics'
import {
  suggestionsApi, PROFILE_STYLES, type ProfileStyle, type SuggestionOut,
} from '@/lib/api/suggestions'
import { tradingApi } from '@/lib/api/trading'
import { useTradingHaltStore } from '@/store/tradingHaltStore'
import { tradeBlock } from '@/features/alerts/alertPresentation'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { PriceCell } from '@/components/ui/PriceCell'
import { VirtualSpacer, VirtualViewport } from '@/components/ui/virtual-table'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { ProvisionalPanel } from '@/features/dashboard/ProvisionalPanel'
import { useToast } from '@/hooks/useToast'
import { formatCurrency, formatGreek, formatInt, formatPct } from '@/lib/format'
import { StyleStatsHeader } from './StyleStatsHeader'
import { FactorDrawer } from './FactorDrawer'

const STYLE_META: Record<ProfileStyle, { label: string; desc: string; icon: React.ReactNode }> = {
  intraday:   { label: 'Intraday',   desc: 'Same-session momentum & breakouts — squared off by close.',  icon: <Activity size={18} /> },
  swing:      { label: 'Swing',      desc: 'Multi-day trend continuation (~5 trading-day validity).',    icon: <TrendingUp size={18} /> },
  fno:        { label: 'F&O',        desc: 'Derivatives & option-selling setups.',                        icon: <Layers size={18} /> },
  investment: { label: 'Investment', desc: 'Positional / long-term theses (~30 trading-day validity).',   icon: <Landmark size={18} /> },
}

/**
 * Why a style's table is empty, per style.
 *
 * "Generated nightly after EOD" was shown for every style — true for the
 * EOD-scheduled ones, and simply false for intraday, whose three profiles are
 * inactive because walk-forward returned NEGATIVE risk-adjusted returns for all
 * of them (pdh_pdl −1.06 Sharpe, orb_15m −0.60, gainer_925 −0.86). An empty
 * table that blames the clock reads as a broken pipeline; the real reason is a
 * deliberate refusal to suggest trades from a profile that has not earned it.
 */
const EMPTY_REASON: Record<ProfileStyle, string> = {
  intraday:
    'No intraday profile has passed validation yet, so none are live. The three '
    + 'candidates were all negative on risk-adjusted walk-forward returns, and '
    + 'nothing is activated until forward evidence earns it — an empty table '
    + 'beats a losing suggestion.',
  swing:
    'Fresh suggestions are generated nightly after EOD (~7:30 PM IST on a trading day).',
  investment:
    'Fresh suggestions are generated nightly after EOD (~7:30 PM IST on a trading day).',
  fno:
    'Option-selling candidates need the IV-rank gate to pass; when volatility is '
    + 'cheap the engine correctly declines to sell premium.',
}

/** Must match the rendered row height for the windowing maths to line up. */
const ROW_HEIGHT = 41
const TABLE_COLUMNS = 11

function isStyle(s: string | undefined): s is ProfileStyle {
  return !!s && (PROFILE_STYLES as readonly string[]).includes(s)
}

function DirBadge({ dir }: { dir: 'BUY' | 'SELL' }) {
  const buy = dir === 'BUY'
  return (
    <span
      className="px-2 py-0.5 rounded-full text-[0.7rem] font-bold whitespace-nowrap"
      style={{
        background: buy ? 'var(--color-profit-bg)' : 'var(--color-loss-bg)',
        color: buy ? 'var(--color-bull)' : 'var(--color-bear)',
      }}
    >
      {buy ? '▲ BUY' : '▼ SELL'}
    </span>
  )
}

/**
 * Memoised row. `quotes` is component state, so EVERY rAF flush re-renders the
 * page — without this, all visible rows and all 11 cells re-run their
 * parseFloat/format work per frame. `PriceCell` isolates the flash, not the
 * render. Only the row whose `ltp` actually changed re-renders now.
 */
const SuggestionRow = memo(function SuggestionRow({
  s,
  ltp,
  rr,
  isTrading,
  halted,
  onDetail,
  onTrade,
}: {
  s: SuggestionOut
  ltp: number | undefined
  rr: number | null
  isTrading: boolean
  halted: boolean
  onDetail: (s: SuggestionOut) => void
  onTrade: (s: SuggestionOut) => void
}) {
  // The 5th Buy surface. It posts a real Signal id into the same paper order path, so it
  // needs the same eligibility verdict as the other four (quant-verifier, 2026-09-02).
  const block = tradeBlock(s, {
    symbol: s.symbol,
    halted,
    isTrading,
    normalTitle: s.direction === 'BUY' ? 'Paper Buy (open long)' : 'Paper Sell (open short)',
    normalAria: `Paper ${s.direction} ${s.symbol}`,
  })
  return (
    <TableRow style={{ height: ROW_HEIGHT }}>
      <TableCell>
        {/* A button, not a clickable row: the drawer has to be reachable by
            keyboard with a visible focus ring. */}
        <button
          type="button"
          onClick={() => onDetail(s)}
          className="font-mono font-bold text-(--color-text) underline decoration-dotted decoration-(--color-border-strong) underline-offset-4 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)"
          aria-label={`Why ${s.symbol} fired`}
        >
          {s.symbol}
        </button>
      </TableCell>
      <TableCell><DirBadge dir={s.direction} /></TableCell>
      <TableCell numeric className="text-(--color-accent)">
        {formatPct(s.confidence_pct, { signed: false })}
      </TableCell>
      <TableCell numeric>{formatCurrency(parseFloat(s.entry_price))}</TableCell>
      <TableCell numeric>
        <PriceCell value={ltp} format={formatCurrency} />
      </TableCell>
      <TableCell numeric style={{ color: 'var(--color-bear)' }}>
        {formatCurrency(parseFloat(s.stop_loss))}
      </TableCell>
      <TableCell numeric style={{ color: 'var(--color-bull)' }}>
        {formatCurrency(parseFloat(s.take_profit))}
      </TableCell>
      <TableCell numeric className="text-(--color-text-secondary)">
        {rr != null ? `${formatGreek(rr, 2)}:1` : '—'}
      </TableCell>
      <TableCell numeric>{formatInt(s.suggested_qty)}</TableCell>
      <TableCell className="text-(--color-text-secondary) whitespace-nowrap">
        {s.profile_name}
      </TableCell>
      <TableCell numeric>
        <Button
          variant="outline"
          size="xs"
          disabled={block.nativeDisabled}
          aria-disabled={block.ariaDisabled}
          onClick={() => {
            if (block.inert) return
            onTrade(s)
          }}
          style={{
            color: block.blocked
              ? 'var(--color-loss)'
              : s.direction === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)',
          }}
          title={block.title}
          aria-label={block.ariaLabel}
        >
          {block.blocked ? block.label : isTrading ? '…' : s.direction === 'BUY' ? '▲ Buy' : '▼ Sell'}
          {block.unknown && (
            <span className="ml-1 text-(--color-warning)">{block.unknownLabel}</span>
          )}
        </Button>
      </TableCell>
    </TableRow>
  )
})

function rewardRisk(s: SuggestionOut): number | null {
  const entry = parseFloat(s.entry_price)
  const risk = Math.abs(entry - parseFloat(s.stop_loss))
  if (!Number.isFinite(risk) || risk === 0) return null
  const reward = Math.abs(parseFloat(s.take_profit) - entry)
  return Number.isFinite(reward) ? reward / risk : null
}

export function StylePage() {
  const { style } = useParams()
  const { accessToken } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const [tradingId, setTradingId] = useState<string | null>(null)
  const [detail, setDetail] = useState<SuggestionOut | null>(null)
  const halted = useTradingHaltStore((s) => s.halted)
  const viewportRef = useRef<HTMLDivElement>(null)

  const valid = isStyle(style)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['suggestions', style],
    queryFn: () => suggestionsApi.getByStyle(style as string, accessToken!),
    enabled: !!accessToken && valid,
    staleTime: 60_000,
  })

  const outcomes = useQuery({
    queryKey: ['outcome-analytics'],
    queryFn: () => analyticsApi.getOutcomes(accessToken!),
    enabled: !!accessToken && valid,
    staleTime: 5 * 60_000,
  })

  const suggestions = useMemo(() => data?.suggestions ?? [], [data])

  // Live LTP for exactly the symbols on screen. useLiveQuotes v2 batches ticks
  // per animation frame, so a full-rate tape costs one render per frame, and
  // PriceCell flashes the single cell instead of re-rendering the row.
  const symbols = useMemo(() => suggestions.map((s) => s.symbol), [suggestions])
  const { quotes } = useLiveQuotes(symbols)

  const win = useVirtualRows(viewportRef, {
    count: suggestions.length,
    rowHeight: ROW_HEIGHT,
  })
  const visible = suggestions.slice(win.startIndex, win.endIndex)

  const paperTrade = useMutation({
    mutationFn: ({ id, dir }: { id: string; dir: 'BUY' | 'SELL' }) =>
      tradingApi.placeOrder({ signal_id: id, side: dir }, accessToken!),
    onSuccess: (order) => {
      toast.success(`Paper ${order.side} placed: ${order.filled_qty} × ${order.symbol}`)
      void qc.invalidateQueries({ queryKey: ['positions-open'] })
      void qc.invalidateQueries({ queryKey: ['paper-record'] })
      setTradingId(null)
    },
    onError: (err: { message?: string }) => {
      toast.error(err.message ?? 'Order rejected')
      setTradingId(null)
    },
  })

  // Stable identity, or every memoised row re-renders on each parent render.
  const handleTrade = useCallback(
    (s: SuggestionOut) => {
      if (halted) {
        toast.error('Trading is halted — release the kill switch on Go Live.')
        return
      }
      setTradingId(s.id)
      paperTrade.mutate({ id: s.id, dir: s.direction })
    },
    // `toast` and the mutation object are recreated per render; the mutate fn
    // and the halt flag are what actually matter here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [halted, paperTrade.mutate],
  )

  if (!valid) {
    return (
      <div className="max-w-md">
        <EmptyState
          title="Unknown style"
          description={`"${style}" is not a trading style — pick Intraday, Swing, F&O or Investment.`}
        />
      </div>
    )
  }

  const meta = STYLE_META[style as ProfileStyle]
  const styleStats = outcomes.data?.styles.find((s) => s.style === style)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={`${meta.label} suggestions`} subtitle={meta.desc} />

      <StyleStatsHeader
        stats={styleStats}
        statsLoading={outcomes.isLoading}
        suggestions={suggestions}
      />

      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between gap-2 flex-wrap">
          <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            {meta.icon} {meta.label}
            <span
              className="px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider"
              style={{ background: 'var(--color-profit-bg)', color: 'var(--color-bull)' }}
              title="Scored on COMPLETE candles and valid from the next one — the tradeable layer. Contrast with the provisional leaderboard below."
            >
              COMMITTED
            </span>
          </span>
          {data && (
            <span className="text-xs text-(--color-text-muted)">
              {data.total} suggestion{data.total !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {isLoading && (
          <div className="p-4 space-y-2" aria-label="loading suggestions">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </div>
        )}

        {isError && (
          <div className="p-4 text-sm text-(--color-text-muted)">
            Could not load {meta.label} suggestions.{' '}
            <Button variant="link" size="sm" onClick={() => void refetch()}>Retry</Button>
          </div>
        )}

        {!isLoading && !isError && suggestions.length === 0 && (
          <EmptyState
            title={`No ${meta.label} suggestions right now`}
            description={EMPTY_REASON[style as ProfileStyle]}
          />
        )}

        {!isLoading && suggestions.length > 0 && (
          <VirtualViewport ref={viewportRef} className="max-h-[65vh]">
            <Table aria-label={`${meta.label} committed suggestions`}>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Dir</TableHead>
                  <TableHead numeric>Conf</TableHead>
                  <TableHead numeric>Entry</TableHead>
                  <TableHead numeric>LTP</TableHead>
                  <TableHead numeric>SL</TableHead>
                  <TableHead numeric>TP</TableHead>
                  <TableHead numeric>R:R</TableHead>
                  <TableHead numeric>Qty</TableHead>
                  <TableHead>Profile</TableHead>
                  <TableHead numeric>Trade</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <VirtualSpacer height={win.padTop} colSpan={TABLE_COLUMNS} />
                {visible.map((s) => (
                  <SuggestionRow
                    key={s.id}
                    s={s}
                    ltp={quotes[s.symbol]?.ltp}
                    rr={rewardRisk(s)}
                    isTrading={tradingId === s.id}
                    halted={halted}
                    onDetail={setDetail}
                    onTrade={handleTrade}
                  />
                ))}
                <VirtualSpacer height={win.padBottom} colSpan={TABLE_COLUMNS} />
              </TableBody>
            </Table>
          </VirtualViewport>
        )}
      </div>

      {/* Forming layer — the same frozen engine on the still-forming candle. */}
      <ProvisionalPanel style={style as ProfileStyle} />

      <FactorDrawer suggestion={detail} onClose={() => setDetail(null)} />
    </div>
  )
}

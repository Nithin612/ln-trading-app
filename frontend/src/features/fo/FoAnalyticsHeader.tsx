/**
 * F&O analytics strip — spot/ATM, PCR, max pain, basis, IV-rank, VIX regime.
 *
 * Every tile states what it is measured from. The VIX band is the engine's
 * HARD, fail-closed veto on option selling, so "unknown" is rendered as a
 * stand-down state, not as a blank — a blind safety gate must never look OK.
 */

import type { FoAnalytics, IvRank } from '@/lib/api/fo'
import { formatINR, formatLakh, formatPct } from '@/lib/format'
import { Skeleton } from '@/components/ui/skeleton'

interface TileProps {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  tone?: 'neutral' | 'profit' | 'loss' | 'warn'
  title?: string
}

function Tile({ label, value, sub, tone = 'neutral', title }: TileProps) {
  const color =
    tone === 'profit'
      ? 'var(--color-profit)'
      : tone === 'loss'
        ? 'var(--color-loss)'
        : tone === 'warn'
          ? 'var(--color-warning)'
          : 'var(--color-text)'
  return (
    <div
      className="px-3 py-2 rounded-lg bg-(--color-surface-2) border border-(--color-border) min-w-0"
      title={title}
    >
      <div className="text-[0.65rem] uppercase tracking-wider text-(--color-text-muted) truncate">
        {label}
      </div>
      <div className="text-sm font-semibold tabular-nums truncate" style={{ color }}>
        {value}
      </div>
      {sub && (
        <div className="text-[0.65rem] text-(--color-text-muted) tabular-nums truncate">{sub}</div>
      )}
    </div>
  )
}

/** IV-rank ≥ 50 is the engine's "vol is rich enough to sell" gate. */
function ivRankTone(rank: number): TileProps['tone'] {
  return rank >= 50 ? 'profit' : 'neutral'
}

const VIX_COPY: Record<string, { tone: TileProps['tone']; note: string }> = {
  low: { tone: 'neutral', note: 'calm regime' },
  normal: { tone: 'neutral', note: 'normal regime' },
  high: { tone: 'loss', note: 'selling vetoed' },
}

interface Props {
  analytics: FoAnalytics | undefined
  ivRank: IvRank | undefined
  /** True while IV-rank is loading; a 404 means "not enough history", not an error. */
  ivRankMissing: boolean
  isLoading: boolean
}

export function FoAnalyticsHeader({ analytics, ivRank, ivRankMissing, isLoading }: Props) {
  if (isLoading) {
    return (
      <div
        className="grid gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6"
        aria-label="loading F&O analytics"
      >
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
      </div>
    )
  }
  if (!analytics) return null

  const { pcr, basis, vix, spot, atm_strike, max_pain } = analytics
  const vixCopy = vix ? VIX_COPY[vix.band] : undefined

  return (
    <div className="grid gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
      <Tile
        label="Spot / ATM"
        value={spot ? `₹${formatINR(parseFloat(spot))}` : '—'}
        sub={atm_strike ? `ATM ${formatINR(parseFloat(atm_strike))}` : 'no ATM'}
        title="Underlying close from the futures row; ATM = nearest strike"
      />
      <Tile
        label="PCR (OI)"
        value={pcr.pcr_oi != null ? formatINR(pcr.pcr_oi) : '—'}
        sub={
          pcr.pcr_volume != null
            ? `vol ${formatINR(pcr.pcr_volume)}`
            : 'volume PCR undefined'
        }
        title={`Put OI ${formatLakh(pcr.total_pe_oi)} / Call OI ${formatLakh(pcr.total_ce_oi)}`}
      />
      <Tile
        label="Max pain"
        value={max_pain ? formatINR(parseFloat(max_pain)) : '—'}
        sub="writer-payout minimum"
        title="The strike where the most option value expires worthless"
      />
      <Tile
        label="Basis"
        value={basis ? `${formatINR(parseFloat(basis.basis))}` : '—'}
        sub={basis ? formatPct(basis.basis_pct) : 'no futures close'}
        tone={basis ? (basis.basis_pct >= 0 ? 'profit' : 'loss') : 'neutral'}
        title="Futures − underlying (carry). Positive = contango."
      />
      <Tile
        label="IV rank"
        value={ivRank ? formatPct(ivRank.rank, { signed: false }) : '—'}
        sub={
          ivRank
            ? `IV ${formatPct(ivRank.current_iv * 100, { signed: false })} · ${ivRank.sample}d`
            : ivRankMissing
              ? 'not enough history'
              : '—'
        }
        tone={ivRank ? ivRankTone(ivRank.rank) : 'neutral'}
        title="Where today's ATM IV sits in its trailing range. The engine sells only when rank ≥ 50."
      />
      <Tile
        label="India VIX"
        value={vix ? formatINR(parseFloat(vix.current)) : 'unknown'}
        sub={
          vix
            ? `${vixCopy?.note} · p${formatPct(vix.percentile, { signed: false })}`
            : 'selling vetoed (fail-closed)'
        }
        tone={vix ? vixCopy?.tone : 'warn'}
        title={
          vix
            ? 'Volatility regime from the India VIX percentile. A high band vetoes option selling.'
            : 'No VIX history recorded — the veto fails CLOSED, so selling stands down.'
        }
      />
    </div>
  )
}

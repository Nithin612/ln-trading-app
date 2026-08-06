/**
 * Per-style stats header (Phase 5 slice 5.3).
 *
 * Two rows of truth, kept separate on purpose:
 *  - **Tracked outcomes** for this style from `/analytics/outcomes` — what
 *    actually happened to past suggestions.
 *  - **Right now** — the shape of the live suggestion list on screen.
 *
 * Sample size is rendered next to every rate, not hidden in a tooltip. The
 * daily-analysis evidence (1 of 15 trades reached +1R over 08-03→05) is exactly
 * the regime where a hit rate off a handful of outcomes looks like an edge and
 * isn't — so a rate computed from fewer than MIN_HONEST_SAMPLE outcomes is
 * shown greyed with an explicit "n too small" note rather than coloured as
 * good or bad.
 */

import type { OutcomeStyleStats } from '@/lib/api/analytics'
import type { SuggestionOut } from '@/lib/api/suggestions'
import { formatINR, formatPct } from '@/lib/format'
import { Skeleton } from '@/components/ui/skeleton'

/** Below this many tracked outcomes, a rate is noise — say so, don't colour it. */
export const MIN_HONEST_SAMPLE = 20

interface StatProps {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  tone?: 'neutral' | 'profit' | 'loss' | 'muted'
  title?: string
}

function Stat({ label, value, sub, tone = 'neutral', title }: StatProps) {
  const color =
    tone === 'profit'
      ? 'var(--color-profit)'
      : tone === 'loss'
        ? 'var(--color-loss)'
        : tone === 'muted'
          ? 'var(--color-text-muted)'
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

interface Props {
  stats: OutcomeStyleStats | undefined
  statsLoading: boolean
  suggestions: SuggestionOut[]
}

export function StyleStatsHeader({ stats, statsLoading, suggestions }: Props) {
  const buys = suggestions.filter((s) => s.direction === 'BUY').length
  const sells = suggestions.length - buys
  const avgConfidence =
    suggestions.length > 0
      ? suggestions.reduce((t, s) => t + s.confidence_pct, 0) / suggestions.length
      : null

  const enoughSample = (stats?.sample ?? 0) >= MIN_HONEST_SAMPLE
  const hitRate = stats?.hit_rate ?? null
  const avgReturn = stats?.avg_return_pct ?? null

  return (
    <div className="grid gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
      {statsLoading ? (
        Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={`s${i}`} className="h-16 w-full" />
        ))
      ) : (
        <>
          <Stat
            label="Hit rate"
            value={hitRate != null ? formatPct(hitRate, { signed: false }) : '—'}
            sub={
              stats
                ? enoughSample
                  ? `${stats.wins}W / ${stats.losses}L · n=${stats.sample}`
                  : `n=${stats.sample} — too small to read`
                : 'no tracked outcomes yet'
            }
            tone={
              hitRate == null || !enoughSample
                ? 'muted'
                : hitRate >= 50
                  ? 'profit'
                  : 'loss'
            }
            title="Share of ENTERED suggestions that hit target before stop. Tracked outcomes only — not a backtest."
          />
          <Stat
            label="Entry rate"
            value={stats?.entry_rate != null ? formatPct(stats.entry_rate, { signed: false }) : '—'}
            sub={stats ? `${stats.entered} entered of ${stats.total}` : '—'}
            tone="neutral"
            title="How often the entry zone was actually touched before the signal expired. A low entry rate means the entries are priced too far away."
          />
          <Stat
            label="Avg return"
            value={avgReturn != null ? formatPct(avgReturn) : '—'}
            sub={
              stats
                ? enoughSample
                  ? `over n=${stats.sample}`
                  : `n=${stats.sample} — too small to read`
                : '—'
            }
            tone={
              avgReturn == null || !enoughSample ? 'muted' : avgReturn >= 0 ? 'profit' : 'loss'
            }
            title="Mean realised return per tracked outcome for this style."
          />
        </>
      )}

      <Stat
        label="Live now"
        value={suggestions.length}
        sub="committed suggestions"
        title="Committed suggestions currently on screen — from complete candles only."
      />
      <Stat
        label="Direction"
        value={
          <span>
            <span style={{ color: 'var(--color-bull)' }}>▲ {buys}</span>
            {' / '}
            <span style={{ color: 'var(--color-bear)' }}>▼ {sells}</span>
          </span>
        }
        sub="buy / sell split"
      />
      <Stat
        label="Avg confidence"
        value={avgConfidence != null ? formatPct(avgConfidence, { signed: false }) : '—'}
        sub={avgConfidence != null ? `${formatINR(avgConfidence)} weighted score` : 'no signals'}
        title="Mean confluence score of the suggestions listed. The engine's gate is 70%."
      />
    </div>
  )
}

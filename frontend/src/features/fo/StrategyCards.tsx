/**
 * Option-selling candidate cards (Phase 4 slice 4.3 engine → Phase 5 UI).
 *
 * Honesty rules carried over from docs/phases/phase-04-fo-suggestions.md — the
 * UI must not overstate what the engine claims:
 *
 * - **Forward-tested, not backtested.** Recorded chain history is thin and POP
 *   is a forward claim, so the panel says so out loud.
 * - **Expectancy is REPORT-ONLY, never a gate.** Under a risk-neutral
 *   (breakeven `N(d2)`) POP, a fairly-priced credit spread's expectancy is ~0
 *   by construction, and the shipped estimator is deliberately
 *   negative-biased — so a small negative number is EXPECTED, not a red flag.
 *   Rendering it bare, in loss red, would read as "this trade loses money".
 *   The real edge is the volatility risk premium, proxied by the IV-rank gate.
 * - **Suggestions only.** There is no order button here: F&O execution does not
 *   exist (live trading is Phase 7) and the engine never auto-trades.
 */

import type { SpreadCandidate, SpreadStructure } from '@/lib/api/fo'
import { formatGreek, formatINR, formatPct } from '@/lib/format'
import { EmptyState } from '@/components/ui/empty-state'

const STRUCTURE_LABEL: Record<SpreadStructure, string> = {
  bull_put: 'Bull put spread',
  bear_call: 'Bear call spread',
  iron_condor: 'Iron condor',
}

const STRUCTURE_BIAS: Record<SpreadStructure, string> = {
  bull_put: 'mildly bullish · sells downside',
  bear_call: 'mildly bearish · sells upside',
  iron_condor: 'neutral · sells both wings',
}

function Metric({
  label,
  value,
  tone = 'neutral',
  title,
}: {
  label: string
  value: React.ReactNode
  tone?: 'neutral' | 'profit' | 'loss'
  title?: string
}) {
  const color =
    tone === 'profit'
      ? 'var(--color-profit)'
      : tone === 'loss'
        ? 'var(--color-loss)'
        : 'var(--color-text)'
  return (
    <div className="min-w-0" title={title}>
      <div className="text-[0.65rem] uppercase tracking-wider text-(--color-text-muted) truncate">
        {label}
      </div>
      <div className="text-sm font-semibold tabular-nums truncate" style={{ color }}>
        {value}
      </div>
    </div>
  )
}

function LegRow({ leg }: { leg: SpreadCandidate['legs'][number] }) {
  const isSell = leg.action === 'sell'
  return (
    <li className="flex items-center gap-2 text-xs font-mono">
      <span
        className="px-1.5 py-0.5 rounded font-bold"
        style={{
          background: isSell ? 'var(--color-loss-bg)' : 'var(--color-profit-bg)',
          color: isSell ? 'var(--color-bear)' : 'var(--color-bull)',
        }}
      >
        {isSell ? '▼ SELL' : '▲ BUY'}
      </span>
      <span className="text-(--color-text)">
        {formatINR(parseFloat(leg.strike))} {leg.option_type}
      </span>
      <span className="text-(--color-text-muted)">@ {formatINR(parseFloat(leg.premium))}</span>
    </li>
  )
}

function CandidateCard({ c }: { c: SpreadCandidate }) {
  const expectancy = parseFloat(c.expectancy)
  return (
    <article className="rounded-lg border border-(--color-border) bg-(--color-surface-2) p-4 flex flex-col gap-3">
      <header className="flex items-start justify-between gap-2 flex-wrap">
        <div className="min-w-0">
          <h3 className="text-sm font-bold text-(--color-text)">{STRUCTURE_LABEL[c.structure]}</h3>
          <p className="text-[0.7rem] text-(--color-text-muted)">{STRUCTURE_BIAS[c.structure]}</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-(--color-text-muted)">
            {c.expiry} · {c.dte}d
          </div>
          <div className="text-[0.7rem] text-(--color-text-muted) tabular-nums">
            short Δ {formatGreek(Math.abs(c.short_delta))}
          </div>
        </div>
      </header>

      <ul className="flex flex-col gap-1">
        {c.legs.map((leg, i) => (
          <LegRow key={`${leg.action}-${leg.option_type}-${leg.strike}-${i}`} leg={leg} />
        ))}
      </ul>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 border-t border-(--color-border)">
        <Metric
          label="Net credit"
          value={`₹${formatINR(parseFloat(c.net_credit))}`}
          tone="profit"
          title="Premium received after a conservative per-leg fill haircut"
        />
        <Metric
          label="Max loss"
          value={`₹${formatINR(parseFloat(c.max_loss))}`}
          tone="loss"
          title="Width − credit. Defined risk: this is the worst case at expiry."
        />
        <Metric
          label="POP"
          value={formatPct(c.pop * 100, { signed: false })}
          title="Risk-neutral probability of finishing on the profitable side of the breakeven (Black-76 N(d2)). A forward claim, not a guarantee."
        />
        <Metric
          label="Return on margin"
          value={formatPct(c.return_on_margin * 100, { signed: false })}
          title="Credit ÷ max loss (defined-risk margin proxy; Kite SPAN refinement is a follow-up)"
        />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <Metric
          label="Breakeven"
          value={c.breakevens.map((b) => formatINR(parseFloat(b))).join(' / ')}
        />
        <Metric label="Width" value={formatINR(parseFloat(c.width))} />
        <Metric
          label="Margin est."
          value={`₹${formatINR(parseFloat(c.margin_est))}`}
          title="Defined-risk upper bound = max loss"
        />
        <Metric
          label="Expectancy"
          value={
            <span className="text-(--color-text-muted)">
              ₹{formatINR(expectancy)}
              <span className="ml-1 text-[0.6rem] uppercase">report-only</span>
            </span>
          }
          title="Risk-neutral expectancy is ~0 by construction and this estimator is deliberately negative-biased — a small negative value on a fairly-priced spread is EXPECTED. The edge is the volatility risk premium (gated by IV-rank), which prices cannot prove."
        />
      </div>

      <div className="text-xs text-(--color-text-muted) border-t border-(--color-border) pt-2">
        <div className="font-semibold text-(--color-text-secondary) mb-0.5">Mechanical exit</div>
        take profit at ₹{formatINR(parseFloat(c.exit_plan.take_profit_credit))} credit · stop at ₹
        {formatINR(parseFloat(c.exit_plan.stop_loss_amount))} · time stop {c.exit_plan.time_stop_dte}{' '}
        DTE
      </div>

      {c.rationale && (
        <p className="text-xs text-(--color-text-secondary) italic">{c.rationale}</p>
      )}
    </article>
  )
}

interface Props {
  symbol: string
  candidates: SpreadCandidate[] | undefined
  isLoading: boolean
  isError: boolean
}

export function StrategyCards({ symbol, candidates, isLoading, isError }: Props) {
  if (isLoading) {
    return (
      <div className="text-sm text-(--color-text-muted)" aria-label="loading option-selling candidates">
        Scanning {symbol} for defined-risk credit structures…
      </div>
    )
  }
  if (isError) {
    return (
      <div className="text-sm text-(--color-text-muted)">
        Could not load option-selling candidates for {symbol}.
      </div>
    )
  }
  if (!candidates || candidates.length === 0) {
    return (
      <EmptyState
        title="No candidates clear the gates"
        description={
          'An empty list is a valid, deliberate answer — a safe "no trade" stance. ' +
          'The v1 rules are intentionally selective (index-only, IV-rank ≥ 50, ~0.16Δ short strike, ' +
          'credit ≥ 30% of width, POP ≥ 0.65, DTE 20–45) and the India-VIX veto fails CLOSED, ' +
          'standing down when the regime is high OR unknown.'
        }
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-(--color-text-muted)">
        <span className="font-semibold text-(--color-warning)">Forward-tested, not backtested.</span>{' '}
        Recorded option history is thin, and POP is a forward claim — these are ranked suggestions
        (by return-on-margin × POP), never orders. F&O execution does not exist yet (Phase 7).
      </p>
      <div className="grid gap-3 lg:grid-cols-2">
        {candidates.map((c, i) => (
          <CandidateCard key={`${c.structure}-${c.expiry}-${i}`} c={c} />
        ))}
      </div>
    </div>
  )
}

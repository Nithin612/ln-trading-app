/**
 * Factor-breakdown drawer (Phase 5 slice 5.3) — why this suggestion fired.
 *
 * The confluence engine is the platform's edge and it is deliberately NOT a
 * black box: this shows every factor's weight, its score, its weighted
 * contribution, and the engine's own explanation string, so a suggestion can
 * be argued with rather than trusted blindly.
 *
 * Contribution = weight × score, matching how the scorer aggregates. Factors
 * are ordered by absolute contribution, so what actually drove the decision is
 * at the top rather than buried in alphabetical order.
 */

import type { SuggestionOut } from '@/lib/api/suggestions'
import { formatGreek, formatINR, formatPct } from '@/lib/format'
import { Drawer } from '@/components/ui/drawer'

interface Props {
  suggestion: SuggestionOut | null
  onClose: () => void
}

function riskReward(s: SuggestionOut): number | null {
  const entry = parseFloat(s.entry_price)
  const sl = parseFloat(s.stop_loss)
  const tp = parseFloat(s.take_profit)
  const risk = Math.abs(entry - sl)
  if (!Number.isFinite(risk) || risk === 0) return null
  const reward = Math.abs(tp - entry)
  if (!Number.isFinite(reward)) return null
  return reward / risk
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <span className="text-(--color-text-muted)">{label}</span>
      <span className="font-semibold tabular-nums text-(--color-text)">{value}</span>
    </div>
  )
}

export function FactorDrawer({ suggestion, onClose }: Props) {
  const s = suggestion
  const factors = s
    ? Object.entries(s.factor_scores)
        .map(([name, f]) => ({ name, ...f, contribution: f.weight * f.score }))
        .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    : []
  const maxAbs = factors.reduce((m, f) => Math.max(m, Math.abs(f.contribution)), 0)
  const rr = s ? riskReward(s) : null

  return (
    <Drawer
      open={s !== null}
      onClose={onClose}
      title={s ? `${s.symbol} — ${s.direction} (${formatPct(s.confidence_pct, { signed: false })})` : ''}
      width={560}
    >
      {s && (
        <div className="flex flex-col gap-4">
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-(--color-text-muted) mb-1">
              Plan
            </h3>
            <Row label="Entry" value={`₹${formatINR(parseFloat(s.entry_price))}`} />
            <Row label="Stop loss" value={`₹${formatINR(parseFloat(s.stop_loss))}`} />
            <Row label="Take profit" value={`₹${formatINR(parseFloat(s.take_profit))}`} />
            <Row label="Suggested qty" value={formatINR(s.suggested_qty)} />
            <Row label="Reward : risk" value={rr != null ? `${formatGreek(rr, 2)} : 1` : '—'} />
            <Row
              label="Profile"
              value={`${s.profile_name} v${s.profile_version}`}
            />
            <Row label="Classification" value={`${s.classification} · ${s.timeframe}`} />
            <Row label="Valid until" value={new Date(s.validity_until).toLocaleString('en-IN')} />
            {s.volatility_reduced && (
              <p className="mt-1 text-xs text-(--color-warning)">
                Size was reduced for volatility.
              </p>
            )}
          </section>

          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-(--color-text-muted) mb-1">
              Factor breakdown
            </h3>
            {factors.length === 0 ? (
              <p className="text-sm text-(--color-text-muted)">
                No factor breakdown was recorded for this suggestion.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {factors.map((f) => {
                  const pct = maxAbs > 0 ? Math.round((Math.abs(f.contribution) / maxAbs) * 100) : 0
                  const positive = f.contribution >= 0
                  return (
                    <li key={f.name}>
                      <div className="flex items-baseline justify-between gap-2 text-xs">
                        <span className="font-semibold text-(--color-text)">{f.name}</span>
                        <span className="tabular-nums text-(--color-text-muted)">
                          w {formatGreek(f.weight, 2)} × {formatGreek(f.score, 2)} ={' '}
                          <span
                            style={{
                              color: positive ? 'var(--color-profit)' : 'var(--color-loss)',
                            }}
                          >
                            {positive ? '+' : ''}
                            {formatGreek(f.contribution, 2)}
                          </span>
                        </span>
                      </div>
                      {/* Bar length = share of the largest contribution. */}
                      <div
                        className="mt-0.5 h-1 rounded-sm bg-(--color-surface-3)"
                        aria-hidden="true"
                      >
                        <div
                          className="h-1 rounded-sm"
                          style={{
                            width: `${pct}%`,
                            background: positive
                              ? 'var(--color-profit)'
                              : 'var(--color-loss)',
                          }}
                        />
                      </div>
                      {f.explanation && (
                        <p className="mt-0.5 text-xs text-(--color-text-secondary)">
                          {f.explanation}
                        </p>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </section>

          {s.setup_trigger && Object.keys(s.setup_trigger).length > 0 && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-(--color-text-muted) mb-1">
                Setup trigger
              </h3>
              <ul className="flex flex-col gap-0.5 text-xs">
                {Object.entries(s.setup_trigger).map(([k, v]) => (
                  <li key={k} className="flex items-baseline justify-between gap-3">
                    <span className="text-(--color-text-muted)">{k}</span>
                    <span className="tabular-nums text-(--color-text)">{String(v)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </Drawer>
  )
}

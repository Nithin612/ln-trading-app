import type { CSSProperties } from 'react'
import { useQuery } from '@tanstack/react-query'

import { useAuth } from '@/hooks/useAuth'
import { formatCurrency, formatINR, formatInt, formatPct, formatScore } from '@/lib/format'
import { outcomeApi, signalsApi } from '@/lib/api/signals'
import type { ConfidenceBreakdown, SignalOut, SignalOutcome } from '@/lib/api/signals'

interface Props {
  signal: SignalOut
  onClose: () => void
}

// Outcome ladder → label + tone (glyph + color, never color alone).
const OUTCOME_LABELS: Record<SignalOutcome['status'], { label: string; color: string }> = {
  open: { label: '· awaiting entry', color: 'var(--color-text-muted)' },
  entry_touched: { label: '◆ entry touched', color: 'var(--color-accent)' },
  tp_first: { label: '▲ target hit', color: 'var(--color-profit)' },
  sl_first: { label: '▼ stopped out', color: 'var(--color-loss)' },
  expired_untouched: { label: '— expired, never entered', color: 'var(--color-text-muted)' },
  expired_open: { label: '— expired after entry', color: 'var(--color-text-muted)' },
}

// Forecast horizon per classification (validity per .claude/rules/trading-domain.md). The card
// labels it because a confidence figure with no horizon invites reading a multi-day setup on a
// one-day clock (docs/analysis/horizon-recovery-2026-08-25.md).
const HORIZON: Record<string, string> = {
  scalp: '30 minutes',
  intraday: 'until 3:15 PM IST',
  swing: '5 trading days',
  positional: '30 trading days',
}

function istTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit',
  })
}

function humanize(token: string): string {
  return token.replace(/_/g, ' ').toLowerCase()
}

function OutcomeSection({ signalId }: { signalId: string }) {
  const { accessToken } = useAuth()
  const query = useQuery({
    queryKey: ['signal-outcome', signalId],
    queryFn: () => outcomeApi.getOutcome(signalId, accessToken ?? ''),
    enabled: accessToken !== null,
    staleTime: 30_000,
  })
  if (query.isLoading || query.isError) return null // enrichment only — never block the modal
  const outcome = query.data
  if (!outcome) return null // no row yet (lazily written)
  const tone = OUTCOME_LABELS[outcome.status] ?? OUTCOME_LABELS.open
  const touches = [
    outcome.entry_touched_at
      ? `entry ${formatCurrency(Number(outcome.entry_touch_price ?? 0))} at ${istTime(outcome.entry_touched_at)}`
      : null,
    outcome.tp_touched_at
      ? `TP ${formatCurrency(Number(outcome.tp_touch_price ?? 0))} at ${istTime(outcome.tp_touched_at)}`
      : null,
    outcome.sl_touched_at
      ? `SL ${formatCurrency(Number(outcome.sl_touch_price ?? 0))} at ${istTime(outcome.sl_touched_at)}`
      : null,
  ].filter(Boolean)
  return (
    <div
      style={{
        background: 'var(--color-surface-3)', borderRadius: 'var(--radius-md)',
        padding: '0.625rem', marginBottom: '1.25rem',
        display: 'flex', gap: '0.75rem', alignItems: 'baseline', flexWrap: 'wrap',
      }}
    >
      <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Outcome
      </span>
      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: tone.color }}>
        {tone.label}
      </span>
      {touches.length > 0 && (
        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
          {touches.join(' · ')}
        </span>
      )}
    </div>
  )
}

const SECTION_LABEL: CSSProperties = {
  fontSize: '0.75rem', color: 'var(--color-text-muted)',
  textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem',
}

function signed(n: number, dp = 1): string {
  return `${n >= 0 ? '+' : ''}${formatScore(n, dp)}`
}

// U17 — the vote as one stacked bar: each scoring factor's SHARE of the total contribution.
// A single tall segment is the SRTL tell — 82% carried by one factor looks nothing like 82%
// from four. Direction gives the colour; the caption + per-segment title give the non-colour cue.
function DistributionBar({ b }: { b: ConfidenceBreakdown }) {
  const dir = b.direction === 'SELL' ? 'var(--color-bear)' : 'var(--color-bull)'
  const totalAbs = b.scoring.reduce((s, c) => s + Math.abs(c.contribution), 0)
  const dominant = b.scoring.length
    ? Math.max(...b.scoring.map((c) => Math.abs(c.contribution))) / (totalAbs || 1)
    : 0
  return (
    <div style={{ marginBottom: '0.5rem' }}>
      <div
        role="img"
        aria-label={`${b.scoring.length} factors voted for this ${b.direction} signal; the largest is ${formatPct(dominant * 100, { signed: false })} of the score`}
        style={{
          display: 'flex', height: '1.5rem', borderRadius: 'var(--radius-sm)',
          overflow: 'hidden', border: '1px solid var(--color-border)',
        }}
      >
        {b.scoring.map((c, i) => {
          const share = Math.abs(c.contribution) / (totalAbs || 1)
          return (
            <div
              key={c.name}
              title={`${humanize(c.name)}: ${formatPct(share * 100, { signed: false })} of the score`}
              style={{
                flexGrow: share, flexBasis: 0, minWidth: share > 0.06 ? undefined : '3px',
                background: dir, opacity: 0.55 + 0.45 * share,
                borderRight: i < b.scoring.length - 1 ? '1px solid var(--color-surface-2)' : undefined,
              }}
            />
          )
        })}
      </div>
      <p style={{ fontSize: '0.7rem', color: 'var(--color-text-secondary)', marginTop: '0.35rem' }}>
        {b.scoring.length} of {b.scoring.length + b.abstained.length} factors voted
        {dominant >= 0.5 && b.scoring.length > 1
          ? ` — one factor carries ${formatPct(dominant * 100, { signed: false })} of it`
          : ''}
        {b.scoring.length === 1 ? ' — a single indicator carries the entire score' : ''}
      </p>
    </div>
  )
}

// U10 — the arithmetic, rendered so the normalising division is visible: abstainers DROP OUT of
// the divisor, which is exactly how one 0.8 factor reads 80% and clears the ≥70% gate (SRTL).
function ArithmeticCard({ b }: { b: ConfidenceBreakdown }) {
  const dir = b.direction === 'SELL' ? 'var(--color-bear)' : 'var(--color-bull)'
  const td: CSSProperties = { padding: '0.2rem 0', fontVariantNumeric: 'tabular-nums' }
  const num: CSSProperties = { ...td, textAlign: 'right', fontFamily: 'var(--font-mono)' }
  return (
    <div
      style={{
        background: 'var(--color-surface-3)', borderRadius: 'var(--radius-md)',
        padding: '0.75rem', marginBottom: '0.75rem',
      }}
    >
      <table style={{ width: '100%', fontSize: '0.75rem', color: 'var(--color-text)', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ color: 'var(--color-text-secondary)' }}>
            <th style={{ ...td, textAlign: 'left' }}>factor</th>
            <th style={num}>weight</th>
            <th style={num}>score</th>
            <th style={num}>contribution</th>
          </tr>
        </thead>
        <tbody>
          {b.scoring.map((c) => (
            <tr key={c.name} style={{ borderTop: '1px solid var(--color-border)' }}>
              <td style={{ ...td, textAlign: 'left' }}>{humanize(c.name)}</td>
              <td style={num}>{formatInt(c.weight)}</td>
              <td style={num}>{formatScore(c.score, 2)}</td>
              {/* Direction accent (bull/bear token). Direction is ALSO carried by the +/- sign and
                  the "N% BUY/SELL" line below, so this is not colour-alone; the bull/bear-on-surface
                  pair is a known app-wide sub-AA accent (ui-reviewer 2026-09-09). */}
              <td style={{ ...num, color: dir }}>{signed(c.contribution)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr style={{ borderTop: '2px solid var(--color-border)', color: 'var(--color-text-secondary)' }}>
            <td style={{ ...td, textAlign: 'left' }} colSpan={3}>Σ contribution (numerator)</td>
            <td style={{ ...num, color: 'var(--color-text)' }}>{signed(b.numerator)}</td>
          </tr>
          <tr style={{ color: 'var(--color-text-secondary)' }}>
            <td style={{ ...td, textAlign: 'left' }} colSpan={3}>Σ weight of scoring factors (divisor)</td>
            <td style={{ ...num, color: 'var(--color-text)' }}>{formatInt(b.denominator)}</td>
          </tr>
        </tfoot>
      </table>
      <div
        style={{
          marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--color-border)',
          fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--color-text)',
        }}
      >
        {signed(b.numerator)} ÷ {formatInt(b.denominator)} = {formatScore(b.normalized, 3)}
        {'  →  '}
        <strong style={{ color: dir }}>{b.confidence_pct}% {b.direction}</strong>
      </div>
      {b.abstained.length > 0 && (
        <p style={{ fontSize: '0.7rem', color: 'var(--color-text-secondary)', marginTop: '0.4rem' }}>
          ⚠ {b.abstained.length} factor{b.abstained.length > 1 ? 's' : ''} abstained (
          {b.abstained.map((a) => humanize(a.name)).join(', ')}) — a 0-score factor DROPS OUT of
          the divisor, it does not dilute the number.
        </p>
      )}
    </div>
  )
}

export function SignalDetailModal({ signal, onClose }: Props) {
  const { accessToken } = useAuth()

  // Fetch the full detail for the server-authored confidence breakdown (U10/U15/U17). The signal
  // handed in is usually a list row, which omits it (the list stays lean). Enrichment only —
  // never blocks the modal; on error we fall back to what the prop already carries.
  const detailQuery = useQuery({
    queryKey: ['signal-detail', signal.id],
    queryFn: () => signalsApi.getById(signal.id, accessToken ?? ''),
    enabled: accessToken !== null,
    staleTime: 30_000,
  })
  const breakdown: ConfidenceBreakdown | null =
    detailQuery.data?.confidence_breakdown ?? signal.confidence_breakdown ?? null

  const rr = (
    (parseFloat(signal.take_profit) - parseFloat(signal.entry_price)) /
    Math.abs(parseFloat(signal.entry_price) - parseFloat(signal.stop_loss))
  )

  // U15 — named evidence in plain language. Prefer the triggering pattern/indicator names; fall
  // back to the scoring factor names so a thin, single-factor signal READS thin instantly.
  const evidence = [
    ...(signal.triggering_patterns ?? []),
    ...(signal.triggering_indicators ?? []),
  ].map(humanize)
  const evidenceFallback = breakdown?.scoring.map((c) => humanize(c.name)) ?? []
  const evidenceLine = (evidence.length ? evidence : evidenceFallback).join(' · ')

  const validUntil = new Date(signal.validity_until).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--color-surface-2)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          width: '100%', maxWidth: '680px',
          maxHeight: '90vh', overflowY: 'auto',
          padding: '1.5rem',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
              <span
                style={{
                  fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '1.125rem',
                  color: 'var(--color-text)',
                }}
              >
                {signal.symbol}
              </span>
              <span
                style={{
                  padding: '2px 8px', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 600,
                  background: signal.direction === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)',
                  color: 'var(--color-primary-foreground)',
                }}
              >
                {signal.direction}
              </span>
              <span
                style={{
                  padding: '2px 8px', borderRadius: '9999px', fontSize: '0.75rem',
                  background: 'var(--color-surface-3)', color: 'var(--color-text-muted)',
                }}
              >
                {signal.classification}
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              {signal.headline}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--color-text-muted)', fontSize: '1.25rem', lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Outcome ledger (3.6) — shown once anything is recorded */}
        <OutcomeSection signalId={signal.id} />

        {/* Key metrics */}
        <div
          style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '0.75rem', marginBottom: '1.25rem',
          }}
        >
          {[
            { label: 'Entry', value: `₹${formatINR(parseFloat(signal.entry_price))}` },
            { label: 'Stop Loss', value: `₹${formatINR(parseFloat(signal.stop_loss))}`, color: 'var(--color-bear)' },
            { label: 'Target', value: `₹${formatINR(parseFloat(signal.take_profit))}`, color: 'var(--color-bull)' },
            { label: 'R:R', value: Number.isFinite(rr) ? `1:${formatScore(rr, 1)}` : '—', color: 'var(--color-accent)' },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              style={{ background: 'var(--color-surface-3)', borderRadius: 'var(--radius-md)', padding: '0.625rem' }}
            >
              <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '0.25rem' }}>
                {label}
              </p>
              <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '0.9rem', color: color ?? 'var(--color-text)' }}>
                {value}
              </p>
            </div>
          ))}
        </div>

        {/* Confidence + qty row */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Confidence</span>
            <span
              style={{
                fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '1rem',
                color: signal.direction === 'SELL' ? 'var(--color-bear)' : 'var(--color-bull)',
              }}
            >
              {signal.confidence_pct}%
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Suggested qty</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-text)' }}>
              {formatInt(signal.suggested_qty)}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Valid until</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text)' }}>{validUntil} IST</span>
          </div>
        </div>

        {/* U15 — named evidence + forecast horizon */}
        <div style={{ marginBottom: '1.25rem', fontSize: '0.78rem' }}>
          {evidenceLine && (
            <p style={{ color: 'var(--color-text)' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>Evidence: </span>
              {evidenceLine}
            </p>
          )}
          <p style={{ color: 'var(--color-text-muted)', marginTop: '0.15rem' }}>
            Horizon: {signal.classification} — graded over {HORIZON[signal.classification] ?? 'its validity window'}
          </p>
        </div>

        {/* U10 + U17 — how the confidence was built */}
        <p style={SECTION_LABEL}>
          How this {breakdown?.confidence_pct ?? signal.confidence_pct}% was built
        </p>
        {breakdown ? (
          <>
            <DistributionBar b={breakdown} />
            <ArithmeticCard b={breakdown} />
          </>
        ) : detailQuery.isLoading ? (
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Loading breakdown…</p>
        ) : (
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            Factor breakdown unavailable for this signal.
          </p>
        )}

        <div style={{ marginTop: '0.5rem', borderTop: '1px solid var(--color-border)', paddingTop: '1rem' }}>
          <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
            Timeframe: <strong>{signal.timeframe}</strong> · Generated:{' '}
            {new Date(signal.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
          </p>
        </div>
      </div>
    </div>
  )
}

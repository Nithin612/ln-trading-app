import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { SignalOut } from '@/lib/api/signals'

interface Props {
  signal: SignalOut
  onClose: () => void
}

function pct(value: string) {
  return parseFloat(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function confidenceColor(pct: number) {
  if (pct >= 85) return 'var(--color-bull)'
  if (pct >= 70) return 'var(--color-neutral)'
  return 'var(--color-bear)'
}

export function SignalDetailModal({ signal, onClose }: Props) {
  const chartData = Object.entries(signal.factor_scores).map(([name, fs]) => ({
    name: name.replace(/_/g, ' '),
    contribution: parseFloat((fs.score * fs.weight).toFixed(2)),
    score: fs.score,
    weight: fs.weight,
    explanation: fs.explanation,
  }))

  const rr = (
    (parseFloat(signal.take_profit) - parseFloat(signal.entry_price)) /
    Math.abs(parseFloat(signal.entry_price) - parseFloat(signal.stop_loss))
  ).toFixed(2)

  const validUntil = new Date(signal.validity_until).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
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
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 700,
                  fontSize: '1.125rem',
                  color: 'var(--color-text)',
                }}
              >
                {signal.symbol}
              </span>
              <span
                style={{
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  background: signal.direction === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)',
                  color: '#fff',
                }}
              >
                {signal.direction}
              </span>
              <span
                style={{
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  background: 'var(--color-surface-3)',
                  color: 'var(--color-text-muted)',
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
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--color-text-muted)', fontSize: '1.25rem', lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Key metrics */}
        <div
          style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '0.75rem', marginBottom: '1.25rem',
          }}
        >
          {[
            { label: 'Entry', value: `₹${pct(signal.entry_price)}` },
            { label: 'Stop Loss', value: `₹${pct(signal.stop_loss)}`, color: 'var(--color-bear)' },
            { label: 'Target', value: `₹${pct(signal.take_profit)}`, color: 'var(--color-bull)' },
            { label: 'R:R', value: `1:${rr}`, color: 'var(--color-accent)' },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              style={{
                background: 'var(--color-surface-3)',
                borderRadius: 'var(--radius-md)',
                padding: '0.625rem',
              }}
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
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Confidence</span>
            <span
              style={{
                fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '1rem',
                color: confidenceColor(signal.confidence_pct),
              }}
            >
              {signal.confidence_pct}%
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Suggested qty</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-text)' }}>
              {signal.suggested_qty.toLocaleString('en-IN')}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Valid until</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text)' }}>{validUntil} IST</span>
          </div>
        </div>

        {/* Triggering patterns + indicators */}
        {(signal.triggering_patterns?.length || signal.triggering_indicators?.length) ? (
          <div style={{ marginBottom: '1.25rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {signal.triggering_patterns?.map((p) => (
              <span
                key={p}
                style={{
                  padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem',
                  background: 'rgba(22,163,74,0.15)', color: 'var(--color-bull)',
                  border: '1px solid rgba(22,163,74,0.3)',
                }}
              >
                {p.replace(/_/g, ' ')}
              </span>
            ))}
            {signal.triggering_indicators?.map((i) => (
              <span
                key={i}
                style={{
                  padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem',
                  background: 'rgba(31,111,235,0.15)', color: 'var(--color-accent)',
                  border: '1px solid rgba(31,111,235,0.3)',
                }}
              >
                {i.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        ) : null}

        {/* Factor breakdown chart */}
        <p
          style={{
            fontSize: '0.75rem', color: 'var(--color-text-muted)',
            textTransform: 'uppercase', letterSpacing: '0.05em',
            marginBottom: '0.75rem',
          }}
        >
          Factor breakdown
        </p>
        <div style={{ height: '260px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 16, right: 24, top: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-chart-grid)" horizontal={false} />
              <XAxis
                type="number"
                domain={['auto', 'auto']}
                tick={{ fill: 'var(--color-chart-text)', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                dataKey="name"
                type="category"
                width={120}
                tick={{ fill: 'var(--color-chart-text)', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                contentStyle={{
                  background: 'var(--color-surface-3)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '6px',
                  fontSize: '12px',
                  color: 'var(--color-text)',
                }}
                formatter={(value, _name, props) => [
                  `${Number(value).toFixed(2)} (${((props.payload as { explanation?: string } | undefined)?.explanation ?? '').slice(0, 60)})`,
                  'Contribution',
                ]}
              />
              <Bar dataKey="contribution" radius={[0, 3, 3, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={entry.contribution >= 0 ? 'var(--color-bull)' : 'var(--color-bear)'}
                    fillOpacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ marginTop: '1rem', borderTop: '1px solid var(--color-border)', paddingTop: '1rem' }}>
          <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
            Timeframe: <strong>{signal.timeframe}</strong> · Generated:{' '}
            {new Date(signal.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
          </p>
        </div>
      </div>
    </div>
  )
}

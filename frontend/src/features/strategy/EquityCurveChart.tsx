import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

import { formatPct, formatScore } from '@/lib/format'

interface EquityCurveChartProps {
  data: number[]
  label?: string
  height?: number
  // U11 — an optional NIFTY buy-and-hold series, parallel to `data` (indexed to 100). When present,
  // it renders as a dashed reference line so "did it beat doing nothing" is visible on the curve.
  benchmark?: number[]
  benchmarkLabel?: string
  benchmarkReturnPct?: number
}

export function EquityCurveChart({
  data,
  label,
  height = 160,
  benchmark,
  benchmarkLabel,
  benchmarkReturnPct,
}: EquityCurveChartProps) {
  const hasBenchmark = Array.isArray(benchmark) && benchmark.length > 0
  const chartData = data.map((v, i) => ({
    trade: i,
    equity: v,
    benchmark: hasBenchmark ? benchmark[i] : undefined,
  }))
  const finalVal = data[data.length - 1] ?? 100
  const pnl = finalVal - 100
  const positive = pnl >= 0

  const spread = hasBenchmark ? [...data, ...benchmark] : data
  const minVal = Math.min(...spread)
  const maxVal = Math.max(...spread)
  const yDomain: [number, number] = [
    Math.floor(minVal * 0.995),
    Math.ceil(maxVal * 1.005),
  ]

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-(--color-text-muted)">Equity curve — {label}</span>
          <span className="flex items-center gap-3 font-mono">
            <span className="font-bold" style={{ color: positive ? 'var(--color-bull)' : 'var(--color-bear)' }}>
              {formatPct(pnl)}
            </span>
            {hasBenchmark && benchmarkReturnPct != null && (
              // Dash glyph + label carry the meaning, not colour alone; text-secondary is AA on surface-2.
              <span className="text-(--color-text-secondary)">
                ┄ {benchmarkLabel ?? 'benchmark'} {formatPct(benchmarkReturnPct)}
              </span>
            )}
          </span>
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`grad-${label ?? 'eq'}`} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor={positive ? 'var(--color-bull)' : 'var(--color-bear)'}
                stopOpacity={0.25}
              />
              <stop
                offset="95%"
                stopColor={positive ? 'var(--color-bull)' : 'var(--color-bear)'}
                stopOpacity={0.02}
              />
            </linearGradient>
          </defs>
          <XAxis dataKey="trade" hide />
          <YAxis domain={yDomain} hide />
          <ReferenceLine y={100} stroke="var(--color-border)" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              borderRadius: 6,
              fontSize: 11,
              color: 'var(--color-text)',
            }}
            formatter={(v: unknown, name: unknown) => [
              formatScore(v as number, 2),
              name === 'benchmark' ? (benchmarkLabel ?? 'Benchmark') : 'Equity',
            ]}
            labelFormatter={(l: unknown) => `Trade #${String(l)}`}
          />
          {hasBenchmark && (
            <Area
              type="monotone"
              dataKey="benchmark"
              stroke="var(--color-text-secondary)"
              strokeWidth={1.25}
              strokeDasharray="4 3"
              fill="none"
              dot={false}
              activeDot={{ r: 3 }}
              isAnimationActive={false}
            />
          )}
          <Area
            type="monotone"
            dataKey="equity"
            stroke={positive ? 'var(--color-bull)' : 'var(--color-bear)'}
            strokeWidth={1.5}
            fill={`url(#grad-${label ?? 'eq'})`}
            dot={false}
            activeDot={{ r: 3 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

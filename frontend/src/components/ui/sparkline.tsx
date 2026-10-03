import { LineChart, Line, Tooltip } from 'recharts'

import { Skeleton } from '@/components/ui/skeleton'
import { formatCurrency, formatPct } from '@/lib/format'

/** Why a sparkline has no line — three different things, rendered distinctly (A24). */
export type SparkStatus = 'ready' | 'pending' | 'error'

/** A move smaller than this (in %) is "flat": neither bull- nor bear-coloured. */
const FLAT_PCT = 0.005

interface SparklineProps {
  /** Oldest → newest. With status 'ready', undefined or < 2 points = no history. */
  data: number[] | undefined
  /** 'pending' = still loading (skeleton) · 'error' = the request failed · 'ready' = answered. */
  status?: SparkStatus
  width?: number
  height?: number
  color?: string
  showTooltip?: boolean
}

export function Sparkline({
  data,
  status = 'ready',
  width = 80,
  height = 32,
  color,
  showTooltip = false,
}: SparklineProps) {
  const hasLine = !!data && data.length >= 2
  if (!hasLine && status === 'pending') {
    return (
      <span role="img" aria-label="Loading price history" className="inline-flex items-center">
        <Skeleton width={width} height={Math.max(8, height - 8)} />
      </span>
    )
  }
  if (!hasLine) {
    // "Unavailable" (we could not ask) and "no history" (we asked; there is none) are different
    // claims; neither may look like a line, a skeleton, or a flat trend.
    const label = status === 'error' ? 'Price history unavailable' : 'No recent price history'
    return (
      <span
        role="img"
        aria-label={label}
        title={label}
        className="inline-flex items-center justify-end text-(--color-text-secondary)"
        style={{ width, height }}
      >
        —
      </span>
    )
  }

  const last = data[data.length - 1]
  const first = data[0]
  const pct = first !== 0 ? ((last - first) / Math.abs(first)) * 100 : 0
  const dir = Math.abs(pct) < FLAT_PCT ? 'flat' : pct > 0 ? 'up' : 'down'
  const lineColor =
    color ??
    (dir === 'up' ? 'var(--color-bull)' : dir === 'down' ? 'var(--color-bear)' : 'var(--color-text-secondary)')
  const label =
    dir === 'flat'
      ? `${data.length}-session close flat`
      : `${data.length}-session close ${dir} ${formatPct(Math.abs(pct), { signed: false })}`

  return (
    // The span is the ONE accessible node: recharts' accessibility layer would otherwise make
    // each svg a focusable role="application" inside an image — a tab stop per table row.
    <span role="img" aria-label={label} title={label} className="inline-block" style={{ width, height }}>
      <LineChart
        width={width}
        height={height}
        data={data.map((v, i) => ({ i, v }))}
        margin={{ top: 2, bottom: 2, left: 0, right: 0 }}
        accessibilityLayer={false}
      >
        {showTooltip && (
          <Tooltip
            contentStyle={{
              background: 'var(--color-surface-3)',
              border: '1px solid var(--color-border)',
              borderRadius: '4px',
              fontSize: '10px',
              padding: '2px 6px',
            }}
            formatter={(v) => [formatCurrency(Number(v)), '']}
            labelFormatter={() => ''}
          />
        )}
        <Line
          type="monotone"
          dataKey="v"
          stroke={lineColor}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </span>
  )
}

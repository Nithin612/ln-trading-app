import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
  showTooltip?: boolean
}

export function Sparkline({
  data,
  width = 80,
  height = 32,
  color,
  showTooltip = false,
}: SparklineProps) {
  if (!data || data.length < 2) {
    return <div style={{ width, height }} />
  }

  const last = data[data.length - 1]
  const first = data[0]
  const lineColor = color ?? (last >= first ? 'var(--color-bull)' : 'var(--color-bear)')

  const chartData = data.map((v, i) => ({ i, v }))

  return (
    <ResponsiveContainer width={width} height={height}>
      <LineChart data={chartData} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
        {showTooltip && (
          <Tooltip
            contentStyle={{
              background: 'var(--color-surface-3)',
              border: '1px solid var(--color-border)',
              borderRadius: '4px',
              fontSize: '10px',
              padding: '2px 6px',
            }}
            formatter={(v) => [Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 }), '']}
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
    </ResponsiveContainer>
  )
}

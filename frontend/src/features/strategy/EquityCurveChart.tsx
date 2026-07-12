import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

interface EquityCurveChartProps {
  data: number[]
  label?: string
  height?: number
}

export function EquityCurveChart({ data, label, height = 160 }: EquityCurveChartProps) {
  const chartData = data.map((v, i) => ({ trade: i, equity: v }))
  const finalVal = data[data.length - 1] ?? 100
  const pnl = finalVal - 100
  const positive = pnl >= 0

  const minVal = Math.min(...data)
  const maxVal = Math.max(...data)
  const yDomain: [number, number] = [
    Math.floor(minVal * 0.995),
    Math.ceil(maxVal * 1.005),
  ]

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-(--color-text-muted)">Equity curve — {label}</span>
          <span
            className="font-mono font-bold"
            style={{ color: positive ? 'var(--color-bull)' : 'var(--color-bear)' }}
          >
            {positive ? '+' : ''}{pnl.toFixed(2)}%
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
            formatter={(v: unknown) => [`${(v as number).toFixed(2)}`, 'Equity']}
            labelFormatter={(l: unknown) => `Trade #${String(l)}`}
          />
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

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { FiiDiiRow } from '@/lib/api/market_data'

interface Props {
  rows: FiiDiiRow[]
  investorType: 'FII' | 'DII'
}

interface ChartPoint {
  date: string
  net: number
}

function formatCr(val: number) {
  return `₹${Math.abs(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr`
}

export function FiiDiiChart({ rows, investorType }: Props) {
  const points: ChartPoint[] = rows
    .filter((r) => r.investor_type === investorType && r.segment === 'cash')
    .map((r) => ({
      date: r.trade_date,
      net: parseFloat(r.net_value_cr),
    }))
    .reverse()

  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 rounded-lg border border-[--color-border] bg-[--color-chart-bg]">
        <span className="text-sm text-[--color-text-muted]">No {investorType} data</span>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={points} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2330" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: '#9ca3af' }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis
          tick={{ fontSize: 10, fill: '#9ca3af' }}
          tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          formatter={(val) => [typeof val === 'number' ? formatCr(val) : '—', `${investorType} Net (Cash)`]}
          labelStyle={{ color: '#9ca3af' }}
          contentStyle={{ background: '#0e1117', border: '1px solid #1e2330', borderRadius: 6 }}
        />
        <ReferenceLine y={0} stroke="#374151" />
        <Legend
          wrapperStyle={{ fontSize: 11, color: '#9ca3af' }}
          formatter={() => `${investorType} Net Cash (Cr)`}
        />
        <Bar dataKey="net" name={`${investorType} Net (Cash)`} radius={[2, 2, 0, 0]}>
          {points.map((p, i) => (
            <Cell key={i} fill={p.net >= 0 ? '#22c55e' : '#ef4444'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

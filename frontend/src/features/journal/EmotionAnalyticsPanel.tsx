import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { journalApi, type EmotionCount } from '@/lib/api/journal'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

const EMOTION_COLORS: Record<string, string> = {
  confident: '#22c55e',
  neutral:   '#64748b',
  fear:      '#f97316',
  greed:     '#a855f7',
  anxious:   '#f59e0b',
  satisfied: '#22c55e',
  excited:   '#3b82f6',
  frustrated:'#ef4444',
  regret:    '#f97316',
}

function pnlClass(val: string | null) {
  if (!val) return 'text-(--color-text-muted)'
  return Number(val) >= 0 ? 'text-(--color-bull)' : 'text-(--color-bear)'
}

function formatPnl(val: string | null) {
  if (!val) return '—'
  const n = Number(val)
  return `${n >= 0 ? '+' : ''}₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

interface EmotionBarProps {
  data: EmotionCount[]
  label: string
}

function EmotionBar({ data, label }: EmotionBarProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-xs text-(--color-text-muted)">
        No data yet
      </div>
    )
  }

  return (
    <div>
      <p className="text-xs font-medium text-(--color-text-muted) uppercase tracking-wider mb-2">
        {label}
      </p>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 8, top: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="emotion"
            tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
            width={72}
          />
          <Tooltip
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as EmotionCount
              return (
                <div className="bg-(--color-surface-2) border border-(--color-border) rounded-md px-3 py-2 text-xs shadow-lg">
                  <p className="font-semibold capitalize text-(--color-text)">{d.emotion}</p>
                  <p className="text-(--color-text-muted)">{d.count} trade{d.count !== 1 ? 's' : ''}</p>
                  <p className={cn('mt-0.5', pnlClass(d.avg_pnl))}>
                    Avg P&L: {formatPnl(d.avg_pnl)}
                  </p>
                </div>
              )
            }}
          />
          <Bar dataKey="count" radius={[0, 3, 3, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.emotion}
                fill={EMOTION_COLORS[entry.emotion] ?? '#64748b'}
                fillOpacity={0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-1 space-y-0.5">
        {data.map((e) => (
          <div key={e.emotion} className="flex items-center justify-between text-xs">
            <span className="capitalize text-(--color-text-muted)">{e.emotion}</span>
            <span className={pnlClass(e.avg_pnl)}>{formatPnl(e.avg_pnl)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function EmotionAnalyticsPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['journal-emotions'],
    queryFn: () => journalApi.analytics(),
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    )
  }

  if (!data) return null

  return (
    <div
      className="rounded-lg border border-(--color-border) p-4"
      style={{ background: 'var(--color-surface-2)' }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-(--color-text)">Emotion Analytics</h3>
        <span className="text-xs text-(--color-text-muted)">{data.total_entries} entries</span>
      </div>

      <div className="space-y-5">
        <EmotionBar data={data.before} label="Before trade" />
        <div className="border-t border-(--color-border)" />
        <EmotionBar data={data.after} label="After trade" />
      </div>
    </div>
  )
}

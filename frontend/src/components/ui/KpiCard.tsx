import { cn } from '@/lib/utils'

interface KpiCardProps {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  accent?: 'profit' | 'loss' | 'warning' | 'info' | 'accent'
  className?: string
}

const ACCENT_BORDER: Record<NonNullable<KpiCardProps['accent']>, string> = {
  profit:  'border-l-(--color-profit)',
  loss:    'border-l-(--color-loss)',
  warning: 'border-l-(--color-warning)',
  info:    'border-l-(--color-info)',
  accent:  'border-l-(--color-accent)',
}

const TREND_COLOR: Record<NonNullable<KpiCardProps['trend']>, string> = {
  up:      'text-(--color-profit)',
  down:    'text-(--color-loss)',
  neutral: 'text-(--color-text-muted)',
}

export function KpiCard({ label, value, sub, trend, accent = 'accent', className }: KpiCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-l-4 border-(--color-border) p-4',
        ACCENT_BORDER[accent],
        className,
      )}
      style={{ backgroundColor: 'var(--color-surface-2)' }}
    >
      <p className="text-xs font-medium text-(--color-text-muted) mb-1 truncate">{label}</p>
      <p className="text-xl font-semibold font-mono tabular-nums text-(--color-text) leading-tight">
        {value}
      </p>
      {sub && (
        <p className={cn('text-xs mt-1', trend ? TREND_COLOR[trend] : 'text-(--color-text-muted)')}>
          {sub}
        </p>
      )}
    </div>
  )
}

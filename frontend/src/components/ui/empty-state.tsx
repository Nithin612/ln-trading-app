import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

function DefaultIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <rect x="8" y="14" width="32" height="22" rx="3" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 2" />
      <circle cx="24" cy="25" r="6" stroke="currentColor" strokeWidth="1.5" />
      <line x1="18" y1="14" x2="20" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="24" y1="14" x2="24" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="30" y1="14" x2="28" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-8 text-center',
        className,
      )}
    >
      <div className="text-(--color-text-muted) mb-4 opacity-50">
        {icon ?? <DefaultIcon />}
      </div>
      <p className="text-sm font-medium text-(--color-text) mb-1">{title}</p>
      {description && (
        <p className="text-xs text-(--color-text-muted) max-w-xs">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

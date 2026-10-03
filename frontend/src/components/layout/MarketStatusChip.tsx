import { useMarketStatus } from '@/hooks/useMarketStatus'
import { cn } from '@/lib/utils'

/**
 * The top-bar session pill + IST clock. Its own component so the per-second tick re-renders
 * only this subtree, not the whole shell (ui-reviewer, 2026-10-03). UNKNOWN — the calendar has
 * not answered — is drawn with a dashed border so it never reads as CLOSED at a glance (A24).
 */
export function MarketStatusChip() {
  const { status, timeIST, nextEvent } = useMarketStatus()
  const unknown = status === 'UNKNOWN'
  return (
    <div className="flex items-center gap-2">
      <span
        title={unknown ? 'Market calendar not reachable — status not assessable' : undefined}
        aria-label={unknown ? 'Market status unknown: calendar not reachable' : `Market ${status}`}
        className={cn(
          'text-xs font-semibold px-2 py-0.5 rounded-full border',
          status === 'OPEN'
            ? 'bg-(--color-profit-bg) text-(--color-profit) border-(--color-profit)/20'
            : status === 'PRE-MARKET'
              ? 'bg-(--color-warning-bg) text-(--color-warning) border-(--color-warning)/20'
              : 'bg-(--color-surface-3) text-(--color-text-muted) border-(--color-border)',
          unknown && 'border-dashed',
        )}
      >
        {status}
      </span>
      <span className="text-xs font-mono text-(--color-text-muted)">{timeIST} IST</span>
      {nextEvent && (
        <span className="text-xs text-(--color-text-muted) hidden xl:block">• {nextEvent}</span>
      )}
    </div>
  )
}

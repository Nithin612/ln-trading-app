import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { X, Edit2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi, type PositionOut } from '@/lib/api/trading'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/hooks/useToast'
import { DailyPnlCard } from './DailyPnlCard'
import { ClosePositionDialog } from './ClosePositionDialog'
import { UpdateSlDialog } from './UpdateSlDialog'

function pnlFmt(val: string | null): React.ReactNode {
  if (val == null) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const n = parseFloat(val)
  const sign = n >= 0 ? '+' : ''
  return (
    <span style={{ color: n >= 0 ? 'var(--color-bull)' : 'var(--color-bear)', fontWeight: 600 }}>
      {sign}₹{Math.abs(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
    </span>
  )
}

function priceFmt(val: string | null): string {
  if (!val) return '—'
  return `₹${parseFloat(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function TrailBadge({ state }: { state: string }) {
  if (state === 'none') return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const colors: Record<string, string> = {
    breakeven: '#60a5fa',
    trailing_1: '#f59e0b',
    trailing_2: 'var(--color-bull)',
  }
  return (
    <span style={{ color: colors[state] ?? 'var(--color-text-muted)', fontSize: '0.7rem', fontWeight: 600 }}>
      {state.replace('_', ' ')}
    </span>
  )
}

export function PositionsPage() {
  const { accessToken } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()

  const [closeTarget, setCloseTarget] = useState<PositionOut | null>(null)
  const [slTarget, setSlTarget] = useState<PositionOut | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['positions-open'],
    queryFn: () => tradingApi.getOpenPositions(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 30_000,
  })

  const closeMutation = useMutation({
    mutationFn: ({ id, exitPrice }: { id: string; exitPrice?: string }) =>
      tradingApi.closePosition(id, exitPrice, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['positions-open'] })
      void qc.invalidateQueries({ queryKey: ['trade-history'] })
      void qc.invalidateQueries({ queryKey: ['daily-pnl'] })
      toast.success('Position closed')
      setCloseTarget(null)
    },
    onError: () => toast.error('Failed to close position'),
  })

  const positions = data?.positions ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1">
          <DailyPnlCard />
        </div>
      </div>

      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Open Positions
          </span>
          {data && (
            <span className="text-xs text-(--color-text-muted)">{data.total} position{data.total !== 1 ? 's' : ''}</span>
          )}
        </div>

        {isLoading && <div className="p-4"><Skeleton className="h-48 w-full" /></div>}

        {!isLoading && positions.length === 0 && (
          <EmptyState
            title="No open positions"
            description="Paper-buy a signal from the Dashboard to open a position."
          />
        )}

        {!isLoading && positions.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="border-b border-(--color-border)">
                  {['Symbol', 'Side', 'Qty', 'Entry', 'SL', 'TP', 'Trail', 'Unreal. P&L', 'Opened', ''].map((h) => (
                    <th
                      key={h}
                      className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium whitespace-nowrap"
                      style={{ color: 'var(--color-text-muted)', textAlign: h === 'Symbol' ? 'left' : 'right' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((pos) => (
                  <tr key={pos.id} className="border-b border-(--color-border) hover:bg-(--color-surface-hover)">
                    <td className="px-3 py-2">
                      <Link
                        to={`/stocks/${pos.stock_id}`}
                        className="font-mono font-bold text-(--color-accent) hover:text-(--color-accent-hover)"
                        style={{ textDecoration: 'none' }}
                      >
                        {pos.symbol}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span style={{
                        padding: '2px 6px', borderRadius: '4px', fontWeight: 700, fontSize: '0.7rem',
                        background: pos.side === 'LONG' ? 'rgba(22,163,74,0.15)' : 'rgba(220,38,38,0.15)',
                        color: pos.side === 'LONG' ? 'var(--color-bull)' : 'var(--color-bear)',
                      }}>
                        {pos.side}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{pos.quantity.toLocaleString('en-IN')}</td>
                    <td className="px-3 py-2 text-right font-mono">{priceFmt(pos.avg_entry_price)}</td>
                    <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--color-bear)' }}>{priceFmt(pos.current_sl)}</td>
                    <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--color-bull)' }}>{priceFmt(pos.current_tp)}</td>
                    <td className="px-3 py-2 text-right"><TrailBadge state={pos.trail_state} /></td>
                    <td className="px-3 py-2 text-right">{pnlFmt(pos.unrealized_pnl)}</td>
                    <td className="px-3 py-2 text-right text-(--color-text-muted) whitespace-nowrap">
                      {new Date(pos.opened_at).toLocaleString('en-IN', {
                        timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => setSlTarget(pos)}
                          className="p-1 rounded text-(--color-text-muted) hover:text-(--color-text) hover:bg-(--color-surface-3) transition-colors"
                          title="Update SL"
                        >
                          <Edit2 size={12} />
                        </button>
                        <button
                          onClick={() => setCloseTarget(pos)}
                          className="p-1 rounded hover:bg-(--color-surface-3) transition-colors"
                          style={{ color: 'var(--color-bear)' }}
                          title="Close position"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {closeTarget && (
        <ClosePositionDialog
          position={closeTarget}
          isLoading={closeMutation.isPending}
          onConfirm={(exitPrice) => closeMutation.mutate({ id: closeTarget.id, exitPrice })}
          onClose={() => setCloseTarget(null)}
        />
      )}

      {slTarget && (
        <UpdateSlDialog
          position={slTarget}
          onClose={() => setSlTarget(null)}
          onUpdated={() => {
            void qc.invalidateQueries({ queryKey: ['positions-open'] })
            setSlTarget(null)
          }}
        />
      )}
    </div>
  )
}

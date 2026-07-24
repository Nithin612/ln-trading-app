import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { tradingApi } from '@/lib/api/trading'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Pagination } from '@/components/ui/pagination'
import { DailyPnlCard } from './DailyPnlCard'
import { formatINR, formatInt } from '@/lib/format'

const PAGE_SIZE = 20

function pnlCell(val: string): React.ReactNode {
  const n = parseFloat(val)
  const sign = n >= 0 ? '+' : '-'
  return (
    <span style={{ color: n >= 0 ? 'var(--color-bull)' : 'var(--color-bear)', fontWeight: 600 }}>
      {sign}₹{formatINR(Math.abs(n))}
    </span>
  )
}

function priceFmt(val: string | null): string {
  if (!val) return '—'
  return `₹${formatINR(parseFloat(val))}`
}

export function TradeHistoryPage() {
  const { accessToken } = useAuth()
  const [page, setPage] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ['trade-history', page],
    queryFn: () => tradingApi.getHistory({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }, accessToken!),
    enabled: !!accessToken,
  })

  const positions = data?.positions ?? []
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  // Running totals
  const totalPnl = positions.reduce((sum, p) => sum + parseFloat(p.realized_pnl), 0)
  const wins = positions.filter((p) => parseFloat(p.realized_pnl) > 0).length
  const winRate = positions.length > 0 ? Math.round((wins / positions.length) * 100) : null

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1">
          <DailyPnlCard />
        </div>

        {/* Summary cards */}
        {data && positions.length > 0 && (
          <>
            <SummaryCard label="Page P&L" value={pnlCell(String(totalPnl))} />
            <SummaryCard label="Win Rate" value={winRate != null ? `${winRate}%` : '—'} />
            <SummaryCard label="Trades" value={data.total} />
          </>
        )}
      </div>

      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Trade History
          </span>
          {data && (
            <span className="text-xs text-(--color-text-muted)">{data.total} trades</span>
          )}
        </div>

        {isLoading && <div className="p-4"><Skeleton className="h-48 w-full" /></div>}

        {!isLoading && positions.length === 0 && (
          <EmptyState
            title="No trade history"
            description="Closed paper trades appear here."
          />
        )}

        {!isLoading && positions.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="border-b border-(--color-border)">
                  {['Symbol', 'Side', 'Qty', 'Entry', 'Exit', 'Realized P&L', 'Opened', 'Closed'].map((h) => (
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
                        background: pos.side === 'LONG' ? 'var(--color-profit-bg)' : 'var(--color-loss-bg)',
                        color: pos.side === 'LONG' ? 'var(--color-bull)' : 'var(--color-bear)',
                      }}>
                        {pos.side}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{formatInt(pos.quantity)}</td>
                    <td className="px-3 py-2 text-right font-mono">{priceFmt(pos.avg_entry_price)}</td>
                    <td className="px-3 py-2 text-right font-mono text-(--color-text-muted)">—</td>
                    <td className="px-3 py-2 text-right">{pnlCell(pos.realized_pnl)}</td>
                    <td className="px-3 py-2 text-right text-(--color-text-muted) whitespace-nowrap">
                      {new Date(pos.opened_at).toLocaleDateString('en-IN', {
                        timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: '2-digit',
                      })}
                    </td>
                    <td className="px-3 py-2 text-right text-(--color-text-muted) whitespace-nowrap">
                      {pos.closed_at
                        ? new Date(pos.closed_at).toLocaleString('en-IN', {
                          timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short',
                          hour: '2-digit', minute: '2-digit',
                        })
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="px-4 py-3 border-t border-(--color-border)">
            <Pagination
              page={page + 1}
              pages={totalPages}
              pageSize={PAGE_SIZE}
              total={data?.total ?? 0}
              onPageChange={(p) => setPage(p - 1)}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
      <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-1">{label}</p>
      <div className="text-xl font-bold font-mono text-(--color-text)">{value}</div>
    </div>
  )
}

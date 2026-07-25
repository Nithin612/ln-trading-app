import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, TrendingUp, Layers, Landmark } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { suggestionsApi, PROFILE_STYLES, type ProfileStyle } from '@/lib/api/suggestions'
import { tradingApi } from '@/lib/api/trading'
import { useTradingHaltStore } from '@/store/tradingHaltStore'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'
import { formatINR, formatInt, formatPct } from '@/lib/format'

const STYLE_META: Record<ProfileStyle, { label: string; desc: string; icon: React.ReactNode }> = {
  intraday:   { label: 'Intraday',   desc: 'Same-session momentum & breakouts — squared off by close.',  icon: <Activity size={18} /> },
  swing:      { label: 'Swing',      desc: 'Multi-day trend continuation (~5 trading-day validity).',    icon: <TrendingUp size={18} /> },
  fno:        { label: 'F&O',        desc: 'Derivatives & option-selling setups.',                        icon: <Layers size={18} /> },
  investment: { label: 'Investment', desc: 'Positional / long-term theses (~30 trading-day validity).',   icon: <Landmark size={18} /> },
}

function isStyle(s: string | undefined): s is ProfileStyle {
  return !!s && (PROFILE_STYLES as readonly string[]).includes(s)
}

function DirBadge({ dir }: { dir: 'BUY' | 'SELL' }) {
  const buy = dir === 'BUY'
  return (
    <span
      className="px-2 py-0.5 rounded-full text-[0.7rem] font-bold whitespace-nowrap"
      style={{
        background: buy ? 'var(--color-profit-bg)' : 'var(--color-loss-bg)',
        color: buy ? 'var(--color-bull)' : 'var(--color-bear)',
      }}
    >
      {buy ? '▲ BUY' : '▼ SELL'}
    </span>
  )
}

export function StylePage() {
  const { style } = useParams()
  const { accessToken } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const [tradingId, setTradingId] = useState<string | null>(null)
  const halted = useTradingHaltStore((s) => s.halted)

  const valid = isStyle(style)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['suggestions', style],
    queryFn: () => suggestionsApi.getByStyle(style as string, accessToken!),
    enabled: !!accessToken && valid,
    staleTime: 60_000,
  })

  const paperTrade = useMutation({
    mutationFn: ({ id, dir }: { id: string; dir: 'BUY' | 'SELL' }) =>
      tradingApi.placeOrder({ signal_id: id, side: dir }, accessToken!),
    onSuccess: (order) => {
      toast.success(`Paper ${order.side} placed: ${order.filled_qty} × ${order.symbol}`)
      void qc.invalidateQueries({ queryKey: ['positions-open'] })
      void qc.invalidateQueries({ queryKey: ['paper-record'] })
      setTradingId(null)
    },
    onError: (err: { message?: string }) => {
      toast.error(err.message ?? 'Order rejected')
      setTradingId(null)
    },
  })

  if (!valid) {
    return (
      <div className="max-w-md">
        <EmptyState
          title="Unknown style"
          description={`"${style}" is not a trading style — pick Intraday, Swing, F&O or Investment.`}
        />
      </div>
    )
  }

  const meta = STYLE_META[style as ProfileStyle]
  const suggestions = data?.suggestions ?? []

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={`${meta.label} suggestions`} subtitle={meta.desc} />

      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between">
          <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            {meta.icon} {meta.label}
          </span>
          {data && (
            <span className="text-xs text-(--color-text-muted)">
              {data.total} suggestion{data.total !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {isLoading && (
          <div className="p-4 space-y-2" aria-label="loading suggestions">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </div>
        )}

        {isError && (
          <div className="p-4 text-sm text-(--color-text-muted)">
            Could not load {meta.label} suggestions.{' '}
            <Button variant="link" size="sm" onClick={() => void refetch()}>Retry</Button>
          </div>
        )}

        {!isLoading && !isError && suggestions.length === 0 && (
          <EmptyState
            title={`No ${meta.label} suggestions right now`}
            description="Fresh suggestions are generated nightly after EOD (~7:30 PM IST on a trading day)."
          />
        )}

        {!isLoading && suggestions.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[0.7rem] uppercase tracking-wide text-(--color-text-muted) border-b border-(--color-border)">
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-left">Dir</th>
                  <th className="px-3 py-2 text-right">Conf</th>
                  <th className="px-3 py-2 text-right">Entry</th>
                  <th className="px-3 py-2 text-right">SL</th>
                  <th className="px-3 py-2 text-right">TP</th>
                  <th className="px-3 py-2 text-right">Qty</th>
                  <th className="px-3 py-2 text-left">Profile</th>
                  <th className="px-3 py-2 text-right" />
                </tr>
              </thead>
              <tbody>
                {suggestions.map((s) => (
                  <tr key={s.id} className="border-b border-(--color-border) hover:bg-(--color-surface-hover)">
                    <td className="px-3 py-2 font-mono font-bold text-(--color-text)">{s.symbol}</td>
                    <td className="px-3 py-2"><DirBadge dir={s.direction} /></td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-(--color-accent)">
                      {formatPct(s.confidence_pct, { signed: false })}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-(--color-text)">₹{formatINR(parseFloat(s.entry_price))}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums" style={{ color: 'var(--color-bear)' }}>₹{formatINR(parseFloat(s.stop_loss))}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums" style={{ color: 'var(--color-bull)' }}>₹{formatINR(parseFloat(s.take_profit))}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{formatInt(s.suggested_qty)}</td>
                    <td className="px-3 py-2 text-(--color-text-muted) whitespace-nowrap">{s.profile_name}</td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        variant="outline"
                        size="xs"
                        disabled={tradingId === s.id || halted}
                        onClick={() => {
                          if (halted) { toast.error('Trading is halted — release the kill switch on Go Live.'); return }
                          setTradingId(s.id); paperTrade.mutate({ id: s.id, dir: s.direction })
                        }}
                        style={{ color: s.direction === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)' }}
                        title={s.direction === 'BUY' ? 'Paper Buy (open long)' : 'Paper Sell (open short)'}
                      >
                        {tradingId === s.id ? '…' : s.direction === 'BUY' ? '▲ Buy' : '▼ Sell'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

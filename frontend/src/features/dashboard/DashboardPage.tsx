import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Copy, TrendingUp, TrendingDown, Minus, Activity, ShoppingCart } from 'lucide-react'
import { BarChart, Bar, XAxis, ResponsiveContainer, Tooltip as ReTooltip, Cell } from 'recharts'
import { useAuth } from '@/hooks/useAuth'
import { signalsApi } from '@/lib/api/signals'
import { marketDataApi } from '@/lib/api/market_data'
import { tradingApi } from '@/lib/api/trading'
import type { SignalOut } from '@/lib/api/signals'
import { SignalDetailModal } from './SignalDetailModal'
import { FilingsPanel } from './FilingsPanel'
import { ProvisionalPanel } from './ProvisionalPanel'
import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { Skeleton, SkeletonCard } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Sparkline } from '@/components/ui/sparkline'
import { PriceCell } from '@/components/ui/PriceCell'
import { formatCurrency, formatINR, formatInt } from '@/lib/format'
import { Slider } from '@/components/ui/slider'
import { useToast } from '@/hooks/useToast'
import { SimpleSelect } from '@/components/ui/simple-select'

function pctFmt(value: string) {
  return formatINR(parseFloat(value))
}

function crFormat(val: string | undefined) {
  if (!val) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const n = parseFloat(val)
  return (
    <span style={{ color: n >= 0 ? 'var(--color-bull)' : 'var(--color-bear)', fontWeight: 600 }}>
      {n >= 0 ? '+' : ''}
      {formatInt(n)} Cr
    </span>
  )
}

const CLASSIFICATIONS = ['All', 'swing', 'positional', 'scalp', 'multibagger']
const DIRECTIONS = ['All', 'BUY', 'SELL']
const SEGMENTS = ['ALL', 'CASH', 'F&O']

function ConfidenceBadge({ pct }: { pct: number }) {
  const color = pct >= 85 ? 'var(--color-bull)' : pct >= 70 ? 'var(--color-neutral)' : 'var(--color-bear)'
  return (
    <span
      style={{
        display: 'inline-block', minWidth: '44px', textAlign: 'center',
        padding: '2px 6px', borderRadius: '4px',
        fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.75rem',
        color, border: `1px solid ${color}`,
      }}
    >
      {pct}%
    </span>
  )
}

function DirectionBadge({ dir }: { dir: string }) {
  const bg = dir === 'BUY' ? 'var(--color-profit-bg)' : 'var(--color-loss-bg)'
  const color = dir === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)'
  return (
    <span style={{ padding: '2px 8px', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 700, background: bg, color }}>
      {dir}
    </span>
  )
}

interface StatCardProps {
  label: string
  value: React.ReactNode
  icon: React.ReactNode
  color?: string
  sub?: string
}

function StatCard({ label, value, icon, color, sub }: StatCardProps) {
  return (
    <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 flex items-start gap-3">
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: color ? `color-mix(in oklab, ${color} 14%, transparent)` : 'var(--color-surface-3)' }}
      >
        <span style={{ color: color ?? 'var(--color-text-muted)' }}>{icon}</span>
      </div>
      <div className="min-w-0">
        <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-1">{label}</p>
        <div className="text-xl font-bold font-mono text-(--color-text)">{value}</div>
        {sub && <p className="text-xs text-(--color-text-muted) mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { accessToken } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const [selectedSignal, setSelectedSignal] = useState<SignalOut | null>(null)
  const [direction, setDirection] = useState('All')
  const [classification, setClassification] = useState('All')
  const [minConfidence, setMinConfidence] = useState(70)
  const [segment, setSegment] = useState('ALL')
  const [tradingSignalId, setTradingSignalId] = useState<string | null>(null)

  const paperTradeMutation = useMutation({
    mutationFn: ({ signalId, side }: { signalId: string; side: 'BUY' | 'SELL' }) =>
      tradingApi.placeOrder({ signal_id: signalId, side }, accessToken!),
    onSuccess: (order) => {
      toast.success(`Paper ${order.side} placed: ${order.filled_qty} × ${order.symbol}`)
      void qc.invalidateQueries({ queryKey: ['positions-open'] })
      void qc.invalidateQueries({ queryKey: ['daily-pnl'] })
      void qc.invalidateQueries({ queryKey: ['paper-record'] })
      setTradingSignalId(null)
    },
    onError: (err: { message?: string }) => {
      toast.error(err.message ?? 'Order rejected')
      setTradingSignalId(null)
    },
  })

  function handlePaperTrade(e: React.MouseEvent, sig: SignalOut) {
    e.stopPropagation()
    // A bearish signal must open a SHORT, not a wrong-way LONG.
    const side = sig.direction === 'SELL' ? 'SELL' : 'BUY'
    setTradingSignalId(sig.id)
    paperTradeMutation.mutate({ signalId: sig.id, side })
  }

  const { data: signalData, isLoading: signalsLoading } = useQuery({
    queryKey: ['signals-active', direction, classification, minConfidence],
    queryFn: () =>
      signalsApi.getActive(
        {
          direction: direction !== 'All' ? direction : undefined,
          classification: classification !== 'All' ? classification : undefined,
          minConfidence,
          limit: 100,
        },
        accessToken!,
      ),
    enabled: !!accessToken,
    refetchInterval: 300_000,
  })

  const signalSymbols = useMemo(
    () => signalData?.signals.map((s) => s.symbol) ?? [],
    [signalData],
  )
  const { quotes: liveQuotes, connected: wsConnected } = useLiveQuotes(signalSymbols)

  const today = useMemo(() => new Date().toISOString().slice(0, 10), [])
  const weekAgo = useMemo(() => {
    const d = new Date(); d.setDate(d.getDate() - 7)
    return d.toISOString().slice(0, 10)
  }, [])

  const { data: fiiData } = useQuery({
    queryKey: ['fii-dii-summary'],
    queryFn: () => marketDataApi.getFiiDii({ fromDate: weekAgo, toDate: today, segment: 'cash', limit: 20 }, accessToken!),
    enabled: !!accessToken,
    refetchInterval: 3600_000,
  })

  const cashRows = useMemo(() => fiiData?.rows ?? [], [fiiData])
  const latestFii = cashRows.find((r) => r.investor_type === 'FII')
  const latestDii = cashRows.find((r) => r.investor_type === 'DII')

  // FII/DII mini bar chart data (last 7 days grouped by date)
  const fiiDiiChartData = useMemo(() => {
    const byDate = new Map<string, { fii: number; dii: number }>()
    for (const r of cashRows) {
      if (!byDate.has(r.trade_date)) byDate.set(r.trade_date, { fii: 0, dii: 0 })
      const entry = byDate.get(r.trade_date)!
      if (r.investor_type === 'FII') entry.fii = parseFloat(r.net_value_cr)
      if (r.investor_type === 'DII') entry.dii = parseFloat(r.net_value_cr)
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({ date: date.slice(5), ...vals }))
  }, [cashRows])

  const signals = useMemo(() => signalData?.signals ?? [], [signalData])
  const buyCount = signals.filter((s) => s.direction === 'BUY').length
  const sellCount = signals.filter((s) => s.direction === 'SELL').length
  const avgConf = signals.length
    ? Math.round(signals.reduce((sum, s) => sum + s.confidence_pct, 0) / signals.length)
    : 0

  // Filter by segment (client-side since signal data is already fetched)
  const filteredSignals = useMemo(() => {
    if (segment === 'ALL') return signals
    if (segment === 'F&O') return signals.filter((s) => s.classification === 'scalp' || s.timeframe === '5m' || s.timeframe === '15m')
    return signals // CASH — no good way to filter without stock metadata, show all
  }, [signals, segment])

  function copySignal(sig: SignalOut) {
    const text = `${sig.symbol} ${sig.direction} @ ₹${pctFmt(sig.entry_price)} | SL ₹${pctFmt(sig.stop_loss)} | TP ₹${pctFmt(sig.take_profit)} | Conf: ${sig.confidence_pct}% | Qty: ${sig.suggested_qty}`
    void navigator.clipboard.writeText(text).then(() => toast.success('Signal copied to clipboard'))
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {signalsLoading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <StatCard
              label="Active Signals"
              value={signalData?.total ?? 0}
              icon={<Activity size={18} />}
              color="var(--color-accent)"
              sub={`≥${minConfidence}% confidence`}
            />
            <StatCard
              label="Buy Signals"
              value={buyCount}
              icon={<TrendingUp size={18} />}
              color="var(--color-bull)"
            />
            <StatCard
              label="Sell Signals"
              value={sellCount}
              icon={<TrendingDown size={18} />}
              color="var(--color-bear)"
            />
            <StatCard
              label="Avg Confidence"
              value={signals.length ? `${avgConf}%` : '—'}
              icon={<Minus size={18} />}
              color="var(--color-neutral)"
              sub={signals.length ? `across ${signals.length} signals` : 'no signals'}
            />
          </>
        )}
      </div>

      {/* ── Main content: signals + filings ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 340px',
          gap: '1rem',
          alignItems: 'start',
        }}
      >
        {/* ── Signals table ── */}
        <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg">
          {/* Filter bar */}
          <div className="px-4 py-3 border-b border-(--color-border) flex flex-wrap gap-3 items-center">
            <span className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide mr-auto">
              Signals
            </span>

            {/* WS live indicator */}
            <span className="flex items-center gap-1.5 text-xs" style={{ color: wsConnected ? 'var(--color-bull)' : 'var(--color-text-muted)' }}>
              <span
                style={{
                  width: '6px', height: '6px', borderRadius: '50%', display: 'inline-block',
                  background: wsConnected ? 'var(--color-bull)' : 'var(--color-text-muted)',
                }}
              />
              {wsConnected ? 'Live' : 'Offline'}
            </span>

            {/* Segment dropdown */}
            <SimpleSelect
              value={segment}
              size="sm"
              className="min-w-[80px]"
              options={SEGMENTS.map((s) => ({ value: s, label: s }))}
              onChange={setSegment}
            />

            {/* Direction toggle */}
            <div className="flex rounded overflow-hidden border border-(--color-border)">
              {DIRECTIONS.map((d) => (
                <button
                  key={d}
                  onClick={() => setDirection(d)}
                  className="px-2.5 py-1 text-xs font-semibold transition-colors"
                  style={{
                    background: direction === d ? 'var(--color-accent)' : 'var(--color-surface-3)',
                    color: direction === d ? '#fff' : 'var(--color-text-muted)',
                  }}
                >
                  {d}
                </button>
              ))}
            </div>

            {/* Classification dropdown */}
            <SimpleSelect
              value={classification}
              size="sm"
              className="min-w-[110px]"
              options={CLASSIFICATIONS.map((c) => ({ value: c, label: c === 'All' ? 'All classes' : c }))}
              onChange={setClassification}
            />

            {/* Confidence slider */}
            <div className="w-32 hidden lg:block">
              <Slider
                value={minConfidence}
                onChange={setMinConfidence}
                min={50}
                max={95}
                step={5}
                label={`Min conf`}
              />
            </div>
            {/* Compact confidence selector — small screens only */}
            <SimpleSelect
              value={String(minConfidence)}
              size="sm"
              className="min-w-[80px] lg:hidden"
              options={[50, 60, 70, 75, 80, 85, 90].map((v) => ({ value: String(v), label: `${v}%+` }))}
              onChange={(v) => setMinConfidence(Number(v))}
            />
          </div>

          {/* Table */}
          {signalsLoading && (
            <div className="p-4"><Skeleton className="h-64 w-full" /></div>
          )}

          {!signalsLoading && filteredSignals.length === 0 && (
            <EmptyState
              title="No active signals"
              description="Signals are generated nightly at 18:00 IST. Adjust filters or run manually."
            />
          )}

          {!signalsLoading && filteredSignals.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr className="border-b border-(--color-border) bg-(--color-surface-2) sticky top-0">
                    {/* static header list — index keys are stable here; the
                        two trailing action columns share the "" label, so
                        label keys duplicated (React duplicate-key warning) */}
                    {['Symbol', 'Sparkline', 'LTP', 'Dir', 'Class', 'Conf', 'Entry', 'SL', 'TP', 'Qty', 'Valid until', '', ''].map((h, i) => (
                      <th
                        key={i}
                        className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium whitespace-nowrap"
                        style={{ color: 'var(--color-text-muted)', textAlign: h === 'Symbol' ? 'left' : 'right' }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredSignals.map((sig) => {
                    const validUntil = new Date(sig.validity_until).toLocaleString('en-IN', {
                      timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                    })
                    const ltp = liveQuotes[sig.symbol]
                    return (
                      <tr
                        key={sig.id}
                        onClick={() => setSelectedSignal(sig)}
                        className="border-b border-(--color-border) cursor-pointer transition-colors hover:bg-(--color-surface-hover)"
                      >
                        <td className="px-3 py-2">
                          <Link
                            to={`/stocks/${sig.stock_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="font-mono font-bold text-(--color-accent) hover:text-(--color-accent-hover) text-sm"
                            style={{ textDecoration: 'none' }}
                          >
                            {sig.symbol}
                          </Link>
                        </td>
                        <td className="px-3 py-2" style={{ textAlign: 'right' }}>
                          {/* sparkline placeholder — real data needs historical prices per symbol */}
                          <div className="flex justify-end">
                            <Sparkline
                              data={generateFakeSpark(sig.entry_price, sig.stop_loss, sig.take_profit)}
                              width={60}
                              height={24}
                            />
                          </div>
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-(--color-text)">
                          {/* Live LTP: neutral text, 250ms directional flash on tick
                              (PriceCell) — never a persistent bull-green (was misleading
                              on down-ticks). */}
                          <PriceCell value={ltp?.ltp} format={formatCurrency} />
                        </td>
                        <td className="px-3 py-2 text-right"><DirectionBadge dir={sig.direction} /></td>
                        <td className="px-3 py-2 text-right text-(--color-text-muted)">{sig.classification}</td>
                        <td className="px-3 py-2 text-right"><ConfidenceBadge pct={sig.confidence_pct} /></td>
                        <td className="px-3 py-2 text-right font-mono text-(--color-text)">₹{pctFmt(sig.entry_price)}</td>
                        <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--color-bear)' }}>₹{pctFmt(sig.stop_loss)}</td>
                        <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--color-bull)' }}>₹{pctFmt(sig.take_profit)}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatInt(sig.suggested_qty)}</td>
                        <td className="px-3 py-2 text-right text-(--color-text-muted) whitespace-nowrap">{validUntil}</td>
                        <td className="px-3 py-2 text-right">
                          <button
                            onClick={(e) => { e.stopPropagation(); copySignal(sig) }}
                            className="p-1 rounded text-(--color-text-muted) hover:text-(--color-text) hover:bg-(--color-surface-3) transition-colors"
                            title="Copy signal"
                          >
                            <Copy size={12} />
                          </button>
                        </td>
                        <td className="px-3 py-2 text-right">
                          <button
                            onClick={(e) => handlePaperTrade(e, sig)}
                            disabled={tradingSignalId === sig.id}
                            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold transition-colors disabled:opacity-50 border"
                            style={{
                              color: sig.direction === 'SELL' ? 'var(--color-bear)' : 'var(--color-bull)',
                              borderColor: sig.direction === 'SELL' ? 'var(--color-bear)' : 'var(--color-bull)',
                            }}
                            title={sig.direction === 'SELL' ? 'Paper Sell (open short)' : 'Paper Buy (open long)'}
                          >
                            <ShoppingCart size={10} />
                            {tradingSignalId === sig.id
                              ? '…'
                              : sig.direction === 'SELL' ? 'Sell' : 'Buy'}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Right column: FII/DII chart + filings ── */}
        <div className="flex flex-col gap-3">
          {/* FII/DII mini chart */}
          <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide">
                FII / DII Net (Cash)
              </p>
              <span className="text-xs text-(--color-text-muted)">
                {latestFii?.trade_date ?? '—'}
              </span>
            </div>

            <div className="flex gap-4 mb-3">
              <div>
                <p className="text-[10px] text-(--color-text-muted) uppercase tracking-wide mb-0.5">FII</p>
                <div className="text-sm font-semibold">{crFormat(latestFii?.net_value_cr)}</div>
              </div>
              <div>
                <p className="text-[10px] text-(--color-text-muted) uppercase tracking-wide mb-0.5">DII</p>
                <div className="text-sm font-semibold">{crFormat(latestDii?.net_value_cr)}</div>
              </div>
            </div>

            {fiiDiiChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={80}>
                <BarChart data={fiiDiiChartData} barSize={6} margin={{ top: 0, bottom: 0, left: 0, right: 0 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={false} />
                  <ReTooltip
                    contentStyle={{ background: 'var(--color-surface-3)', border: '1px solid var(--color-border)', borderRadius: '4px', fontSize: '10px' }}
                    formatter={(v, name) => { const n = Number(v ?? 0); return [`${n > 0 ? '+' : ''}${formatInt(n)} Cr`, String(name).toUpperCase()] }}
                  />
                  <Bar dataKey="fii" name="fii" radius={[2, 2, 0, 0]}>
                    {fiiDiiChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.fii >= 0 ? 'var(--color-bull)' : 'var(--color-bear)'} />
                    ))}
                  </Bar>
                  <Bar dataKey="dii" name="dii" radius={[2, 2, 0, 0]}>
                    {fiiDiiChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.dii >= 0 ? 'var(--color-info)' : 'var(--color-warning)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-20 flex items-center justify-center text-xs text-(--color-text-muted)">No flow data</div>
            )}
          </div>

          {/* Provisional confidence leaderboard (3.5) */}
          <ProvisionalPanel />

          {/* Filings panel */}
          <FilingsPanel hours={24} />
        </div>
      </div>

      {selectedSignal && (
        <SignalDetailModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
      )}
    </div>
  )
}

function generateFakeSpark(entry: string, sl: string, tp: string): number[] {
  const e = parseFloat(entry)
  const s = parseFloat(sl)
  const t = parseFloat(tp)
  const mid = (s + t) / 2
  return [s + (mid - s) * 0.3, s + (e - s) * 0.6, e, e + (t - e) * 0.2, e + (t - e) * 0.4, e, e + (t - e) * 0.3]
}

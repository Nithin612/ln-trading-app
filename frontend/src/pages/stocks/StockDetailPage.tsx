import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, TrendingUp } from 'lucide-react'
import {
  ComposedChart, Line, Bar, XAxis, YAxis, ResponsiveContainer,
  Tooltip as ReTooltip, ReferenceLine, CartesianGrid,
} from 'recharts'
import { useAuth } from '@/hooks/useAuth'
import { stocksApi } from '@/lib/api/stocks'
import { marketDataApi } from '@/lib/api/market_data'
import { signalsApi } from '@/lib/api/signals'
import { filingsApi } from '@/lib/api/filings'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { TagPicker } from '@/features/categories/TagPicker'
import { CandlestickChart, type OhlcvBar } from '@/components/charts/CandlestickChart'
import { useLiveQuotes } from '@/hooks/useLiveQuotes'

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-2">
      <span className="text-sm text-(--color-text-muted)">{label}</span>
      <span className="text-sm text-(--color-text) font-medium">{value ?? '—'}</span>
    </div>
  )
}

type Timeframe = '1D' | '5D' | '1M' | '3M' | '6M' | '1Y'

function tfToLimit(tf: Timeframe): number {
  return { '1D': 1, '5D': 5, '1M': 30, '3M': 90, '6M': 180, '1Y': 365 }[tf]
}

function calcEMA(data: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1)
  const result: (number | null)[] = Array(data.length).fill(null)
  let ema: number | null = null
  for (let i = 0; i < data.length; i++) {
    if (ema === null) {
      if (i < period - 1) continue
      ema = data.slice(0, period).reduce((a, b) => a + b, 0) / period
    } else {
      ema = data[i] * k + ema * (1 - k)
    }
    result[i] = Math.round(ema * 100) / 100
  }
  return result
}

function calcRSI(closes: number[], period = 14): (number | null)[] {
  const result: (number | null)[] = Array(closes.length).fill(null)
  if (closes.length < period + 1) return result
  for (let i = period; i < closes.length; i++) {
    let gains = 0, losses = 0
    for (let j = i - period + 1; j <= i; j++) {
      const diff = closes[j] - closes[j - 1]
      if (diff > 0) gains += diff; else losses -= diff
    }
    const rs = losses === 0 ? 100 : gains / losses
    result[i] = Math.round((100 - 100 / (1 + rs)) * 100) / 100
  }
  return result
}

export function StockDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { accessToken } = useAuth()
  const [timeframe, setTimeframe] = useState<Timeframe>('1Y')
  const [showEma20, setShowEma20] = useState(false)
  const [showEma50, setShowEma50] = useState(false)
  const [showEma200, setShowEma200] = useState(false)

  const { data: stock, isLoading, isError } = useQuery({
    queryKey: ['stock', id],
    queryFn: () => stocksApi.get(Number(id), accessToken!),
    enabled: !!accessToken && !!id,
  })

  const { data: ohlcv, isLoading: ohlcvLoading } = useQuery({
    queryKey: ['ohlcv', id, timeframe],
    queryFn: () => marketDataApi.getOhlcv(Number(id), { limit: tfToLimit(timeframe) }, accessToken!),
    enabled: !!accessToken && !!id && !!stock,
  })

  const { data: signalsData } = useQuery({
    queryKey: ['signals-stock', id],
    queryFn: () => signalsApi.getActive({ limit: 20 }, accessToken!),
    enabled: !!accessToken && !!id,
    select: (data) => ({ ...data, signals: data.signals.filter((s) => s.stock_id === Number(id)) }),
  })

  const { data: filingsData } = useQuery({
    queryKey: ['filings-stock', id],
    queryFn: () => filingsApi.getByStock(Number(id), { days: 90, limit: 20 }, accessToken!),
    enabled: !!accessToken && !!id,
  })

  const { data: dealsData } = useQuery({
    queryKey: ['deals-stock', id],
    queryFn: () => marketDataApi.getBulkBlockDeals({ stockId: Number(id), limit: 30 }, accessToken!),
    enabled: !!accessToken && !!id,
  })

  const { quotes: liveQuotes } = useLiveQuotes(stock ? [stock.symbol] : [])
  const ltp = stock ? liveQuotes[stock.symbol] : undefined

  const bars = ohlcv?.bars ?? []
  const chartBars: OhlcvBar[] = bars.map((b) => ({
    time: b.time.slice(0, 10),
    open: parseFloat(b.open),
    high: parseFloat(b.high),
    low: parseFloat(b.low),
    close: parseFloat(b.close),
    volume: b.volume,
  }))

  const closes = useMemo(() => chartBars.map((b) => b.close), [chartBars])
  const ema20 = useMemo(() => calcEMA(closes, 20), [closes])
  const ema50 = useMemo(() => calcEMA(closes, 50), [closes])
  const ema200 = useMemo(() => calcEMA(closes, 200), [closes])
  const rsi14 = useMemo(() => calcRSI(closes), [closes])

  const volumeData = chartBars.map((b, i) => ({
    time: b.time,
    volume: b.volume,
    color: b.close >= b.open ? 'var(--color-bull)' : 'var(--color-bear)',
    ema20: showEma20 ? ema20[i] : undefined,
    ema50: showEma50 ? ema50[i] : undefined,
    ema200: showEma200 ? ema200[i] : undefined,
  }))

  const rsiData = rsi14.map((v, i) => ({ time: chartBars[i]?.time, rsi: v })).filter((d) => d.rsi !== null)

  if (isLoading) {
    return (
      <div className="max-w-5xl space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (isError || !stock) {
    return (
      <EmptyState
        title="Stock not found"
        description="This stock ID does not exist or you don't have access to it."
        action={<Link to="/stocks" className="btn btn-ghost text-sm">← Back to Stocks</Link>}
      />
    )
  }

  return (
    <div className="max-w-5xl space-y-4">
      <Link
        to="/stocks"
        className="inline-flex items-center gap-1.5 text-sm text-(--color-text-muted) hover:text-(--color-text)"
      >
        <ArrowLeft size={14} /> Back to Stocks
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold font-mono text-(--color-accent)">{stock.symbol}</h1>
              {ltp && (
                <span className="text-lg font-semibold font-mono" style={{ color: 'var(--color-bull)' }}>
                  ₹{ltp.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              )}
              {ltp && (
                <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-bull)' }}>
                  <TrendingUp size={12} /> Live
                </span>
              )}
            </div>
            <p className="text-(--color-text-muted) text-sm mt-0.5">{stock.company_name}</p>
          </div>
        </div>
        <div className="flex gap-1.5 flex-wrap justify-end">
          {stock.is_nifty50 && <Badge className="bg-blue-950 text-blue-300 border-blue-800 border">Nifty 50</Badge>}
          {stock.is_banknifty && <Badge className="bg-purple-950 text-purple-300 border-purple-800 border">Bank Nifty</Badge>}
          {stock.is_finnifty && <Badge className="bg-teal-950 text-teal-300 border-teal-800 border">Fin Nifty</Badge>}
          {stock.is_fno && <Badge className="bg-amber-950 text-amber-300 border-amber-800 border">F&amp;O</Badge>}
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="chart">
        <TabsList>
          <TabsTrigger value="chart">Price History</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="signals">
            Signals {signalsData?.signals.length ? `(${signalsData.signals.length})` : ''}
          </TabsTrigger>
          <TabsTrigger value="filings">
            Filings {filingsData?.total ? `(${filingsData.total})` : ''}
          </TabsTrigger>
          <TabsTrigger value="deals">
            Bulk &amp; Block {dealsData?.total ? `(${dealsData.total})` : ''}
          </TabsTrigger>
        </TabsList>

        {/* Chart tab */}
        <TabsContent value="chart" className="pt-4 space-y-3">
          {/* Timeframe + EMA toggles */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex rounded overflow-hidden border border-(--color-border)">
              {(['1D', '5D', '1M', '3M', '6M', '1Y'] as Timeframe[]).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className="px-3 py-1 text-xs font-medium transition-colors"
                  style={{
                    background: timeframe === tf ? 'var(--color-accent)' : 'var(--color-surface-3)',
                    color: timeframe === tf ? '#fff' : 'var(--color-text-muted)',
                  }}
                >
                  {tf}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 text-xs text-(--color-text-muted)">
              {[
                { label: 'EMA 20', show: showEma20, set: setShowEma20, color: '#f59e0b' },
                { label: 'EMA 50', show: showEma50, set: setShowEma50, color: '#8b5cf6' },
                { label: 'EMA 200', show: showEma200, set: setShowEma200, color: '#ec4899' },
              ].map(({ label, show, set, color }) => (
                <button
                  key={label}
                  onClick={() => set(!show)}
                  className="flex items-center gap-1 px-2 py-0.5 rounded border transition-colors"
                  style={{
                    borderColor: show ? color : 'var(--color-border)',
                    color: show ? color : 'var(--color-text-muted)',
                    background: show ? `${color}15` : 'transparent',
                  }}
                >
                  <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {ohlcvLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : chartBars.length === 0 ? (
            <EmptyState title="No price data available" description="Price history not yet ingested for this stock." />
          ) : (
            <>
              {/* Candlestick chart — EMA overlays rendered as SVG lines would need chart lib support.
                  For now, we render EMA data beneath in a separate recharts overlay chart */}
              <CandlestickChart bars={chartBars} height={320} />

              {/* Volume panel */}
              <div className="mt-1">
                <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-1">Volume</p>
                <ResponsiveContainer width="100%" height={60}>
                  <ComposedChart data={volumeData} margin={{ top: 0, bottom: 0, left: 0, right: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-chart-grid)" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis hide />
                    <ReTooltip
                      contentStyle={{ background: 'var(--color-surface-3)', border: '1px solid var(--color-border)', borderRadius: '4px', fontSize: '10px' }}
                      formatter={(v) => [Number(v).toLocaleString('en-IN'), 'Volume']}
                      labelFormatter={(l) => String(l ?? '')}
                    />
                    <Bar dataKey="volume" fill="var(--color-accent)" opacity={0.6} radius={[1, 1, 0, 0]} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* RSI panel */}
              {rsiData.length > 0 && (
                <div className="mt-1">
                  <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-1">RSI (14)</p>
                  <ResponsiveContainer width="100%" height={70}>
                    <ComposedChart data={rsiData} margin={{ top: 4, bottom: 0, left: 0, right: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-chart-grid)" vertical={false} />
                      <XAxis dataKey="time" hide />
                      <YAxis domain={[0, 100]} hide />
                      <ReferenceLine y={70} stroke="var(--color-bear)" strokeDasharray="3 3" strokeOpacity={0.5} />
                      <ReferenceLine y={30} stroke="var(--color-bull)" strokeDasharray="3 3" strokeOpacity={0.5} />
                      <ReTooltip
                        contentStyle={{ background: 'var(--color-surface-3)', border: '1px solid var(--color-border)', borderRadius: '4px', fontSize: '10px' }}
                        formatter={(v) => [Number(v).toFixed(1), 'RSI']}
                      />
                      <Line type="monotone" dataKey="rsi" stroke="var(--color-accent)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </TabsContent>

        {/* Details tab */}
        <TabsContent value="details" className="pt-4">
          <div className="card">
            <div className="divide-y divide-(--color-border)">
              <DetailRow label="Exchange" value={stock.exchange} />
              <DetailRow label="ISIN" value={stock.isin} />
              <DetailRow label="Sector" value={stock.sector} />
              <DetailRow label="Industry" value={stock.industry} />
              <DetailRow
                label="Market Cap (Cr)"
                value={stock.market_cap_cr ? `₹${Number(stock.market_cap_cr).toLocaleString('en-IN')}` : '—'}
              />
              <DetailRow label="Lot Size" value={stock.lot_size > 1 ? stock.lot_size.toLocaleString() : '1 (equity)'} />
              <DetailRow label="Tick Size" value={`₹${stock.tick_size}`} />
              <DetailRow label="Listed On" value={stock.listed_on} />
            </div>
            <Separator className="bg-(--color-border) mt-4 mb-4" />
            <div>
              <p className="text-xs text-(--color-text-muted) mb-2 uppercase tracking-wide">Categories</p>
              <TagPicker stockId={stock.id} />
            </div>
          </div>
        </TabsContent>

        {/* Active signals tab */}
        <TabsContent value="signals" className="pt-4">
          {!signalsData?.signals.length ? (
            <EmptyState title="No active signals" description="No confluence signals for this stock right now." />
          ) : (
            <div className="rounded-lg border border-(--color-border) overflow-hidden">
              <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr className="border-b border-(--color-border) bg-(--color-surface-2)">
                    {['Dir', 'Class', 'Conf', 'Entry', 'SL', 'TP', 'Qty', 'Valid until'].map((h) => (
                      <th key={h} className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) text-left">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {signalsData.signals.map((sig) => (
                    <tr key={sig.id} className="border-b border-(--color-border) hover:bg-(--color-surface-hover)">
                      <td className="px-3 py-2">
                        <span
                          className="px-2 py-0.5 rounded-full text-xs font-bold"
                          style={{
                            background: sig.direction === 'BUY' ? 'rgba(22,163,74,0.15)' : 'rgba(220,38,38,0.15)',
                            color: sig.direction === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)',
                          }}
                        >
                          {sig.direction}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-(--color-text-muted)">{sig.classification}</td>
                      <td className="px-3 py-2 font-mono font-bold" style={{ color: sig.confidence_pct >= 80 ? 'var(--color-bull)' : 'var(--color-neutral)' }}>
                        {sig.confidence_pct}%
                      </td>
                      <td className="px-3 py-2 font-mono">₹{parseFloat(sig.entry_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-bear)' }}>₹{parseFloat(sig.stop_loss).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-bull)' }}>₹{parseFloat(sig.take_profit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className="px-3 py-2 font-mono">{sig.suggested_qty.toLocaleString()}</td>
                      <td className="px-3 py-2 text-(--color-text-muted) whitespace-nowrap">
                        {new Date(sig.validity_until).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        {/* Filings tab */}
        <TabsContent value="filings" className="pt-4">
          {!filingsData?.filings.length ? (
            <EmptyState title="No filings" description="No corporate filings for this stock in the last 90 days." />
          ) : (
            <div className="space-y-2">
              {filingsData.filings.map((f) => (
                <div key={f.id} className="bg-(--color-surface-2) border border-(--color-border) rounded-lg px-4 py-3 flex gap-3 items-start hover:bg-(--color-surface-hover) transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-(--color-surface-3) text-(--color-text-muted)">{f.filing_type}</span>
                      {f.is_high_impact && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded border font-semibold"
                          style={{ color: 'var(--color-error)', borderColor: 'rgba(218,54,51,0.4)', background: 'rgba(218,54,51,0.1)' }}>
                          HIGH IMPACT
                        </span>
                      )}
                      <span className="text-xs text-(--color-text-muted)">{f.filing_date}</span>
                    </div>
                    <p className="text-sm text-(--color-text) truncate" title={f.headline}>{f.headline}</p>
                  </div>
                  {f.source_url && (
                    <a href={f.source_url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-(--color-accent) hover:underline flex-shrink-0">
                      PDF →
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Bulk & Block Deals tab */}
        <TabsContent value="deals" className="pt-4">
          {!dealsData?.items.length ? (
            <EmptyState title="No bulk/block deals" description="No deals recorded for this stock." />
          ) : (
            <div className="rounded-lg border border-(--color-border) overflow-hidden">
              <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr className="border-b border-(--color-border) bg-(--color-surface-2)">
                    {['Date', 'Type', 'Client', 'Txn', 'Qty', 'Price', 'Value (Cr)'].map((h) => (
                      <th key={h} className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) text-left">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dealsData.items.map((deal) => (
                    <tr key={deal.id} className="border-b border-(--color-border) hover:bg-(--color-surface-hover)">
                      <td className="px-3 py-2 text-(--color-text-muted)">{deal.trade_date}</td>
                      <td className="px-3 py-2">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-(--color-surface-3) text-(--color-text-muted)">
                          {deal.deal_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-(--color-text) max-w-[160px] truncate">{deal.client_name ?? '—'}</td>
                      <td className="px-3 py-2">
                        <span style={{ color: deal.transaction === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)', fontWeight: 600 }}>
                          {deal.transaction}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono">{deal.quantity.toLocaleString('en-IN')}</td>
                      <td className="px-3 py-2 font-mono">₹{parseFloat(deal.price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td className="px-3 py-2 font-mono">{parseFloat(deal.value_cr).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

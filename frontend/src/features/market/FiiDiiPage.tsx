import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip as ReTooltip, Cell,
  CartesianGrid, Legend,
} from 'recharts'
import { useAuth } from '@/hooks/useAuth'
import { marketDataApi } from '@/lib/api/market_data'
import { PageHeader } from '@/components/layout/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { formatINR, formatInt } from '@/lib/format'

type Segment = 'ALL' | 'cash' | 'futures' | 'options'
type InvestorType = 'ALL' | 'FII' | 'DII'

function crFormat(val: string) {
  const n = parseFloat(val)
  return (
    <span style={{ color: n >= 0 ? 'var(--color-bull)' : 'var(--color-bear)', fontWeight: 600 }}>
      {n >= 0 ? '+' : ''}{formatINR(n)} Cr
    </span>
  )
}

function exportCsv(rows: ReturnType<typeof buildTableRows>) {
  const header = 'Date,Type,Segment,Buy (Cr),Sell (Cr),Net (Cr),Cumulative Net (Cr)'
  const lines = rows.map((r) =>
    [r.trade_date, r.investor_type, r.segment, r.buy_value_cr, r.sell_value_cr, r.net_value_cr, r.cumNet.toFixed(2)].join(','),
  )
  const csv = [header, ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'fii-dii.csv'; a.click()
  URL.revokeObjectURL(url)
}

interface TableRow {
  trade_date: string
  investor_type: string
  segment: string
  buy_value_cr: string
  sell_value_cr: string
  net_value_cr: string
  cumNet: number
}

function buildTableRows(
  rows: { trade_date: string; investor_type: string; segment: string; buy_value_cr: string; sell_value_cr: string; net_value_cr: string }[],
): TableRow[] {
  let cum = 0
  return rows.map((r) => {
    cum += parseFloat(r.net_value_cr)
    return { ...r, cumNet: Math.round(cum * 100) / 100 }
  })
}

export function FiiDiiPage() {
  const { accessToken } = useAuth()
  const [days, setDays] = useState(30)
  const [segment, setSegment] = useState<Segment>('ALL')
  const [investorType, setInvestorType] = useState<InvestorType>('ALL')

  const toDate = useMemo(() => new Date().toISOString().slice(0, 10), [])
  const fromDate = useMemo(() => {
    const d = new Date(); d.setDate(d.getDate() - days)
    return d.toISOString().slice(0, 10)
  }, [days])

  const { data, isLoading } = useQuery({
    queryKey: ['fii-dii', days],
    queryFn: () => marketDataApi.getFiiDii({ fromDate, toDate, limit: days * 6 }, accessToken!),
    enabled: !!accessToken,
  })

  const allRows = useMemo(() => data?.rows ?? [], [data])

  const filteredRows = useMemo(() => {
    let rows = allRows
    if (segment !== 'ALL') rows = rows.filter((r) => r.segment === segment)
    if (investorType !== 'ALL') rows = rows.filter((r) => r.investor_type === investorType)
    return rows
  }, [allRows, segment, investorType])

  const cashRows = allRows.filter((r) => r.segment === 'cash')
  const latestFii = cashRows.find((r) => r.investor_type === 'FII')
  const latestDii = cashRows.find((r) => r.investor_type === 'DII')

  // Combined chart data: group by date, FII + DII net
  const combinedChartData = useMemo(() => {
    const seg = segment === 'ALL' ? 'cash' : segment
    const byDate = new Map<string, { fii: number; dii: number }>()
    for (const r of allRows.filter((x) => x.segment === seg)) {
      if (!byDate.has(r.trade_date)) byDate.set(r.trade_date, { fii: 0, dii: 0 })
      const entry = byDate.get(r.trade_date)!
      if (r.investor_type === 'FII') entry.fii = parseFloat(r.net_value_cr)
      if (r.investor_type === 'DII') entry.dii = parseFloat(r.net_value_cr)
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({ date: date.slice(5), ...vals }))
  }, [allRows, segment])

  const tableRows = useMemo(() => buildTableRows(filteredRows), [filteredRows])

  return (
    <div className="space-y-5">
      <PageHeader
        title="FII / DII Flows"
        subtitle="Institutional buying and selling activity (NSE)"
      />

      {/* Controls */}
      <div className="flex gap-3 flex-wrap items-center">
        {/* Days */}
        <div className="flex rounded overflow-hidden border border-(--color-border)">
          {[7, 15, 30, 60].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className="px-3 py-1 text-xs font-medium transition-colors"
              style={{
                background: days === d ? 'var(--color-accent)' : 'var(--color-surface-3)',
                color: days === d ? 'var(--color-primary-foreground)' : 'var(--color-text-muted)',
              }}
            >
              {d}D
            </button>
          ))}
        </div>

        {/* Segment filter */}
        <div className="flex rounded overflow-hidden border border-(--color-border)">
          {([['ALL', 'All'], ['cash', 'Cash'], ['futures', 'Futures'], ['options', 'Options']] as [Segment, string][]).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setSegment(val)}
              className="px-3 py-1 text-xs font-medium transition-colors"
              style={{
                background: segment === val ? 'var(--color-accent)' : 'var(--color-surface-3)',
                color: segment === val ? 'var(--color-primary-foreground)' : 'var(--color-text-muted)',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Investor type */}
        <div className="flex rounded overflow-hidden border border-(--color-border)">
          {(['ALL', 'FII', 'DII'] as InvestorType[]).map((v) => (
            <button
              key={v}
              onClick={() => setInvestorType(v)}
              className="px-3 py-1 text-xs font-medium transition-colors"
              style={{
                background: investorType === v ? 'var(--color-accent)' : 'var(--color-surface-3)',
                color: investorType === v ? 'var(--color-primary-foreground)' : 'var(--color-text-muted)',
              }}
            >
              {v}
            </button>
          ))}
        </div>

        {tableRows.length > 0 && (
          <button
            onClick={() => exportCsv(tableRows)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-(--color-border) text-xs text-(--color-text-muted) hover:bg-(--color-surface-3) transition-colors ml-auto"
          >
            <Download size={12} /> Export CSV
          </button>
        )}
      </div>

      {isLoading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Skeleton className="h-28" /><Skeleton className="h-28" />
          </div>
          <Skeleton className="h-48" />
        </div>
      )}

      {!isLoading && (!data || data.total === 0) && (
        <EmptyState
          title="No FII/DII data"
          description="No data for this period. Run POST /api/v1/market/ingest/fii-dii to pull from NSE."
        />
      )}

      {!isLoading && data && data.total > 0 && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card">
              <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-2">FII Latest (Cash)</p>
              {latestFii ? (
                <>
                  <p className="text-xs text-(--color-text-muted) mb-2">{latestFii.trade_date}</p>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-(--color-text-muted)">Buy</span>
                      <span className="font-mono">₹{formatInt(parseFloat(latestFii.buy_value_cr))} Cr</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-(--color-text-muted)">Sell</span>
                      <span className="font-mono">₹{formatInt(parseFloat(latestFii.sell_value_cr))} Cr</span>
                    </div>
                    <div className="flex justify-between font-semibold border-t border-(--color-border) pt-1 mt-1">
                      <span className="text-(--color-text-muted)">Net</span>
                      {crFormat(latestFii.net_value_cr)}
                    </div>
                  </div>
                </>
              ) : <p className="text-sm text-(--color-text-muted)">No data</p>}
            </div>

            <div className="card">
              <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-2">DII Latest (Cash)</p>
              {latestDii ? (
                <>
                  <p className="text-xs text-(--color-text-muted) mb-2">{latestDii.trade_date}</p>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-(--color-text-muted)">Buy</span>
                      <span className="font-mono">₹{formatInt(parseFloat(latestDii.buy_value_cr))} Cr</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-(--color-text-muted)">Sell</span>
                      <span className="font-mono">₹{formatInt(parseFloat(latestDii.sell_value_cr))} Cr</span>
                    </div>
                    <div className="flex justify-between font-semibold border-t border-(--color-border) pt-1 mt-1">
                      <span className="text-(--color-text-muted)">Net</span>
                      {crFormat(latestDii.net_value_cr)}
                    </div>
                  </div>
                </>
              ) : <p className="text-sm text-(--color-text-muted)">No data</p>}
            </div>
          </div>

          {/* Combined FII + DII net chart */}
          <div className="card">
            <p className="text-xs text-(--color-text-muted) uppercase tracking-wide mb-3">
              FII + DII Net — {segment === 'ALL' ? 'Cash' : segment} — Last {days} days
            </p>
            {combinedChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={combinedChartData} barSize={8} barCategoryGap="20%">
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-chart-grid)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={false} width={50}
                    tickFormatter={(v: number) => `${formatInt(v / 1000)}k`} />
                  <ReTooltip
                    contentStyle={{ background: 'var(--color-surface-3)', border: '1px solid var(--color-border)', borderRadius: '4px', fontSize: '11px' }}
                    formatter={(v, name) => { const n = Number(v ?? 0); return [`${n > 0 ? '+' : ''}${formatInt(n)} Cr`, String(name).toUpperCase()] }}
                  />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: '11px', color: 'var(--color-text-muted)' }} />
                  <Bar dataKey="fii" name="fii" radius={[2, 2, 0, 0]}>
                    {combinedChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.fii >= 0 ? 'var(--color-bull)' : 'var(--color-bear)'} />
                    ))}
                  </Bar>
                  <Bar dataKey="dii" name="dii" radius={[2, 2, 0, 0]}>
                    {combinedChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.dii >= 0 ? 'var(--color-info)' : 'var(--color-warning)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-40 flex items-center justify-center text-xs text-(--color-text-muted)">No chart data for this selection</div>
            )}
          </div>

          {/* All rows table */}
          <div className="card overflow-hidden p-0">
            <div className="px-4 py-3 border-b border-(--color-border)">
              <p className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide">
                All Rows {filteredRows.length !== allRows.length ? `(${filteredRows.length} filtered)` : `(${allRows.length})`}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr className="border-b border-(--color-border) bg-(--color-surface-2) sticky top-0">
                    {['Date', 'Type', 'Segment', 'Buy (Cr)', 'Sell (Cr)', 'Net (Cr)', 'Cum. Net (Cr)'].map((h) => (
                      <th key={h} className="px-3 py-2 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted)"
                        style={{ textAlign: ['Date', 'Type', 'Segment'].includes(h) ? 'left' : 'right' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.length === 0 ? (
                    <tr><td colSpan={7}><EmptyState title="No rows" description="Adjust filters to see data." /></td></tr>
                  ) : (
                    tableRows.map((r, i) => (
                      <tr key={i} className="border-b border-(--color-border)/40 hover:bg-(--color-surface-hover) transition-colors">
                        <td className="px-3 py-2 text-(--color-text-muted)">{r.trade_date}</td>
                        <td className="px-3 py-2 font-mono font-semibold" style={{ color: r.investor_type === 'FII' ? 'var(--color-bull)' : 'var(--color-info)' }}>{r.investor_type}</td>
                        <td className="px-3 py-2 text-(--color-text-muted)">{r.segment}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatInt(parseFloat(r.buy_value_cr))}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatInt(parseFloat(r.sell_value_cr))}</td>
                        <td className="px-3 py-2 text-right">{crFormat(r.net_value_cr)}</td>
                        <td className="px-3 py-2 text-right font-mono" style={{ color: r.cumNet >= 0 ? 'var(--color-bull)' : 'var(--color-bear)' }}>
                          {r.cumNet >= 0 ? '+' : ''}{formatInt(r.cumNet)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

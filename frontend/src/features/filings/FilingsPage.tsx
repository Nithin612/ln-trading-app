import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Search } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { filingsApi } from '@/lib/api/filings'
import { DateRangePicker } from '@/components/ui/date-range-picker'
import { Pagination } from '@/components/ui/pagination'
import { SkeletonTable } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { SimpleSelect } from '@/components/ui/simple-select'
import { Input } from '@/components/ui/input'

const FILING_TYPES = [
  '', 'earnings', 'board_meeting', 'dividend', 'split', 'bonus', 'merger', 'agm', 'rating_change', 'other',
]

const TYPE_LABELS: Record<string, string> = {
  earnings: 'Earnings', board_meeting: 'Board Meeting', dividend: 'Dividend',
  split: 'Split', bonus: 'Bonus', merger: 'Merger', agm: 'AGM',
  rating_change: 'Rating Change', other: 'Other',
}

const TYPE_ICONS: Record<string, string> = {
  earnings: '📊', board_meeting: '📋', dividend: '💰', split: '✂️',
  bonus: '🎁', merger: '🤝', agm: '🏛️', rating_change: '⭐', other: '📄',
}

function defaultDateRange() {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 7)
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  }
}

const PAGE_SIZE = 25

export function FilingsPage() {
  const { accessToken } = useAuth()
  const [dateRange, setDateRange] = useState(defaultDateRange)
  const [filingType, setFilingType] = useState('')
  const [symbolSearch, setSymbolSearch] = useState('')
  const [debouncedSymbol, setDebouncedSymbol] = useState('')
  const [page, setPage] = useState(1)

  const offset = (page - 1) * PAGE_SIZE

  // hours = days * 24 (we'll pass a large hours value if date range is set)
  const hours = useMemo(() => {
    const from = new Date(dateRange.from)
    const to = new Date(dateRange.to)
    const diffMs = to.getTime() - from.getTime() + 86400000 // include full end day
    return Math.ceil(diffMs / 3600000)
  }, [dateRange])

  const { data, isLoading } = useQuery({
    queryKey: ['filings-page', hours, filingType, offset],
    queryFn: () =>
      filingsApi.getRecent(
        { hours, filingType: filingType || undefined, limit: PAGE_SIZE, offset },
        accessToken!,
      ),
    enabled: !!accessToken,
  })

  const filings = (data?.filings ?? []).filter((f) =>
    !debouncedSymbol || f.symbol.toLowerCase().includes(debouncedSymbol.toLowerCase()),
  )

  const total = data?.total ?? 0
  const pages = Math.ceil(total / PAGE_SIZE)

  function handleSymbolSearch(val: string) {
    setSymbolSearch(val)
    clearTimeout((window as typeof window & { _filingTimer?: ReturnType<typeof setTimeout> })._filingTimer)
    ;(window as typeof window & { _filingTimer?: ReturnType<typeof setTimeout> })._filingTimer = setTimeout(() => {
      setDebouncedSymbol(val)
      setPage(1)
    }, 300)
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-(--color-text)">Corporate Filings</h1>
        <p className="text-sm text-(--color-text-muted)">Earnings, board meetings, dividends, splits and more</p>
      </div>

      {/* Filters */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4 flex flex-wrap gap-4 items-end">
        <DateRangePicker
          label="Date range"
          value={dateRange}
          onChange={(r) => { setDateRange(r); setPage(1) }}
          maxDate={new Date().toISOString().slice(0, 10)}
        />

        <div className="flex flex-col gap-1">
          <span className="text-xs text-(--color-text-muted)">Filing type</span>
          <SimpleSelect
            value={filingType}
            placeholder="All types"
            options={[
              { value: '', label: 'All types' },
              ...FILING_TYPES.filter(Boolean).map((t) => ({ value: t, label: TYPE_LABELS[t] ?? t })),
            ]}
            onChange={(v) => { setFilingType(v); setPage(1) }}
          />
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs text-(--color-text-muted)">Symbol</span>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-(--color-text-muted) pointer-events-none" />
            <Input
              value={symbolSearch}
              onChange={(e) => handleSymbolSearch(e.target.value)}
              placeholder="e.g. RELIANCE"
              className="pl-7 w-40"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg overflow-hidden">
        {isLoading ? (
          <SkeletonTable rows={8} cols={5} />
        ) : filings.length === 0 ? (
          <EmptyState
            title="No filings found"
            description="Try a different date range, type, or symbol."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="border-b border-(--color-border) bg-(--color-surface-2) sticky top-0">
                  <th className="px-4 py-3 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) text-left w-28">Date</th>
                  <th className="px-4 py-3 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) text-left w-24">Symbol</th>
                  <th className="px-4 py-3 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) text-left w-32">Type</th>
                  <th className="px-4 py-3 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) text-left">Headline</th>
                  <th className="px-4 py-3 text-[10px] uppercase tracking-wide font-medium text-(--color-text-muted) text-left w-14">Source</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {filings.map((f) => (
                  <tr key={f.id} className="border-b border-(--color-border)/50 hover:bg-(--color-surface-hover) transition-colors">
                    <td className="px-4 py-3 text-xs text-(--color-text-muted) whitespace-nowrap">
                      {new Date(f.filing_time).toLocaleString('en-IN', {
                        timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short',
                        hour: '2-digit', minute: '2-digit',
                      })} IST
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono font-bold text-sm text-(--color-accent)">{f.symbol}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">{TYPE_ICONS[f.filing_type] ?? '📄'}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded bg-(--color-surface-3) text-(--color-text-muted)">
                          {TYPE_LABELS[f.filing_type] ?? f.filing_type}
                        </span>
                        {f.is_high_impact && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded border font-semibold"
                            style={{ color: 'var(--color-error)', borderColor: 'rgba(218,54,51,0.4)', background: 'rgba(218,54,51,0.1)' }}>
                            HIGH
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 max-w-0">
                      <p className="text-sm text-(--color-text) truncate" title={f.headline}>{f.headline}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-(--color-text-muted)">{f.source}</td>
                    <td className="px-4 py-3">
                      {f.source_url && (
                        <a href={f.source_url} target="_blank" rel="noopener noreferrer"
                          className="text-(--color-accent) hover:text-(--color-accent-hover) transition-colors">
                          <ExternalLink size={14} />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!isLoading && (
        <Pagination
          page={page}
          pages={pages}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      )}
    </div>
  )
}

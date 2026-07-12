import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Search, ChevronUp, ChevronDown, ChevronsUpDown,
  BarChart2, Settings2, Download, Copy,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { stocksApi, type StockListParams, type Stock } from '@/lib/api/stocks'
import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { SkeletonTable } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Sparkline } from '@/components/ui/sparkline'
import { Popover } from '@/components/ui/popover'
import {
  Select, SelectContent, SelectItem, SelectTrigger,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { seededSpark } from '@/lib/sparkline'

type SortField = 'symbol' | 'company_name' | 'sector' | 'lot_size' | 'market_cap_cr'
type ColKey = 'num' | 'symbol' | 'company_name' | 'sector' | 'market_cap_cr' | 'ltp' | 'indices' | 'lot_size' | 'isin' | 'sparkline' | 'actions'

interface ColDef { key: ColKey; label: string; sortable: boolean }

const COLUMNS: ColDef[] = [
  { key: 'num',          label: '#',       sortable: false },
  { key: 'symbol',       label: 'Symbol',  sortable: true  },
  { key: 'company_name', label: 'Company', sortable: true  },
  { key: 'sector',       label: 'Sector',  sortable: true  },
  { key: 'market_cap_cr',label: 'Mkt Cap', sortable: true  },
  { key: 'ltp',          label: 'LTP',     sortable: false },
  { key: 'indices',      label: 'Indices', sortable: false },
  { key: 'lot_size',     label: 'Lot',     sortable: true  },
  { key: 'isin',         label: 'ISIN',    sortable: false },
  { key: 'sparkline',    label: '7d',      sortable: false },
  { key: 'actions',      label: '',        sortable: false },
]

const DEFAULT_VISIBLE = new Set<ColKey>([
  'num', 'symbol', 'company_name', 'sector', 'market_cap_cr',
  'ltp', 'indices', 'lot_size', 'sparkline', 'actions',
])

function fmtCap(cr: string | null): string {
  if (!cr) return '—'
  const n = Number(cr)
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L Cr`
  if (n >= 1000)   return `₹${(n / 1000).toFixed(1)}K Cr`
  return `₹${n.toFixed(0)} Cr`
}

function exportCsv(items: Stock[]) {
  const headers = ['Symbol', 'Company', 'Sector', 'Mkt Cap (Cr)', 'Indices', 'Lot', 'ISIN', 'Exchange']
  const rows = items.map(s => [
    s.symbol, s.company_name, s.sector ?? '', s.market_cap_cr ?? '',
    [s.is_nifty50 && 'N50', s.is_banknifty && 'BN', s.is_finnifty && 'FN', s.is_fno && 'FO']
      .filter(Boolean).join(' '),
    String(s.lot_size), s.isin ?? '', s.exchange,
  ])
  const csv = [headers, ...rows]
    .map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `stocks-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function SortIcon({ field, active, dir }: { field: SortField; active: SortField; dir: 'asc' | 'desc' }) {
  if (field !== active) return <ChevronsUpDown size={12} className="text-(--color-text-muted) ml-1 inline" />
  return dir === 'asc'
    ? <ChevronUp size={12} className="text-(--color-accent) ml-1 inline" />
    : <ChevronDown size={12} className="text-(--color-accent) ml-1 inline" />
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <Button
      onClick={onClick}
      variant={active ? 'default' : 'outline'}
      size="xs"
      className={cn(
        'rounded-full whitespace-nowrap',
        active
          ? 'bg-(--color-accent) text-white border-(--color-accent) hover:bg-(--color-accent-hover)'
          : 'hover:border-(--color-accent)',
      )}
    >
      {label}
    </Button>
  )
}

type FilterVal = true | undefined

export function StocksPage() {
  const { accessToken } = useAuth()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [sortBy, setSortBy] = useState<SortField>('market_cap_cr')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [filterFno, setFilterFno] = useState<FilterVal>()
  const [filterNifty50, setFilterNifty50] = useState<FilterVal>()
  const [filterBankNifty, setFilterBankNifty] = useState<FilterVal>()
  const [filterFinNifty, setFilterFinNifty] = useState<FilterVal>()
  const [sectorFilter, setSectorFilter] = useState('')
  const [visibleCols, setVisibleCols] = useState<Set<ColKey>>(DEFAULT_VISIBLE)
  const [density, setDensity] = useState<'compact' | 'comfortable'>('compact')

  const params: StockListParams = {
    q: debouncedSearch || undefined,
    is_fno: filterFno,
    is_nifty50: filterNifty50,
    is_banknifty: filterBankNifty,
    is_finnifty: filterFinNifty,
    sector: sectorFilter || undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
    page,
    page_size: pageSize,
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['stocks', params],
    queryFn: () => stocksApi.list(params, accessToken!),
    enabled: !!accessToken,
  })

  const { data: allData } = useQuery({
    queryKey: ['stocks-sectors'],
    queryFn: () => stocksApi.list({ page_size: 2500 }, accessToken!),
    enabled: !!accessToken,
    staleTime: 300_000,
  })

  const symbols = data?.items.map(s => s.symbol) ?? []
  const { quotes, connected } = useLiveQuotes(symbols)

  const sectors = [
    ...new Set((allData?.items ?? []).map(s => s.sector).filter(Boolean) as string[])
  ].sort()

  function handleSort(field: SortField) {
    if (field === sortBy) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortDir(field === 'market_cap_cr' ? 'desc' : 'asc')
    }
    setPage(1)
  }

  function handleSearch(val: string) {
    setSearch(val)
    clearTimeout((window as typeof window & { _searchTimer?: ReturnType<typeof setTimeout> })._searchTimer)
    ;(window as typeof window & { _searchTimer?: ReturnType<typeof setTimeout> })._searchTimer = setTimeout(() => {
      setDebouncedSearch(val)
      setPage(1)
    }, 300)
  }

  function toggleFilter(current: FilterVal, setter: (v: FilterVal) => void) {
    setter(current === undefined ? true : undefined)
    setPage(1)
  }

  function toggleCol(col: ColKey) {
    setVisibleCols(prev => {
      const next = new Set(prev)
      if (next.has(col)) { next.delete(col) } else { next.add(col) }
      return next
    })
  }

  const clearFilters = () => {
    setFilterNifty50(undefined)
    setFilterBankNifty(undefined)
    setFilterFinNifty(undefined)
    setFilterFno(undefined)
    setSearch('')
    setDebouncedSearch('')
    setSectorFilter('')
    setPage(1)
  }

  const hasActiveFilters = !!(filterNifty50 || filterBankNifty || filterFinNifty || filterFno || debouncedSearch || sectorFilter)
  const activeFilterCount = [filterNifty50, filterBankNifty, filterFinNifty, filterFno].filter(Boolean).length + (sectorFilter ? 1 : 0)

  const total = data?.total ?? 0
  const pages = data?.pages ?? 1
  const offset = (page - 1) * pageSize

  const showCol = (col: ColKey) => visibleCols.has(col)
  const rowPy = density === 'comfortable' ? 'py-2.5' : undefined

  return (
    <div className="h-full flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-(--color-text)">Stocks</h1>
          <p className="text-sm text-(--color-text-muted)">
            {total > 0 ? `${total.toLocaleString()} stocks` : isLoading ? 'Loading…' : '0 stocks'}
          </p>
        </div>
        <Link to="/screener" className="btn btn-primary text-sm">Open Screener</Link>
      </div>

      {/* Filter panel */}
      <div className="rounded-lg border border-l-2 border-(--color-border) border-l-(--color-accent)/40 bg-(--color-surface-2) p-3 space-y-2.5 flex-shrink-0">
        {/* Row 1: search + toolbar */}
        <div className="flex gap-2 items-center flex-wrap">
          <div className="relative flex-1 min-w-48 max-w-72">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--color-text-muted)" />
            <Input
              placeholder="Search symbol or company…"
              value={search}
              onChange={e => handleSearch(e.target.value)}
              className="pl-8 h-8 text-sm bg-(--color-surface-3) border-(--color-border) text-(--color-text) placeholder:text-(--color-text-muted) focus-visible:ring-(--color-accent)"
            />
          </div>

          <div className="ml-auto flex gap-2 items-center">
            {/* Density toggle */}
            <div className="flex rounded-md border border-(--color-border) overflow-hidden">
              {(['compact', 'comfortable'] as const).map(d => (
                <Button
                  key={d}
                  onClick={() => setDensity(d)}
                  variant={density === d ? 'default' : 'outline'}
                  size="xs"
                  className={cn(
                    'rounded-none border-0 capitalize',
                    density === d
                      ? 'bg-(--color-accent) text-white'
                      : 'hover:bg-(--color-surface-3)',
                  )}
                >
                  {d}
                </Button>
              ))}
            </div>

            {data?.items && data.items.length > 0 && (
              <Button
                onClick={() => exportCsv(data.items)}
                variant="outline"
                size="xs"
                title="Export visible page as CSV"
              >
                <Download size={12} /> Export
              </Button>
            )}

            <Popover
              align="end"
              trigger={
                <Button variant="outline" size="xs">
                  <Settings2 size={12} /> Columns
                </Button>
              }
            >
              <div className="p-3 space-y-2 min-w-[160px]">
                <p className="text-xs font-semibold text-(--color-text-muted) uppercase tracking-wide mb-2">Visible columns</p>
                {COLUMNS.filter(c => c.key !== 'symbol' && c.key !== 'actions' && c.key !== 'num').map(col => (
                  <label key={col.key} className="flex items-center gap-2 cursor-pointer text-sm text-(--color-text)">
                    <Checkbox
                      checked={visibleCols.has(col.key)}
                      onCheckedChange={() => toggleCol(col.key)}
                    />
                    {col.label || col.key}
                  </label>
                ))}
              </div>
            </Popover>
          </div>
        </div>

        {/* Row 2: filter chips */}
        <div className="flex gap-2 items-center flex-wrap">
          <span className="text-xs font-medium text-(--color-text-muted) select-none flex-shrink-0">
            Filters{activeFilterCount > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-(--color-accent-bg) text-(--color-accent) text-[10px] font-bold">{activeFilterCount}</span>
            )}
          </span>

          <Select
            value={sectorFilter || null}
            onValueChange={(v) => { setSectorFilter(v ?? ''); setPage(1) }}
          >
            <SelectTrigger
              size="sm"
              className="bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus:ring-(--color-accent)"
            >
              <span className="flex flex-1 text-left text-sm">{sectorFilter || 'All sectors'}</span>
            </SelectTrigger>
            <SelectContent className="bg-(--color-surface-3) border-(--color-border) text-(--color-text)">
              <SelectItem value="">All sectors</SelectItem>
              {allData === undefined && (
                <SelectItem value="__loading__" disabled>Loading sectors…</SelectItem>
              )}
              {allData !== undefined && sectors.length === 0 && (
                <SelectItem value="__none__" disabled>No sectors</SelectItem>
              )}
              {sectors.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>

          <div className="w-px h-5 bg-(--color-border)" />

          <FilterChip label="Nifty 50"   active={!!filterNifty50}    onClick={() => toggleFilter(filterNifty50,    setFilterNifty50)}    />
          <FilterChip label="BankNifty"  active={!!filterBankNifty}  onClick={() => toggleFilter(filterBankNifty,  setFilterBankNifty)}  />
          <FilterChip label="FinNifty"   active={!!filterFinNifty}   onClick={() => toggleFilter(filterFinNifty,   setFilterFinNifty)}   />
          <FilterChip label="F&amp;O"    active={!!filterFno}        onClick={() => toggleFilter(filterFno,        setFilterFno)}        />

          {hasActiveFilters && (
            <Button
              onClick={clearFilters}
              variant="ghost"
              size="xs"
              className="text-(--color-text-muted) hover:text-(--color-error)"
            >
              × Clear all
            </Button>
          )}

          {connected && (
            <span className="ml-auto flex items-center gap-1.5 text-xs text-(--color-profit)">
              <span className="w-1.5 h-1.5 rounded-full bg-(--color-profit) animate-pulse" />
              Live
            </span>
          )}
        </div>
      </div>

      {/* Table — flex-1 min-h-0 so it fills remaining height without overflowing */}
      <div className="flex-1 min-h-0 rounded-lg border border-(--color-border) overflow-hidden flex flex-col">
        <div className="overflow-auto flex-1">
        <Table>
          <TableHeader className="sticky top-0 z-10">
            <TableRow className="border-(--color-border) hover:bg-transparent bg-(--color-surface-3)">
              {showCol('num') && (
                <TableHead className="text-(--color-text-muted) w-10 text-right text-xs pr-3">#</TableHead>
              )}
              <TableHead
                className={cn('text-(--color-text-muted) cursor-pointer select-none w-28', sortBy === 'symbol' && 'bg-(--color-accent)/10')}
                onClick={() => handleSort('symbol')}
              >
                <span className="flex items-center">Symbol <SortIcon field="symbol" active={sortBy} dir={sortDir} /></span>
              </TableHead>
              {showCol('company_name') && (
                <TableHead
                  className={cn('text-(--color-text-muted) cursor-pointer select-none', sortBy === 'company_name' && 'bg-(--color-accent)/10')}
                  onClick={() => handleSort('company_name')}
                >
                  <span className="flex items-center">Company <SortIcon field="company_name" active={sortBy} dir={sortDir} /></span>
                </TableHead>
              )}
              {showCol('sector') && (
                <TableHead
                  className={cn('text-(--color-text-muted) cursor-pointer select-none w-36', sortBy === 'sector' && 'bg-(--color-accent)/10')}
                  onClick={() => handleSort('sector')}
                >
                  <span className="flex items-center">Sector <SortIcon field="sector" active={sortBy} dir={sortDir} /></span>
                </TableHead>
              )}
              {showCol('market_cap_cr') && (
                <TableHead
                  className={cn('text-(--color-text-muted) cursor-pointer select-none w-28 text-right', sortBy === 'market_cap_cr' && 'bg-(--color-accent)/10')}
                  onClick={() => handleSort('market_cap_cr')}
                >
                  <span className="flex items-center justify-end">Mkt Cap <SortIcon field="market_cap_cr" active={sortBy} dir={sortDir} /></span>
                </TableHead>
              )}
              {showCol('ltp') && (
                <TableHead className="text-(--color-text-muted) w-24 text-right">LTP</TableHead>
              )}
              {showCol('indices') && (
                <TableHead className="text-(--color-text-muted) w-28">Indices</TableHead>
              )}
              {showCol('lot_size') && (
                <TableHead
                  className={cn('text-(--color-text-muted) cursor-pointer select-none w-16 text-right', sortBy === 'lot_size' && 'bg-(--color-accent)/10')}
                  onClick={() => handleSort('lot_size')}
                >
                  <span className="flex items-center justify-end">Lot <SortIcon field="lot_size" active={sortBy} dir={sortDir} /></span>
                </TableHead>
              )}
              {showCol('isin') && (
                <TableHead className="text-(--color-text-muted) w-32">ISIN</TableHead>
              )}
              {showCol('sparkline') && (
                <TableHead className="text-(--color-text-muted) w-20 text-right">7d</TableHead>
              )}
              {showCol('actions') && (
                <TableHead className="w-8" />
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length} className="p-0">
                  <SkeletonTable rows={8} cols={6} />
                </TableCell>
              </TableRow>
            )}
            {isError && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length} className="text-center py-8 text-(--color-error)">
                  Failed to load stocks.
                </TableCell>
              </TableRow>
            )}
            {!isLoading && !isError && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length} className="p-0">
                  <EmptyState title="No stocks found" description="Try adjusting filters or search query" />
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((stock, idx) => {
              const ltp = quotes[stock.symbol]?.ltp
              return (
                <TableRow
                  key={stock.id}
                  className={cn(
                    'hover:bg-(--color-surface-hover) transition-colors group/row',
                    idx % 2 === 1 ? 'bg-(--color-row-alt)' : 'bg-(--color-surface-2)',
                  )}
                >
                  {showCol('num') && (
                    <TableCell className={cn('text-right text-xs text-(--color-text-muted) font-mono tabular-nums select-none w-10 pr-3', rowPy)}>
                      {offset + idx + 1}
                    </TableCell>
                  )}
                  <TableCell className={cn('w-28', rowPy)}>
                    <div className="flex items-center gap-1.5 group/sym">
                      <Link
                        to={`/stocks/${stock.id}`}
                        className="font-mono font-semibold text-(--color-accent) hover:text-(--color-accent-hover) transition-colors"
                      >
                        {stock.symbol}
                      </Link>
                      <Button
                        onClick={() => void navigator.clipboard.writeText(stock.symbol)}
                        variant="ghost"
                        size="icon-xs"
                        className="opacity-0 group-hover/sym:opacity-100 transition-opacity"
                        title="Copy symbol"
                      >
                        <Copy size={11} />
                      </Button>
                    </div>
                  </TableCell>
                  {showCol('company_name') && (
                    <TableCell className={cn('text-(--color-text) text-sm', rowPy)}>{stock.company_name}</TableCell>
                  )}
                  {showCol('sector') && (
                    <TableCell className={cn('text-(--color-text-muted) text-sm w-36', rowPy)}>{stock.sector ?? '—'}</TableCell>
                  )}
                  {showCol('market_cap_cr') && (
                    <TableCell className={cn('text-right font-mono text-sm text-(--color-text) w-28', rowPy)}>
                      {fmtCap(stock.market_cap_cr)}
                    </TableCell>
                  )}
                  {showCol('ltp') && (
                    <TableCell className={cn('text-right font-mono text-sm w-24', rowPy)}>
                      {ltp !== undefined
                        ? <span className="text-(--color-text)">₹{ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        : <span className="text-(--color-text-muted)">—</span>
                      }
                    </TableCell>
                  )}
                  {showCol('indices') && (
                    <TableCell className={cn('w-28', rowPy)}>
                      <div className="flex gap-1 flex-wrap">
                        {stock.is_nifty50   && <Badge className="text-[10px] px-1.5 py-0 badge-n50">N50</Badge>}
                        {stock.is_banknifty && <Badge className="text-[10px] px-1.5 py-0 badge-bn">BN</Badge>}
                        {stock.is_finnifty  && <Badge className="text-[10px] px-1.5 py-0 badge-fn">FN</Badge>}
                        {stock.is_fno       && <Badge className="text-[10px] px-1.5 py-0 badge-fno">F&amp;O</Badge>}
                      </div>
                    </TableCell>
                  )}
                  {showCol('lot_size') && (
                    <TableCell className={cn('text-right font-mono text-sm text-(--color-text-muted) w-16', rowPy)}>
                      {stock.lot_size > 1 ? stock.lot_size.toLocaleString() : '—'}
                    </TableCell>
                  )}
                  {showCol('isin') && (
                    <TableCell className={cn('font-mono text-xs text-(--color-text-muted) w-32', rowPy)}>{stock.isin ?? '—'}</TableCell>
                  )}
                  {showCol('sparkline') && (
                    <TableCell className={cn('text-right w-20', rowPy)}>
                      <div className="flex justify-end">
                        <Sparkline data={seededSpark(stock.id)} width={60} height={24} />
                      </div>
                    </TableCell>
                  )}
                  {showCol('actions') && (
                    <TableCell className={cn('w-8', rowPy)}>
                      <Link
                        to={`/stocks/${stock.id}`}
                        className="p-1 rounded text-(--color-text-muted) hover:text-(--color-accent) transition-colors inline-flex opacity-0 group-hover/row:opacity-100"
                        title="View chart"
                      >
                        <BarChart2 size={14} />
                      </Link>
                    </TableCell>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
        </div>
      </div>

      <Pagination
        page={page}
        pages={pages}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onPageSizeChange={s => { setPageSize(s); setPage(1) }}
        className="flex-shrink-0"
      />
    </div>
  )
}


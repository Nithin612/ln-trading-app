import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Play, Save, Trash2, BookOpen, Download, Filter } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { stocksApi } from '@/lib/api/stocks'
import { useScreenerStore } from './screenerStore'
import { FilterRow } from './FilterRow'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Sparkline } from '@/components/ui/sparkline'
import { EmptyState } from '@/components/ui/empty-state'
import { SkeletonTable } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { useToast } from '@/hooks/useToast'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { seededSpark } from '@/lib/sparkline'

const STARTER_SCREENS = [
  { name: 'Nifty 50 only', filters: [{ field: 'is_nifty50', op: 'eq', value: true }] },
  { name: 'F&O stocks', filters: [{ field: 'is_fno', op: 'eq', value: true }] },
  { name: 'BankNifty constituents', filters: [{ field: 'is_banknifty', op: 'eq', value: true }] },
  { name: 'Nifty50 F&O', filters: [
    { field: 'is_nifty50', op: 'eq', value: true },
    { field: 'is_fno', op: 'eq', value: true },
  ]},
]

function exportCsv(items: { symbol: string; company_name: string; sector: string | null; market_cap_cr: string | null; lot_size: number }[]) {
  const header = 'Symbol,Company,Sector,Market Cap (Cr),Lot Size'
  const rows = items.map((s) =>
    [s.symbol, `"${s.company_name}"`, s.sector ?? '', s.market_cap_cr ?? '', s.lot_size].join(','),
  )
  const csv = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'screener-results.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export function ScreenerPage() {
  const { accessToken } = useAuth()
  const qc = useQueryClient()
  const store = useScreenerStore()
  const toast = useToast()

  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [saveError, setSaveError] = useState('')

  const { data: savedScreens } = useQuery({
    queryKey: ['screener-saved'],
    queryFn: () => stocksApi.savedList(accessToken!),
    enabled: !!accessToken,
  })

  const runMutation = useMutation({
    mutationFn: () => {
      const req = store.toRequest()
      req.filters = req.filters.map((f) => {
        if (f.op === 'in' && typeof f.value === 'string') {
          return { ...f, value: (f.value as string).split(',').map((s) => s.trim()).filter(Boolean) }
        }
        if (f.op === 'between' && Array.isArray(f.value)) {
          return { ...f, value: (f.value as string[]).map(Number) }
        }
        return f
      })
      return stocksApi.screenerRun(req, accessToken!)
    },
    onSuccess: (result) => {
      store.setResult(result)
      toast.success(`${result.total} stocks matched`)
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const saveMutation = useMutation({
    mutationFn: () => stocksApi.savedCreate(saveName.trim(), store.toRequest(), accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['screener-saved'] })
      setSaveDialogOpen(false)
      setSaveName('')
      setSaveError('')
      toast.success('Screen saved')
    },
    onError: (err: Error) => setSaveError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => stocksApi.savedDelete(id, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['screener-saved'] })
      toast.success('Screen deleted')
    },
  })

  function applyStarter(starter: typeof STARTER_SCREENS[number]) {
    useScreenerStore.setState({
      filters: starter.filters.map((f) => ({ ...f })),
      result: null,
      activeSavedScreen: null,
    })
  }

  const result = store.result
  const isRunning = runMutation.isPending
  const activeFilterCount = store.filters.filter((f) => f.field).length

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[--color-text]">Screener</h1>
          <p className="text-sm text-[--color-text-muted]">Filter stocks by any combination of fields</p>
        </div>
        <Link to="/stocks" className="text-sm text-[--color-text-muted] hover:text-[--color-text]">← All Stocks</Link>
      </div>

      {/* Main two-column grid */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4 overflow-hidden">
        {/* ── Left: Saved screens + starters ── */}
        <aside className="h-full overflow-y-auto space-y-4">
          <div className="card p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-[--color-text-muted]">
              <BookOpen size={14} /> Saved Screens
            </div>
            {savedScreens && savedScreens.length > 0 ? (
              <div className="space-y-1">
                {savedScreens.map((s) => (
                  <div key={s.id} className="flex items-center justify-between group">
                    <Button
                      type="button"
                      variant="ghost"
                      className="text-sm text-[--color-text] hover:text-[--color-accent] truncate flex-1 justify-start h-auto py-1 px-2"
                      onClick={() => store.loadSavedScreen(s)}
                    >
                      <div className="flex flex-col items-start gap-0.5 w-full">
                        <div className="flex items-center gap-1.5">
                          {s.name}
                          {store.activeSavedScreen?.id === s.id && (
                            <span className="text-[10px] text-[--color-accent]">● active</span>
                          )}
                        </div>
                        <p className="text-[10px] text-[--color-text-muted]">
                          {new Date(s.updated_at).toLocaleDateString('en-IN')}
                        </p>
                      </div>
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="opacity-0 group-hover:opacity-100 text-[--color-text-muted] hover:text-[--color-error] transition-all"
                      onClick={() => deleteMutation.mutate(s.id)}
                    >
                      <Trash2 size={12} />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[--color-text-muted]">No saved screens yet.</p>
            )}
          </div>

          <div className="card p-4 space-y-2">
            <p className="text-xs font-semibold text-[--color-text-secondary] uppercase tracking-wider">Quick start</p>
            {STARTER_SCREENS.map((s) => (
              <Button
                key={s.name}
                type="button"
                variant="ghost"
                className="w-full justify-start text-sm text-[--color-text-muted] hover:text-[--color-text]"
                onClick={() => applyStarter(s)}
              >
                {s.name}
              </Button>
            ))}
          </div>
        </aside>

        {/* ── Right: Filter builder + results ── */}
        <div className="h-full flex flex-col gap-4 overflow-hidden">
          {/* Filter builder — left accent border per §9.1 */}
          <div className="flex-shrink-0 rounded-lg border border-l-2 border-[--color-border] border-l-[--color-accent]/40 bg-[--color-surface-2] p-4 space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Filter size={14} className="text-[--color-text-muted]" />
                <span className="text-sm text-[--color-text-secondary]">Match</span>
              </div>
              <div className="flex rounded-md overflow-hidden border border-[--color-border]">
                {(['AND', 'OR'] as const).map((l) => (
                  <Button
                    key={l}
                    type="button"
                    variant={store.logic === l ? 'default' : 'outline'}
                    size="xs"
                    className={`rounded-none border-0 ${
                      store.logic === l
                        ? 'bg-[--color-accent] text-white'
                        : 'bg-[--color-surface-3] hover:bg-[--color-surface-2]'
                    }`}
                    onClick={() => store.setLogic(l)}
                  >
                    {l}
                  </Button>
                ))}
              </div>
              <span className="text-sm text-[--color-text-secondary]">of these filters</span>
              {activeFilterCount > 0 && (
                <Badge className="bg-[--color-accent]/20 text-[--color-accent] border-[--color-accent]/30 border text-xs">
                  Filters ({activeFilterCount})
                </Badge>
              )}
            </div>

            <div className="space-y-2">
              {store.filters.map((filter, i) => (
                <FilterRow
                  key={i}
                  filter={filter}
                  onChange={(patch) => store.updateFilter(i, patch)}
                  onRemove={() => store.removeFilter(i)}
                />
              ))}
            </div>

            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={store.addFilter}
              className="text-[--color-text-muted] hover:text-[--color-accent]"
            >
              <Plus size={13} /> Add filter
            </Button>

            <Separator className="bg-[--color-border]" />

            <div className="flex items-center gap-2 flex-wrap">
              <Button
                onClick={() => runMutation.mutate()}
                disabled={isRunning}
                className="bg-[--color-accent] hover:bg-[--color-accent-hover] text-white"
              >
                <Play size={13} className="mr-1.5" />
                {isRunning ? 'Running…' : 'Run Screen'}
              </Button>

              {result && (
                <>
                  <Button
                    variant="outline"
                    onClick={() => setSaveDialogOpen(true)}
                  >
                    <Save size={13} className="mr-1.5" /> Save Screen
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => exportCsv(result.items)}
                  >
                    <Download size={13} className="mr-1.5" /> Export CSV
                  </Button>
                </>
              )}

              {(store.filters.length > 0 || result) && (
                <Button
                  variant="ghost"
                  onClick={() => { store.resetFilters(); }}
                  className="text-[--color-text-muted] hover:text-[--color-text]"
                >
                  {activeFilterCount > 0 ? `Clear all (${activeFilterCount})` : 'Reset'}
                </Button>
              )}
            </div>
          </div>

          {/* Results zone */}
          <div className="flex-1 min-h-0 rounded-lg border border-[--color-border] overflow-hidden">
            {!isRunning && !result && (
              <div className="h-full flex items-center justify-center">
                <EmptyState
                  title="No results yet"
                  description="Add filters and click Run Screen to see matching stocks"
                />
              </div>
            )}

            {isRunning && (
              <div className="h-full overflow-auto">
                <SkeletonTable rows={6} cols={5} />
              </div>
            )}

            {!isRunning && result && (
              <div className="h-full flex flex-col overflow-hidden">
                <div className="flex-shrink-0 px-3 py-2 border-b border-[--color-border] bg-[--color-surface-2]">
                  <p className="text-sm text-[--color-text-muted]">
                    {result.total.toLocaleString()} stocks matched
                    {result.total > result.limit && ` — showing first ${result.limit}`}
                  </p>
                </div>
                <div className="overflow-auto flex-1">
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent bg-[--color-surface-3]">
                        <TableHead className="w-28">Symbol</TableHead>
                        <TableHead>Company</TableHead>
                        <TableHead className="w-36">Sector</TableHead>
                        <TableHead className="w-24">Indices</TableHead>
                        <TableHead numeric className="w-20">Lot</TableHead>
                        <TableHead numeric className="w-16">7d</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.items.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={6} className="p-0">
                            <EmptyState title="No stocks matched the filters." description="Try relaxing or removing some filters." />
                          </TableCell>
                        </TableRow>
                      )}
                      {result.items.map((stock) => (
                        <TableRow key={stock.id}>
                          <TableCell>
                            <Link to={`/stocks/${stock.id}`} className="font-mono font-semibold text-[--color-accent] hover:text-[--color-accent-hover]">
                              {stock.symbol}
                            </Link>
                          </TableCell>
                          <TableCell className="text-sm text-[--color-text]">{stock.company_name}</TableCell>
                          <TableCell className="text-sm text-[--color-text-muted]">{stock.sector ?? '—'}</TableCell>
                          <TableCell>
                            <div className="flex gap-1 flex-wrap">
                              {stock.is_nifty50   && <Badge className="text-[10px] px-1 py-0 badge-n50">N50</Badge>}
                              {stock.is_banknifty && <Badge className="text-[10px] px-1 py-0 badge-bn">BN</Badge>}
                              {stock.is_finnifty  && <Badge className="text-[10px] px-1 py-0 badge-fn">FN</Badge>}
                              {stock.is_fno       && <Badge className="text-[10px] px-1 py-0 badge-fno">F&amp;O</Badge>}
                            </div>
                          </TableCell>
                          <TableCell numeric className="text-sm text-[--color-text-muted]">
                            {stock.lot_size > 1 ? stock.lot_size.toLocaleString() : '—'}
                          </TableCell>
                          <TableCell numeric>
                            <div className="flex justify-end">
                              <Sparkline data={seededSpark(stock.id)} width={50} height={20} />
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Save dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="bg-[--color-surface-2] border-[--color-border] text-[--color-text]">
          <DialogHeader>
            <DialogTitle className="text-[--color-text]">Save Screen</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <Input
              placeholder="Screen name…"
              value={saveName}
              onChange={(e) => { setSaveName(e.target.value); setSaveError('') }}
              className="bg-[--color-surface-3] border-[--color-border] text-[--color-text] focus-visible:ring-[--color-accent]"
              autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter' && saveName.trim()) saveMutation.mutate() }}
            />
            {saveError && <p className="text-sm text-[--color-error]">{saveError}</p>}
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => { setSaveDialogOpen(false); setSaveName(''); setSaveError('') }} className="text-[--color-text-muted]">
                Cancel
              </Button>
              <Button
                onClick={() => saveMutation.mutate()}
                disabled={!saveName.trim() || saveMutation.isPending}
                className="bg-[--color-accent] hover:bg-[--color-accent-hover] text-white"
              >
                {saveMutation.isPending ? 'Saving…' : 'Save'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

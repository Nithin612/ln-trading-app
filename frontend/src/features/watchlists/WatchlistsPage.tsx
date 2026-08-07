/**
 * WatchlistsPage — manage named stock sets (Phase 3.5 follow-up slice).
 * Watchlists scope the live-alert fanout (AlertBell selector) and, next
 * slice, the provisional-confidence hot set.
 */

import { memo, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks, Plus, Trash2, X } from 'lucide-react'

import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { PriceCell } from '@/components/ui/PriceCell'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { useAuth } from '@/hooks/useAuth'
import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { formatChange, formatCurrency } from '@/lib/format'
import { stocksApi } from '@/lib/api/stocks'
import { watchlistsApi, type WatchlistItem } from '@/lib/api/watchlists'
import { cn } from '@/lib/utils'

/** Percent move of `ltp` against the last completed close, or null when either
 *  side is missing. A zero prev_close would divide by zero, so it is excluded. */
function changePct(ltp: number | undefined, prevClose: string | null): number | null {
  if (ltp === undefined || prevClose === null) return null
  const prev = parseFloat(prevClose)
  if (!Number.isFinite(prev) || prev === 0) return null
  return ((ltp - prev) / prev) * 100
}

/**
 * One watchlist row, memoised.
 *
 * `quotes` is component state, so every rAF flush re-renders the page. Without
 * memoisation each flush re-runs the parse/format work for every row; PriceCell
 * isolates the flash, not the render. Only rows whose LTP actually moved
 * re-render. (Same reasoning as StylePage's SuggestionRow.)
 */
const WatchlistRow = memo(function WatchlistRow({
  item,
  ltp,
  listName,
  removing,
  onRemove,
}: {
  item: WatchlistItem
  ltp: number | undefined
  listName: string
  removing: boolean
  onRemove: () => void
}) {
  const pct = changePct(ltp, item.prev_close)
  return (
    <TableRow>
      <TableCell className="font-mono font-bold text-(--color-text)">{item.symbol}</TableCell>
      <TableCell className="text-(--color-text-muted) text-xs max-w-[18rem] truncate">
        {item.company_name}
      </TableCell>
      <TableCell numeric>
        <PriceCell value={ltp} format={formatCurrency} />
      </TableCell>
      <TableCell
        numeric
        style={
          pct === null
            ? undefined
            : { color: pct > 0 ? 'var(--color-profit)' : pct < 0 ? 'var(--color-loss)' : undefined }
        }
      >
        {/* Glyph AND colour — colour alone is not a direction (ui rules). */}
        {pct === null ? '—' : formatChange(pct)}
      </TableCell>
      <TableCell numeric className="text-(--color-text-muted)">
        {item.prev_close === null ? '—' : formatCurrency(parseFloat(item.prev_close))}
      </TableCell>
      <TableCell numeric>
        <button
          onClick={onRemove}
          disabled={removing}
          aria-label={`Remove ${item.symbol} from ${listName}`}
          className="p-1 rounded text-(--color-text-muted) hover:text-(--color-loss) hover:bg-(--color-surface-3) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)"
        >
          <X size={14} />
        </button>
      </TableCell>
    </TableRow>
  )
})

export function WatchlistsPage() {
  const { accessToken } = useAuth()
  const token = accessToken ?? ''
  const qc = useQueryClient()

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [newName, setNewName] = useState('')
  const [stockQuery, setStockQuery] = useState('')

  const {
    data: lists,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['watchlists'],
    queryFn: () => watchlistsApi.list(token),
    enabled: accessToken !== null,
  })

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['watchlists'] })

  const createMut = useMutation({
    mutationFn: (name: string) => watchlistsApi.create(name, token),
    onSuccess: (wl) => {
      setNewName('')
      setSelectedId(wl.id)
      invalidate()
    },
  })
  const deleteMut = useMutation({
    mutationFn: (id: number) => watchlistsApi.remove(id, token),
    onSuccess: () => {
      setSelectedId(null)
      invalidate()
    },
  })
  const addMut = useMutation({
    mutationFn: (args: { id: number; stockId: number }) =>
      watchlistsApi.addStock(args.id, args.stockId, token),
    onSuccess: () => {
      setStockQuery('')
      invalidate()
    },
  })
  const removeMut = useMutation({
    mutationFn: (args: { id: number; stockId: number }) =>
      watchlistsApi.removeStock(args.id, args.stockId, token),
    onSuccess: invalidate,
  })

  const query = stockQuery.trim()
  const { data: search } = useQuery({
    queryKey: ['watchlist-stock-search', query],
    queryFn: () => stocksApi.list({ q: query, page_size: 50, is_active: true }, token),
    enabled: accessToken !== null && query.length >= 2,
  })
  // The backend q-search is fuzzy and alphabetically ordered — an exact
  // ticker can rank below dozens of substring cousins ("RELIANCE" loses
  // to ABREL/ADVANCE/-ANCE matches). Re-rank client-side: exact symbol,
  // then symbol prefix, then company-name prefix, then the rest.
  const results = useMemo(() => {
    if (!search) return []
    const q = query.toUpperCase()
    const rank = (symbol: string, company: string): number => {
      const s = symbol.toUpperCase()
      if (s === q) return 0
      if (s.startsWith(q)) return 1
      if (company.toUpperCase().startsWith(q)) return 2
      return 3
    }
    return [...search.items]
      .sort(
        (a, b) =>
          rank(a.symbol, a.company_name) - rank(b.symbol, b.company_name) ||
          a.symbol.localeCompare(b.symbol),
      )
      .slice(0, 8)
  }, [search, query])

  const selected = lists?.find((w) => w.id === selectedId) ?? lists?.[0] ?? null
  const inSelected = new Set(selected?.items.map((i) => i.stock_id))

  // Live LTP for the visible list only. Memoised so the array identity is
  // stable across renders — useLiveQuotes diffs the symbol SET, and a fresh
  // array each render is what used to churn the socket subscription.
  // Must sit above the early returns: hooks cannot run conditionally.
  const symbols = useMemo(
    () => (selected?.items ?? []).map((i) => i.symbol),
    [selected],
  )
  const { quotes } = useLiveQuotes(symbols)

  if (isLoading) {
    return (
      <div>
        <PageHeader title="Watchlists" subtitle="Named stock sets that scope live alerts" />
        <div className="space-y-2 max-w-md" data-testid="watchlists-skeleton">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-2/3" />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <PageHeader title="Watchlists" subtitle="Named stock sets that scope live alerts" />
        <EmptyState
          title="Couldn't load watchlists"
          description="The request failed. Check the backend and try again."
          action={<Button onClick={() => void refetch()}>Retry</Button>}
        />
      </div>
    )
  }

  const createForm = (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        const name = newName.trim()
        if (name) createMut.mutate(name)
      }}
    >
      <Input
        value={newName}
        onChange={(e) => setNewName(e.target.value)}
        placeholder="New watchlist name"
        aria-label="New watchlist name"
        className="w-56"
      />
      <Button type="submit" disabled={createMut.isPending || !newName.trim()}>
        <Plus /> Create
      </Button>
    </form>
  )

  if (!lists || lists.length === 0) {
    return (
      <div>
        <PageHeader title="Watchlists" subtitle="Named stock sets that scope live alerts" />
        <EmptyState
          icon={<ListChecks size={44} />}
          title="No watchlists yet"
          description="Create one, add stocks, then pick it in the alert bell to scope live alerts to just those stocks."
          action={createForm}
        />
        {createMut.isError && (
          <p role="alert" className="mt-3 text-xs text-(--color-loss) text-center">
            {(createMut.error as Error).message}
          </p>
        )}
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Watchlists"
        subtitle="Named stock sets that scope live alerts"
        actions={createForm}
      />
      {createMut.isError && (
        <p role="alert" className="mb-3 text-xs text-(--color-loss)">
          {(createMut.error as Error).message}
        </p>
      )}

      <div className="flex gap-5 items-start">
        {/* ── watchlist picker ── */}
        <ul className="w-60 flex-shrink-0 rounded-lg border border-(--color-border) divide-y divide-(--color-border) overflow-hidden" role="list">
          {lists.map((w) => {
            const active = selected?.id === w.id
            return (
              <li key={w.id}>
                <button
                  onClick={() => setSelectedId(w.id)}
                  aria-pressed={active}
                  className={cn(
                    'w-full flex items-center justify-between px-3 py-2 text-sm text-left transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)',
                    active
                      ? 'text-(--color-accent)'
                      : 'text-(--color-text) hover:bg-(--color-surface-3)',
                  )}
                  style={
                    active
                      ? { backgroundColor: 'color-mix(in srgb, var(--color-accent) 12%, transparent)' }
                      : {}
                  }
                >
                  <span className="truncate">{w.name}</span>
                  <span className="text-xs text-(--color-text-muted) flex-shrink-0 ml-2">
                    {w.items.length}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>

        {/* ── selected watchlist detail ── */}
        {selected && (
          <div className="flex-1 min-w-0 rounded-lg border border-(--color-border)">
            <div className="flex items-center justify-between px-4 py-3 border-b border-(--color-border)">
              <h2 className="text-sm font-semibold text-(--color-text)">{selected.name}</h2>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Delete watchlist ${selected.name}`}
                disabled={deleteMut.isPending}
                onClick={() => deleteMut.mutate(selected.id)}
              >
                <Trash2 /> Delete
              </Button>
            </div>

            <div className="px-4 py-3 border-b border-(--color-border)">
              <Input
                value={stockQuery}
                onChange={(e) => setStockQuery(e.target.value)}
                placeholder="Search stocks to add (symbol or name)…"
                aria-label="Search stocks to add"
                className="w-full"
              />
              {search && query.length >= 2 && (
                <ul className="mt-2 divide-y divide-(--color-border) rounded-md border border-(--color-border)" role="list">
                  {results.length === 0 && (
                    <li className="px-3 py-2 text-xs text-(--color-text-muted)">No matches</li>
                  )}
                  {results.map((s) => (
                    <li key={s.id}>
                      <button
                        onClick={() => addMut.mutate({ id: selected.id, stockId: s.id })}
                        disabled={inSelected.has(s.id) || addMut.isPending}
                        className={cn(
                          'w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent)',
                          inSelected.has(s.id)
                            ? 'text-(--color-text-muted)'
                            : 'text-(--color-text) hover:bg-(--color-surface-3)',
                        )}
                      >
                        <Plus size={12} aria-hidden="true" />
                        <span className="font-semibold">{s.symbol}</span>
                        <span className="text-(--color-text-muted) truncate">{s.company_name}</span>
                        {inSelected.has(s.id) && (
                          <span className="ml-auto flex-shrink-0 text-(--color-text-muted)">added</span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {selected.items.length === 0 ? (
              <EmptyState
                className="py-10"
                title="No stocks in this watchlist"
                description="Search above to add stocks."
              />
            ) : (
              <Table aria-label={`Stocks in ${selected.name}`}>
                <TableHeader>
                  <TableRow>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead numeric>LTP</TableHead>
                    <TableHead numeric>Change</TableHead>
                    <TableHead numeric>Prev close</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {selected.items.map((item) => (
                    <WatchlistRow
                      key={item.stock_id}
                      item={item}
                      ltp={quotes[item.symbol]?.ltp}
                      listName={selected.name}
                      removing={removeMut.isPending}
                      onRemove={() =>
                        removeMut.mutate({ id: selected.id, stockId: item.stock_id })
                      }
                    />
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

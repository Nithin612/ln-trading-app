import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  journalApi,
  EMOTIONS_BEFORE,
  EMOTIONS_AFTER,
  type JournalEntry,
  type JournalListParams,
} from '@/lib/api/journal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SimpleSelect } from '@/components/ui/simple-select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Pagination } from '@/components/ui/pagination'
import { EmotionAnalyticsPanel } from './EmotionAnalyticsPanel'
import { JournalEntryModal } from './JournalEntryModal'
import { useToast } from '@/hooks/useToast'
import { cn } from '@/lib/utils'
import { Plus, Search, X, Pencil, Trash2, BookOpen } from 'lucide-react'

const PAGE_SIZE = 20

const EMOTION_COLORS: Record<string, string> = {
  confident: 'text-(--color-profit)',
  neutral:   'text-(--color-text-muted)',
  fear:      'text-orange-400',
  greed:     'text-purple-400',
  anxious:   'text-yellow-400',
  satisfied: 'text-(--color-profit)',
  excited:   'text-blue-400',
  frustrated:'text-(--color-loss)',
  regret:    'text-orange-400',
}

function EmotionChip({ emotion }: { emotion: string | null }) {
  if (!emotion) return <span className="text-(--color-text-muted)">—</span>
  return (
    <span className={cn('capitalize text-xs', EMOTION_COLORS[emotion] ?? 'text-(--color-text-muted)')}>
      {emotion}
    </span>
  )
}

function PnlBadge({ pnl }: { pnl: string | null }) {
  if (!pnl) return <span className="text-(--color-text-muted)">—</span>
  const n = Number(pnl)
  const label = `${n >= 0 ? '+' : ''}₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
  return (
    <span
      className={cn(
        'text-xs font-mono font-semibold',
        n >= 0 ? 'text-(--color-bull)' : 'text-(--color-bear)',
      )}
    >
      {label}
    </span>
  )
}

function EntryRow({
  entry,
  onEdit,
  onDelete,
}: {
  entry: JournalEntry
  onEdit: (e: JournalEntry) => void
  onDelete: (id: string) => void
}) {
  return (
    <tr className="border-b border-(--color-border) hover:bg-(--color-surface-3) transition-colors group">
      <td className="px-4 py-3 text-sm text-(--color-text-muted) whitespace-nowrap">
        {entry.trade_date}
      </td>
      <td className="px-4 py-3">
        {entry.symbol ? (
          <span className="text-sm font-medium text-(--color-text)">{entry.symbol}</span>
        ) : (
          <span className="text-xs text-(--color-text-muted)">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        {entry.side ? (
          <span
            className={cn(
              'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border',
              entry.side === 'LONG'
                ? 'text-(--color-bull) border-(--color-bull) bg-transparent'
                : 'text-(--color-bear) border-(--color-bear) bg-transparent',
            )}
          >
            {entry.side}
          </span>
        ) : (
          <span className="text-xs text-(--color-text-muted)">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <PnlBadge pnl={entry.realized_pnl} />
      </td>
      <td className="px-4 py-3">
        <EmotionChip emotion={entry.emotion_before} />
      </td>
      <td className="px-4 py-3">
        <EmotionChip emotion={entry.emotion_after} />
      </td>
      <td className="px-4 py-3 max-w-[240px]">
        <p className="text-xs text-(--color-text-muted) truncate">{entry.notes ?? '—'}</p>
      </td>
      <td className="px-4 py-3">
        <span
          className={cn(
            'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
            entry.entry_type === 'auto'
              ? 'bg-(--color-surface-3) text-(--color-text-muted)'
              : 'bg-(--color-accent) text-white',
          )}
        >
          {entry.entry_type}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onEdit(entry)}
            className="p-1 rounded text-(--color-text-muted) hover:text-(--color-accent) hover:bg-(--color-surface-3)"
            title="Edit"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(entry.id)}
            className="p-1 rounded text-(--color-text-muted) hover:text-(--color-loss) hover:bg-(--color-surface-3)"
            title="Delete"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </td>
    </tr>
  )
}

export function JournalPage() {
  const qc = useQueryClient()
  const { success, error } = useToast()

  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [filterEB, setFilterEB] = useState('')
  const [filterEA, setFilterEA] = useState('')
  const [filterType, setFilterType] = useState('')

  const [modalOpen, setModalOpen] = useState(false)
  const [editEntry, setEditEntry] = useState<JournalEntry | undefined>()

  // Debounce search
  const handleSearchChange = (v: string) => {
    setSearch(v)
    clearTimeout((window as typeof window & { _jSearchTimer?: number })._jSearchTimer)
    ;(window as typeof window & { _jSearchTimer?: number })._jSearchTimer = window.setTimeout(() => {
      setDebouncedQ(v.trim())
      setPage(0)
    }, 350)
  }

  const params: JournalListParams = {
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
    ...(debouncedQ && { q: debouncedQ }),
    ...(filterEB && { emotion_before: filterEB as never }),
    ...(filterEA && { emotion_after: filterEA as never }),
    ...(filterType && { entry_type: filterType as 'auto' | 'manual' }),
  }

  const { data, isLoading } = useQuery({
    queryKey: ['journal', params],
    queryFn: () => journalApi.list(params),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => journalApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['journal'] })
      void qc.invalidateQueries({ queryKey: ['journal-emotions'] })
      success('Entry deleted')
    },
    onError: (e: Error) => error(e.message),
  })

  const handleEdit = (entry: JournalEntry) => {
    setEditEntry(entry)
    setModalOpen(true)
  }

  const handleNew = () => {
    setEditEntry(undefined)
    setModalOpen(true)
  }

  const handleModalClose = () => {
    setModalOpen(false)
    setEditEntry(undefined)
  }

  const hasFilters = debouncedQ || filterEB || filterEA || filterType
  const clearFilters = () => {
    setSearch('')
    setDebouncedQ('')
    setFilterEB('')
    setFilterEA('')
    setFilterType('')
    setPage(1)
  }

  return (
    <div className="flex gap-5 h-full">

      {/* ── Main content ── */}
      <div className="flex-1 min-w-0 flex flex-col gap-4">

        {/* Toolbar */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[180px] max-w-sm">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-(--color-text-muted)" />
            <Input
              placeholder="Search notes & lessons…"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="pl-8"
            />
          </div>

          <SimpleSelect
            value={filterEB}
            onChange={(v) => { setFilterEB(v); setPage(1) }}
            options={[
              { value: '', label: 'Before: all' },
              ...EMOTIONS_BEFORE.map((e) => ({
                value: e,
                label: e.charAt(0).toUpperCase() + e.slice(1),
              })),
            ]}
          />

          <SimpleSelect
            value={filterEA}
            onChange={(v) => { setFilterEA(v); setPage(1) }}
            options={[
              { value: '', label: 'After: all' },
              ...EMOTIONS_AFTER.map((e) => ({
                value: e,
                label: e.charAt(0).toUpperCase() + e.slice(1),
              })),
            ]}
          />

          <SimpleSelect
            value={filterType}
            onChange={(v) => { setFilterType(v); setPage(1) }}
            options={[
              { value: '', label: 'Type: all' },
              { value: 'auto', label: 'Auto' },
              { value: 'manual', label: 'Manual' },
            ]}
          />

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-xs text-(--color-text-muted) hover:text-(--color-text)"
            >
              <X size={12} /> Clear
            </button>
          )}

          <div className="ml-auto">
            <Button onClick={handleNew} size="sm">
              <Plus size={14} className="mr-1" /> New Entry
            </Button>
          </div>
        </div>

        {/* Table */}
        <div
          className="rounded-lg border border-(--color-border) overflow-hidden"
          style={{ background: 'var(--color-surface-2)' }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-(--color-border)">
                  {['Date', 'Symbol', 'Side', 'P&L', 'Before', 'After', 'Notes', 'Type', ''].map(
                    (h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left text-xs font-medium text-(--color-text-muted) whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-(--color-border)">
                      {Array.from({ length: 9 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : !data || data.entries.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-12">
                      <EmptyState
                        icon={<BookOpen size={28} />}
                        title="No journal entries yet"
                        description={
                          hasFilters
                            ? 'No entries match your filters.'
                            : 'Auto-entries are created when you close a position. You can also add manual entries.'
                        }
                      />
                    </td>
                  </tr>
                ) : (
                  data.entries.map((entry) => (
                    <EntryRow
                      key={entry.id}
                      entry={entry}
                      onEdit={handleEdit}
                      onDelete={(id) => deleteMut.mutate(id)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {data && data.total > PAGE_SIZE && (
          <Pagination
            total={data.total}
            page={page}
            pages={Math.ceil(data.total / PAGE_SIZE)}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        )}
      </div>

      {/* ── Sidebar: analytics ── */}
      <div className="w-64 flex-shrink-0">
        <EmotionAnalyticsPanel />
      </div>

      {/* ── Modal ── */}
      {modalOpen && (
        <JournalEntryModal
          entry={editEntry}
          open={modalOpen}
          onClose={handleModalClose}
        />
      )}
    </div>
  )
}

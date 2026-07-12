import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2, Edit2, Check, X, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { categoriesApi } from '@/lib/api/categories'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Drawer } from '@/components/ui/drawer'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Pagination } from '@/components/ui/pagination'
import { PageHeader } from '@/components/layout/PageHeader'
import { useToast } from '@/hooks/useToast'
import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import type { ApiError } from '@/lib/api/client'
import type { CategoryWithCount } from '@/lib/api/categories'

interface InlineEditProps {
  cat: CategoryWithCount
  onDone: () => void
}

function InlineEdit({ cat, onDone }: InlineEditProps) {
  const { accessToken } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState(cat.name)
  const [description, setDescription] = useState(cat.description ?? '')

  const mut = useMutation({
    mutationFn: () => categoriesApi.update(cat.id, { name: name.trim(), description: description.trim() || null }, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['categories'] })
      toast.success('Category updated')
      onDone()
    },
    onError: (err: ApiError) => toast.error(err.message),
  })

  return (
    <div className="flex items-center gap-2 flex-1">
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="h-7 text-sm bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus-visible:ring-(--color-accent) w-32"
        autoFocus
        onKeyDown={(e) => { if (e.key === 'Enter') mut.mutate(); if (e.key === 'Escape') onDone() }}
      />
      <Input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description"
        className="h-7 text-sm bg-(--color-surface-3) border-(--color-border) text-(--color-text) focus-visible:ring-(--color-accent) w-48"
        onKeyDown={(e) => { if (e.key === 'Enter') mut.mutate(); if (e.key === 'Escape') onDone() }}
      />
      <Button onClick={() => mut.mutate()} disabled={mut.isPending} variant="ghost" size="icon-xs" className="text-(--color-profit)"><Check size={14} /></Button>
      <Button onClick={onDone} variant="ghost" size="icon-xs" className="text-(--color-text-muted) hover:text-(--color-text)"><X size={14} /></Button>
    </div>
  )
}

interface CategoryDrawerProps {
  cat: CategoryWithCount
  open: boolean
  onClose: () => void
}

function CategoryDrawer({ cat, open, onClose }: CategoryDrawerProps) {
  const { accessToken } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['category-stocks', cat.id, page],
    queryFn: () => categoriesApi.getStocks(cat.id, page, accessToken!),
    enabled: open && !!accessToken,
  })

  const symbols = data?.items.map((s) => s.symbol) ?? []
  const { quotes: liveQuotes } = useLiveQuotes(symbols)

  const filtered = (data?.items ?? []).filter((s) =>
    !search || s.symbol.toLowerCase().includes(search.toLowerCase()) || s.company_name.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <Drawer open={open} onClose={onClose} title={cat.name} width={440}>
      <div className="p-4 space-y-3">
        {cat.description && (
          <p className="text-xs text-(--color-text-muted)">{cat.description}</p>
        )}

        {/* Search within drawer */}
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-(--color-text-muted)" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search stocks in this category…"
            className="w-full pl-8 pr-3 py-2 text-sm bg-(--color-surface-3) border border-(--color-border) rounded-md text-(--color-text) placeholder:text-(--color-text-muted) focus:outline-none focus:border-(--color-accent)"
          />
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState title="No stocks" description={search ? 'No matches in this category' : 'This category has no stocks yet'} />
        ) : (
          <div className="space-y-1">
            {filtered.map((stock) => {
              const ltp = liveQuotes[stock.symbol]
              return (
                <div
                  key={stock.id}
                  className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-(--color-surface-3) transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <Link
                      to={`/stocks/${stock.id}`}
                      onClick={onClose}
                      className="font-mono font-semibold text-sm text-(--color-accent) hover:text-(--color-accent-hover)"
                    >
                      {stock.symbol}
                    </Link>
                    <p className="text-xs text-(--color-text-muted) truncate">{stock.company_name}</p>
                  </div>
                  {ltp ? (
                    <span className="font-mono text-sm font-semibold" style={{ color: 'var(--color-bull)' }}>
                      ₹{ltp.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  ) : (
                    <span className="text-xs text-(--color-text-muted)">—</span>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {data && data.pages > 1 && (
          <Pagination
            page={page}
            pages={data.pages}
            pageSize={50}
            total={data.total}
            onPageChange={setPage}
          />
        )}
      </div>
    </Drawer>
  )
}

export function CategoriesPage() {
  const { accessToken, isAdmin } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [drawerCat, setDrawerCat] = useState<CategoryWithCount | null>(null)

  const { data: categories = [], isLoading } = useQuery({
    queryKey: ['categories'],
    queryFn: () => categoriesApi.list(accessToken!),
    enabled: !!accessToken,
  })

  const createMut = useMutation({
    mutationFn: () => categoriesApi.create(name.trim(), description.trim() || null, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['categories'] })
      setName('')
      setDescription('')
      setFormError(null)
      toast.success('Category created')
    },
    onError: (err: ApiError) => setFormError(err.message),
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => categoriesApi.delete(id, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['categories'] })
      toast.success('Category deleted')
    },
    onError: (err: ApiError) => toast.error(err.message),
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    createMut.mutate()
  }

  return (
    <div className="max-w-3xl">
      <PageHeader title="Categories" subtitle="Tag stocks by theme or sector" />

      {isAdmin && (
        <form onSubmit={handleCreate} className="card mb-6 space-y-3">
          <h2 className="text-sm font-semibold text-(--color-text)">New Category</h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="cat-name">Name</Label>
              <Input id="cat-name" placeholder="e.g. Defence" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cat-desc">Description (optional)</Label>
              <Input id="cat-desc" placeholder="Short description" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </div>
          {formError && <p className="text-xs text-(--color-error)">{formError}</p>}
          <Button type="submit" disabled={!name.trim() || createMut.isPending} className="btn btn-primary text-sm">
            {createMut.isPending ? 'Creating…' : 'Create'}
          </Button>
        </form>
      )}

      {isLoading ? (
        <div className="card space-y-3 p-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        </div>
      ) : categories.length === 0 ? (
        <EmptyState
          title="No categories yet"
          description={isAdmin ? 'Create your first category above.' : 'No categories have been created.'}
        />
      ) : (
        <div className="card divide-y divide-(--color-border)">
          {categories.map((cat) => (
            <div key={cat.id} className="flex items-center justify-between py-3 gap-3">
              {editingId === cat.id ? (
                <InlineEdit cat={cat} onDone={() => setEditingId(null)} />
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1 justify-start text-left h-auto py-0 px-0 hover:bg-transparent group"
                  onClick={() => setDrawerCat(cat)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-(--color-text) group-hover:text-(--color-accent) transition-colors">
                      {cat.name}
                    </span>
                    <Badge className="bg-(--color-surface-3) text-(--color-text-muted) border-(--color-border) border text-xs">
                      {cat.stock_count} stock{cat.stock_count !== 1 ? 's' : ''}
                    </Badge>
                  </div>
                  {cat.description && (
                    <p className="text-xs text-(--color-text-muted) mt-0.5">{cat.description}</p>
                  )}
                  <p className="text-xs text-(--color-text-muted) font-mono mt-0.5 opacity-60">slug: {cat.slug}</p>
                </Button>
              )}

              {isAdmin && editingId !== cat.id && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button
                    onClick={() => setEditingId(cat.id)}
                    variant="ghost"
                    size="icon-xs"
                    className="text-(--color-text-muted) hover:text-(--color-accent)"
                    title="Edit"
                  >
                    <Edit2 size={13} />
                  </Button>
                  <Button
                    onClick={() => deleteMut.mutate(cat.id)}
                    disabled={deleteMut.isPending}
                    variant="ghost"
                    size="icon-xs"
                    className="text-(--color-text-muted) hover:text-(--color-error)"
                    title="Delete category"
                  >
                    <Trash2 size={13} />
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {drawerCat && (
        <CategoryDrawer
          cat={drawerCat}
          open={!!drawerCat}
          onClose={() => setDrawerCat(null)}
        />
      )}
    </div>
  )
}

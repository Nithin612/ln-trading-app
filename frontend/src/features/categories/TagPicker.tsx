import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Plus } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { categoriesApi } from '@/lib/api/categories'
import { SimpleSelect } from '@/components/ui/simple-select'

interface Props {
  stockId: number
}

export function TagPicker({ stockId }: Props) {
  const { accessToken, isAdmin } = useAuth()
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)

  const { data: stockCats = [] } = useQuery({
    queryKey: ['stock-categories', stockId],
    queryFn: () => categoriesApi.getStockCategories(stockId, accessToken!),
    enabled: !!accessToken,
  })

  const { data: allCats = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => categoriesApi.list(accessToken!),
    enabled: !!accessToken && adding,
  })

  const tagMut = useMutation({
    mutationFn: (categoryId: number) =>
      categoriesApi.tagStock(stockId, categoryId, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['stock-categories', stockId] })
      void qc.invalidateQueries({ queryKey: ['categories'] })
      setAdding(false)
    },
  })

  const untagMut = useMutation({
    mutationFn: (categoryId: number) =>
      categoriesApi.untagStock(stockId, categoryId, accessToken!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['stock-categories', stockId] })
      void qc.invalidateQueries({ queryKey: ['categories'] })
    },
  })

  const taggedIds = new Set(stockCats.map((c) => c.id))
  const available = allCats.filter((c) => !taggedIds.has(c.id))

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 items-center">
        {stockCats.map((cat) => (
          <span
            key={cat.id}
            className="inline-flex items-center gap-1 rounded-full border border-(--color-border) bg-(--color-surface-3) text-(--color-text-muted) text-xs px-2 py-0.5"
          >
            {cat.name}
            {isAdmin && (
              <button
                type="button"
                onClick={() => untagMut.mutate(cat.id)}
                className="hover:text-(--color-error) transition-colors"
                title="Remove tag"
              >
                <X size={10} />
              </button>
            )}
          </span>
        ))}

        {isAdmin && !adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-0.5 rounded-full border border-dashed border-(--color-border) text-(--color-text-muted) hover:text-(--color-text) text-xs px-2 py-0.5 transition-colors"
          >
            <Plus size={10} /> Add tag
          </button>
        )}

        {isAdmin && adding && (
          <div className="flex items-center gap-1">
            {available.length === 0 ? (
              <span className="text-xs text-(--color-text-muted)">
                All categories tagged
              </span>
            ) : (
              <SimpleSelect
                value=""
                placeholder="Pick category…"
                size="sm"
                className="min-w-[140px] text-xs h-7"
                options={available.map((c) => ({ value: String(c.id), label: c.name }))}
                onChange={(v) => { if (v) tagMut.mutate(Number(v)) }}
              />
            )}
            <button
              type="button"
              onClick={() => setAdding(false)}
              className="text-xs text-(--color-text-muted) hover:text-(--color-text)"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {stockCats.length === 0 && !isAdmin && (
        <span className="text-xs text-(--color-text-muted)">No categories</span>
      )}
      {stockCats.length === 0 && isAdmin && !adding && (
        <span className="text-xs text-(--color-text-muted)">None — add above</span>
      )}
    </div>
  )
}

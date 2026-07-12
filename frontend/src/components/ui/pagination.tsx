import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { SimpleSelect } from '@/components/ui/simple-select'

interface PaginationProps {
  page: number
  pages: number
  pageSize: number
  total: number
  onPageChange: (p: number) => void
  onPageSizeChange?: (size: number) => void
  pageSizeOptions?: number[]
  className?: string
}

const DEFAULT_PAGE_SIZES = [10, 25, 50, 100]

export function Pagination({
  page,
  pages,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = DEFAULT_PAGE_SIZES,
  className,
}: PaginationProps) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  const pageButtons = buildPageButtons(page, pages)

  return (
    <div className={cn('flex items-center justify-between gap-4 text-sm text-(--color-text-muted) flex-wrap', className)}>
      <div className="flex items-center gap-3">
        {onPageSizeChange && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs">Rows:</span>
            <SimpleSelect
              size="sm"
              value={String(pageSize)}
              onChange={(v) => { onPageSizeChange(Number(v)); onPageChange(1) }}
              options={pageSizeOptions.map((s) => ({ value: String(s), label: String(s) }))}
              className="min-w-[64px]"
            />
          </div>
        )}
        <span className="text-xs">
          {total === 0 ? 'No results' : `Showing ${start}–${end} of ${total.toLocaleString()}`}
        </span>
      </div>

      {pages > 1 && (
        <div className="flex items-center gap-1">
          <PageBtn onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Previous page">
            <ChevronLeft size={14} />
          </PageBtn>

          {pageButtons.map((btn, i) =>
            btn === '...' ? (
              <span key={`ellipsis-${i}`} className="px-1 text-xs text-(--color-text-muted)">…</span>
            ) : (
              <PageBtn
                key={btn}
                active={btn === page}
                onClick={() => onPageChange(btn as number)}
              >
                {btn}
              </PageBtn>
            ),
          )}

          <PageBtn onClick={() => onPageChange(page + 1)} disabled={page >= pages} aria-label="Next page">
            <ChevronRight size={14} />
          </PageBtn>
        </div>
      )}
    </div>
  )
}

function PageBtn({
  children,
  onClick,
  disabled,
  active,
  'aria-label': ariaLabel,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  active?: boolean
  'aria-label'?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={cn(
        'min-w-[28px] h-7 px-1.5 rounded text-xs font-medium transition-colors',
        'border border-(--color-border)',
        active
          ? 'bg-(--color-accent) text-white border-(--color-accent)'
          : 'bg-transparent text-(--color-text-muted) hover:bg-(--color-surface-3) hover:text-(--color-text)',
        (disabled) && 'opacity-40 cursor-not-allowed pointer-events-none',
      )}
    >
      {children}
    </button>
  )
}

function buildPageButtons(page: number, pages: number): (number | '...')[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1)
  const buttons: (number | '...')[] = [1]
  if (page > 3) buttons.push('...')
  for (let i = Math.max(2, page - 1); i <= Math.min(pages - 1, page + 1); i++) buttons.push(i)
  if (page < pages - 2) buttons.push('...')
  buttons.push(pages)
  return buttons
}

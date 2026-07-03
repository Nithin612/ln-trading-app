import { useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  width?: number | string
  className?: string
}

export function Drawer({ open, onClose, title, children, width = 480, className }: DrawerProps) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/50 z-40 animate-in fade-in duration-200"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Drawer panel */}
      <div
        className={cn(
          'fixed top-0 right-0 h-full z-50 flex flex-col',
          'bg-[--color-surface-2] border-l border-[--color-border] shadow-2xl',
          'animate-in slide-in-from-right duration-300',
          className,
        )}
        style={{ width }}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[--color-border] flex-shrink-0">
          {title && (
            <h2 className="text-sm font-semibold text-[--color-text] uppercase tracking-wide">
              {title}
            </h2>
          )}
          <button
            onClick={onClose}
            className="ml-auto text-[--color-text-muted] hover:text-[--color-text] transition-colors p-1 rounded hover:bg-[--color-surface-3]"
            aria-label="Close drawer"
          >
            <X size={16} />
          </button>
        </div>
        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </>
  )
}

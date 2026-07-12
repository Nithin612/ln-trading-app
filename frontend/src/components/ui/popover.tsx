import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

interface PopoverProps {
  trigger: React.ReactElement<React.ButtonHTMLAttributes<HTMLButtonElement>>
  children: React.ReactNode
  align?: 'start' | 'end' | 'center'
  className?: string
}

interface Coords {
  top: number
  left?: number
  right?: number
}

export function Popover({ trigger, children, align = 'end', className }: PopoverProps) {
  const [open, setOpen] = useState(false)
  const [coords, setCoords] = useState<Coords>({ top: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!open || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const top = rect.bottom + 4
    if (align === 'end') {
      setCoords({ top, right: window.innerWidth - rect.right })
    } else if (align === 'start') {
      setCoords({ top, left: rect.left })
    } else {
      setCoords({ top, left: rect.left + rect.width / 2 })
    }
  }, [open, align])

  useEffect(() => {
    if (!open) return
    function handler(e: MouseEvent) {
      if (
        panelRef.current?.contains(e.target as Node) ||
        containerRef.current?.contains(e.target as Node)
      ) return
      setOpen(false)
    }
    function keyHandler(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', keyHandler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('keydown', keyHandler)
    }
  }, [open])

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    top: coords.top,
    ...(coords.left !== undefined && { left: coords.left }),
    ...(coords.right !== undefined && { right: coords.right }),
    ...(align === 'center' && { transform: 'translateX(-50%)' }),
  }

  const el = trigger as React.ReactElement<React.ButtonHTMLAttributes<HTMLButtonElement>>

  return (
    <div ref={containerRef} className="relative inline-block">
      <el.type
        {...el.props}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
          setOpen((v) => !v)
          el.props.onClick?.(e)
        }}
      />
      {open && createPortal(
        <div
          ref={panelRef}
          // Solid surface + strong border INLINE (UI_GUIDELINES §17.2):
          // inline var() cannot be dropped by a Tailwind syntax change —
          // the 2026-07-11 v4 [--var]→(--var) incident left this panel
          // transparent; the panel bg stays purge-proof on purpose.
          style={{
            ...panelStyle,
            backgroundColor: 'var(--color-surface)',
            borderColor: 'var(--color-border-strong)',
          }}
          className={cn(
            'z-50 min-w-[160px]',
            'border rounded-lg shadow-xl',
            'animate-in fade-in zoom-in-95 duration-150',
            className,
          )}
          role="dialog"
        >
          {children}
        </div>,
        document.body,
      )}
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { registerGlobalToast } from '@/lib/toast'
import { ToastContext } from '@/lib/toast-context'
import type { ToastContextValue } from '@/lib/toast-context'

type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: string
  message: string
  type: ToastType
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const remove = useCallback((id: string) => {
    setToasts((t) => t.filter((x) => x.id !== id))
    const timer = timers.current.get(id)
    if (timer) { clearTimeout(timer); timers.current.delete(id) }
  }, [])

  const add = useCallback((message: string, type: ToastType) => {
    const id = `${Date.now()}-${Math.random()}`
    setToasts((t) => [...t.slice(-4), { id, message, type }])
    timers.current.set(id, setTimeout(() => remove(id), 4000))
  }, [remove])

  const ctx: ToastContextValue = {
    success: (m) => add(m, 'success'),
    error: (m) => add(m, 'error'),
    info: (m) => add(m, 'info'),
    warning: (m) => add(m, 'warning'),
  }

  useEffect(() => {
    registerGlobalToast(ctx)
    return () => { registerGlobalToast(null) }
  })

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div
        style={{
          position: 'fixed',
          bottom: '1.5rem',
          right: '1.5rem',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          maxWidth: '360px',
          width: '100%',
        }}
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onClose={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

const TYPE_STYLES: Record<ToastType, { border: string; icon: string; iconColor: string }> = {
  success: { border: 'var(--color-bull)', icon: '✓', iconColor: 'var(--color-bull)' },
  error: { border: 'var(--color-error)', icon: '✕', iconColor: 'var(--color-error)' },
  warning: { border: 'var(--color-neutral)', icon: '!', iconColor: 'var(--color-neutral)' },
  info: { border: 'var(--color-accent)', icon: 'i', iconColor: 'var(--color-accent)' },
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const s = TYPE_STYLES[toast.type]
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg p-3.5 text-sm shadow-lg',
        'bg-[--color-surface-2] border border-[--color-border]',
        'animate-in slide-in-from-right-5 fade-in duration-200',
      )}
      style={{ borderLeft: `3px solid ${s.border}` }}
    >
      <span
        className="flex-shrink-0 font-bold text-xs w-4 h-4 flex items-center justify-center rounded-full border mt-0.5"
        style={{ color: s.iconColor, borderColor: s.iconColor }}
      >
        {s.icon}
      </span>
      <span className="flex-1 text-[--color-text]">{toast.message}</span>
      <button
        onClick={onClose}
        className="flex-shrink-0 text-[--color-text-muted] hover:text-[--color-text] transition-colors mt-0.5"
        aria-label="Dismiss"
      >
        <X size={13} />
      </button>
    </div>
  )
}



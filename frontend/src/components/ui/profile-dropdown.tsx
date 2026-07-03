import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { User, Settings, LogOut, ChevronDown, Shield } from 'lucide-react'
import { UserAvatar } from './user-avatar'
import type { UserOut } from '@/lib/api/auth'

interface ProfileDropdownProps {
  user: UserOut
  isAdmin: boolean
  onLogout: () => void
}

export function ProfileDropdown({ user, isAdmin, onLogout }: ProfileDropdownProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState<{ top: number; right: number }>({ top: 0, right: 0 })

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    setCoords({
      top: rect.bottom + 6,
      right: window.innerWidth - rect.right,
    })
  }, [open])

  useEffect(() => {
    if (!open) return
    function onMouse(e: MouseEvent) {
      if (
        panelRef.current?.contains(e.target as Node) ||
        triggerRef.current?.contains(e.target as Node)
      ) return
      setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onMouse)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onMouse)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <>
      <button
        ref={triggerRef}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-[--color-surface-3] transition-colors"
        aria-label="User menu"
        aria-expanded={open}
        data-testid="profile-trigger"
      >
        <UserAvatar name={user.full_name} size="sm" />
        <span className="hidden md:block text-xs font-medium text-[--color-text] max-w-[120px] truncate">
          {user.full_name.split(' ')[0]}
        </span>
        <ChevronDown
          size={13}
          className="text-[--color-text-muted] transition-transform hidden md:block"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        />
      </button>

      {open && createPortal(
        <div
          ref={panelRef}
          style={{
            position: 'fixed',
            top: coords.top,
            right: coords.right,
            zIndex: 50,
            width: '17rem',
          }}
          className="rounded-xl border border-[--color-border-strong] bg-[--color-surface] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        >
          {/* Identity header */}
          <div className="px-4 py-3 border-b border-[--color-border] bg-[--color-surface-2]">
            <div className="flex items-center gap-3">
              <UserAvatar name={user.full_name} size="lg" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-[--color-text] truncate">{user.full_name}</p>
                <p className="text-xs text-[--color-text-muted] truncate">{user.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2.5">
              {isAdmin && (
                <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-900/40 text-purple-300 border border-purple-700">
                  <Shield size={9} />
                  Admin
                </span>
              )}
              <span
                className="text-[10px] font-semibold px-2 py-0.5 rounded-full border"
                style={{
                  backgroundColor: user.trading_mode === 'live'
                    ? 'rgba(34,197,94,0.15)'
                    : 'rgba(59,130,246,0.15)',
                  color: user.trading_mode === 'live'
                    ? 'var(--color-bull)'
                    : 'var(--color-accent)',
                  borderColor: user.trading_mode === 'live'
                    ? 'rgba(34,197,94,0.3)'
                    : 'rgba(59,130,246,0.3)',
                }}
              >
                {user.trading_mode === 'live' ? 'Live Trading' : 'Paper Trading'}
              </span>
            </div>
          </div>

          {/* Nav items */}
          <div className="py-1">
            <MenuItem to="/profile" icon={<User size={14} />} label="My Profile" onClick={() => setOpen(false)} />
            {isAdmin && (
              <MenuItem to="/admin/settings" icon={<Settings size={14} />} label="Appearance Settings" onClick={() => setOpen(false)} />
            )}
          </div>

          <div className="border-t border-[--color-border] py-1">
            <button
              onClick={() => { setOpen(false); onLogout() }}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-[--color-loss] hover:bg-[--color-surface-2] transition-colors"
            >
              <LogOut size={14} />
              Sign out
            </button>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}

function MenuItem({ to, icon, label, onClick }: {
  to: string
  icon: React.ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-2 text-sm text-[--color-text-muted] hover:text-[--color-text] hover:bg-[--color-surface-2] transition-colors"
    >
      {icon}
      {label}
    </Link>
  )
}

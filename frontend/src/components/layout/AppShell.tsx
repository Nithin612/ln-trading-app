import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  TrendingUp,
  SlidersHorizontal,
  Tags,
  Building2,
  Zap,
  Users,
  FileText,
  ChevronLeft,
  ChevronRight,
  Circle,
  Moon,
  Sun,
  Settings,
  Briefcase,
  History,
  FlaskConical,
  BookOpen,
  Wallet,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useKiteStatus } from '@/hooks/useKiteStatus'
import { useThemeStore } from '@/store/themeStore'
import { useUiPrefsStore } from '@/store/uiPrefsStore'
import { ProfileDropdown } from '@/components/ui/profile-dropdown'
import { cn } from '@/lib/utils'

const SIDEBAR_KEY = 'sidebar-collapsed'

interface NavItem {
  to: string
  icon: React.ReactNode
  label: string
  adminOnly?: boolean
  warnIcon?: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard',         icon: <LayoutDashboard size={18} />, label: 'Dashboard' },
  { to: '/stocks',            icon: <TrendingUp size={18} />,      label: 'Stocks' },
  { to: '/screener',          icon: <SlidersHorizontal size={18} />,label: 'Screener' },
  { to: '/categories',        icon: <Tags size={18} />,            label: 'Categories' },
  { to: '/market/fii-dii',    icon: <Building2 size={18} />,       label: 'FII / DII' },
  { to: '/filings',           icon: <FileText size={18} />,        label: 'Filings' },
  { to: '/trading/positions', icon: <Briefcase size={18} />,       label: 'Positions' },
  { to: '/trading/history',   icon: <History size={18} />,         label: 'Trade History' },
  { to: '/strategy',          icon: <FlaskConical size={18} />,    label: 'Strategy Lab' },
  { to: '/journal',           icon: <BookOpen size={18} />,        label: 'Journal' },
  { to: '/portfolio',         icon: <Wallet size={18} />,          label: 'Portfolio' },
]

const ADMIN_NAV_ITEMS: NavItem[] = [
  { to: '/broker/kite',   icon: <Zap size={18} />,     label: 'Kite',     adminOnly: true },
  { to: '/admin/users',   icon: <Users size={18} />,   label: 'Users',    adminOnly: true },
  { to: '/admin/settings',icon: <Settings size={18} />,label: 'Settings', adminOnly: true },
]

function useMarketStatus() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
  const h = ist.getHours()
  const m = ist.getMinutes()
  const day = ist.getDay()
  const isWeekend = day === 0 || day === 6
  const mins = h * 60 + m

  let status: 'OPEN' | 'CLOSED' | 'PRE-MARKET'
  if (isWeekend) {
    status = 'CLOSED'
  } else if (mins >= 555 && mins < 570) {
    status = 'PRE-MARKET'
  } else if (mins >= 570 && mins < 930) {
    status = 'OPEN'
  } else {
    status = 'CLOSED'
  }

  let nextEvent = ''
  if (!isWeekend) {
    if (mins < 570) {
      const rem = 570 - mins
      nextEvent = `opens in ${Math.floor(rem / 60)}h ${rem % 60}m`
    } else if (mins < 930) {
      const rem = 930 - mins
      nextEvent = `closes in ${Math.floor(rem / 60)}h ${rem % 60}m`
    }
  }

  const timeIST = ist.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })

  return { status, timeIST, nextEvent }
}

/* Applies theme + font prefs as data-attributes / CSS vars on <html> */
function ThemeApplicator() {
  const { theme } = useThemeStore()
  const { fontSize, fontFamily, fontSizePx, uiFont, numFont } = useUiPrefsStore()

  useEffect(() => {
    const el = document.documentElement
    el.setAttribute('data-theme', theme)
    // Legacy discrete font size (still needed as fallback)
    el.setAttribute('data-font-size', fontSize)
    el.setAttribute('data-font-family', fontFamily)
    // Continuous font size — only write if the px store differs from discrete default
    el.style.setProperty('--ui-font-size', `${fontSizePx}px`)
    // Split fonts
    el.setAttribute('data-ui-font', uiFont)
    el.setAttribute('data-num-font', numFont)
  }, [theme, fontSize, fontFamily, fontSizePx, uiFont, numFont])

  return null
}

export function AppShell() {
  const { user, logout, isAdmin } = useAuth()
  const kite = useKiteStatus()
  const location = useLocation()
  const { theme, toggle: toggleTheme } = useThemeStore()

  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(SIDEBAR_KEY) === 'true' } catch { return false }
  })

  const toggle = () => {
    setCollapsed((v) => {
      const next = !v
      try { localStorage.setItem(SIDEBAR_KEY, String(next)) } catch { /* */ }
      return next
    })
  }

  const { status: marketStatus, timeIST, nextEvent } = useMarketStatus()

  const banner: 'not-connected' | 'expiring' | null = isAdmin
    ? !kite.connected
      ? 'not-connected'
      : kite.expiringSoon
        ? 'expiring'
        : null
    : null

  const pageTitle = getPageTitle(location.pathname)

  return (
    <>
      <ThemeApplicator />
      <div className="flex h-screen overflow-hidden bg-[--color-surface]">

        {/* ── Sidebar ── */}
        <aside
          className={cn(
            'relative z-20 flex flex-col flex-shrink-0 bg-[--color-sidebar] border-r border-[--color-border]',
            'transition-all duration-300 ease-in-out overflow-hidden',
          )}
          style={{ width: collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)' }}
        >
          {/* Logo */}
          <div
            className={cn(
              'flex items-center flex-shrink-0 border-b border-[--color-border] px-4',
              collapsed ? 'justify-center' : 'gap-3',
            )}
            style={{ height: 'var(--topbar-height)' }}
          >
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, var(--color-accent) 0%, #1e3a8a 100%)' }}
            >
              <TrendingUp size={15} className="text-white" />
            </div>
            {!collapsed && (
              <span className="font-bold text-sm font-mono tracking-widest whitespace-nowrap overflow-hidden"
                style={{ color: 'var(--color-text)', letterSpacing: '0.12em' }}>
                TRADING
              </span>
            )}
          </div>

          {/* Nav links */}
          <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto overflow-x-hidden">
            {NAV_ITEMS.map((item) => (
              <SidebarLink
                key={item.to}
                item={item}
                collapsed={collapsed}
                active={location.pathname === item.to || (item.to !== '/dashboard' && location.pathname.startsWith(item.to))}
              />
            ))}

            {isAdmin && (
              <>
                <div className="my-2 mx-2 border-t border-[--color-border]" />
                {ADMIN_NAV_ITEMS.map((item) => {
                  const hasBanner = item.to === '/broker/kite' && banner
                  return (
                    <SidebarLink
                      key={item.to}
                      item={{
                        ...item,
                        warnIcon: hasBanner
                          ? banner === 'not-connected' ? '⚠' : '!'
                          : undefined,
                      }}
                      collapsed={collapsed}
                      active={location.pathname.startsWith(item.to)}
                      warn={!!hasBanner}
                    />
                  )
                })}
              </>
            )}
          </nav>

          {/* Collapse toggle */}
          <div className="flex-shrink-0 border-t border-[--color-border] p-2">
            <button
              onClick={toggle}
              className={cn(
                'w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-xs text-[--color-text-muted]',
                'hover:bg-[--color-surface-3] hover:text-[--color-text] transition-colors',
                collapsed && 'justify-center',
              )}
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed
                ? <ChevronRight size={16} />
                : <><ChevronLeft size={16} /><span>Collapse</span></>
              }
            </button>
          </div>
        </aside>

        {/* ── Main column ── */}
        <div className="flex flex-col flex-1 overflow-hidden">

          {/* ── Top bar ── */}
          <header
            className="relative z-30 flex-shrink-0 flex items-center justify-between px-5 bg-[--color-topbar]"
            style={{ height: 'var(--topbar-height)', borderBottom: '1px solid var(--color-border)', boxShadow: '0 2px 8px rgba(0,0,0,0.18)' }}
          >
            <h1 className="text-sm font-semibold text-[--color-text]">{pageTitle}</h1>

            <div className="flex items-center gap-2">
              {/* Market status chip + clock */}
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'text-xs font-semibold px-2 py-0.5 rounded-full border',
                    marketStatus === 'OPEN'
                      ? 'bg-[--color-profit-bg] text-[--color-profit] border-[--color-profit]/20'
                      : marketStatus === 'PRE-MARKET'
                        ? 'bg-[--color-warning-bg] text-[--color-warning] border-[--color-warning]/20'
                        : 'bg-[--color-surface-3] text-[--color-text-muted] border-[--color-border]',
                  )}
                >
                  {marketStatus}
                </span>
                <span className="text-xs font-mono text-[--color-text-muted]">{timeIST} IST</span>
                {nextEvent && (
                  <span className="text-xs text-[--color-text-muted] hidden xl:block">• {nextEvent}</span>
                )}
              </div>

              <div className="w-px h-4 bg-[--color-border]" />

              {/* Theme toggle */}
              <button
                onClick={toggleTheme}
                className="p-1.5 rounded-md text-[--color-text-muted] hover:text-[--color-text] hover:bg-[--color-surface-3] transition-colors"
                title={theme === 'daybreak' ? 'Switch to dark mode' : 'Switch to light mode'}
                aria-label="Toggle theme"
                data-testid="theme-toggle"
              >
                {theme === 'daybreak' ? <Moon size={15} /> : <Sun size={15} />}
              </button>

              <div className="w-px h-4 bg-[--color-border]" />

              {/* Profile dropdown */}
              {user && (
                <ProfileDropdown user={user} isAdmin={isAdmin} onLogout={() => void logout()} />
              )}
            </div>
          </header>

          {/* ── Kite warning banner ── */}
          {banner && (
            <div
              className="flex-shrink-0 flex items-center justify-between px-5 py-1.5 text-xs border-b"
              style={{
                backgroundColor: banner === 'not-connected' ? 'rgba(239,68,68,0.08)' : 'rgba(245,158,11,0.08)',
                borderColor: banner === 'not-connected' ? 'rgba(239,68,68,0.25)' : 'rgba(245,158,11,0.25)',
              }}
            >
              <div className="flex items-center gap-2">
                <Circle
                  size={6}
                  className={banner === 'not-connected' ? 'text-[--color-bear] fill-[--color-bear]' : 'text-yellow-500 fill-yellow-500'}
                />
                <span style={{ color: banner === 'not-connected' ? 'var(--color-bear)' : '#f59e0b' }}>
                  {banner === 'not-connected'
                    ? 'Zerodha Kite is not connected — live data and signals are paused.'
                    : `Kite token expires in ${kite.minutesLeft} minute${kite.minutesLeft === 1 ? '' : 's'} — re-authenticate before market opens.`}
                </span>
              </div>
              <Link
                to="/broker/kite"
                className="font-semibold text-xs hover:underline ml-4 flex-shrink-0"
                style={{ color: banner === 'not-connected' ? 'var(--color-bear)' : '#f59e0b' }}
              >
                {banner === 'not-connected' ? 'Connect →' : 'Re-authenticate →'}
              </Link>
            </div>
          )}

          {/* ── Page content ── */}
          <main className="flex-1 overflow-y-auto p-5">
            <Outlet />
          </main>
        </div>
      </div>
    </>
  )
}

interface SidebarLinkProps {
  item: NavItem
  collapsed: boolean
  active: boolean
  warn?: boolean
}

function SidebarLink({ item, collapsed, active, warn }: SidebarLinkProps) {
  return (
    <Link
      to={item.to}
      title={collapsed ? item.label : undefined}
      className={cn(
        'flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors relative overflow-hidden',
        active
          ? 'text-[--color-accent]'
          : warn
            ? 'text-[--color-bear] hover:bg-[--color-surface-3]'
            : 'text-[--color-text-muted] hover:bg-[--color-surface-3] hover:text-[--color-text]',
        collapsed && 'justify-center',
      )}
      style={active ? { backgroundColor: 'color-mix(in srgb, var(--color-accent) 12%, transparent)' } : {}}
    >
      {active && (
        <span className="absolute left-0 top-0 bottom-0 w-[3px] bg-[--color-accent] rounded-r-sm" />
      )}
      <span className="flex-shrink-0 relative">
        {item.icon}
        {item.warnIcon && (
          <span className="absolute -top-1 -right-1 text-[8px] font-bold leading-none">{item.warnIcon}</span>
        )}
      </span>
      {!collapsed && (
        <span className="whitespace-nowrap overflow-hidden text-ellipsis">{item.label}</span>
      )}
    </Link>
  )
}

function getPageTitle(pathname: string): string {
  if (pathname === '/dashboard')      return 'Dashboard'
  if (pathname === '/stocks')         return 'Stocks'
  if (pathname.startsWith('/stocks/'))return 'Stock Detail'
  if (pathname === '/screener')       return 'Screener'
  if (pathname === '/categories')     return 'Categories'
  if (pathname === '/market/fii-dii') return 'FII / DII Flows'
  if (pathname === '/filings')             return 'Filings'
  if (pathname === '/trading/positions')   return 'Positions'
  if (pathname === '/trading/history')     return 'Trade History'
  if (pathname === '/strategy')            return 'Strategy Lab'
  if (pathname === '/journal')             return 'Trading Journal'
  if (pathname === '/portfolio')           return 'External Portfolio'
  if (pathname === '/profile')             return 'My Profile'
  if (pathname === '/broker/kite')    return 'Kite Connect'
  if (pathname === '/admin/users')    return 'User Management'
  if (pathname === '/admin/settings') return 'Appearance Settings'
  return 'Trading Platform'
}

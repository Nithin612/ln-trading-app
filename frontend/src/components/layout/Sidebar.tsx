import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { NAV_GROUPS, isNavActive, type NavItem } from './nav-items'

export function SidebarLink({ item, collapsed, active, warn }: {
  item: NavItem
  collapsed: boolean
  active: boolean
  warn?: boolean
}) {
  return (
    <Link
      to={item.to}
      title={collapsed ? item.label : undefined}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors relative overflow-hidden',
        active
          ? 'text-(--color-accent)'
          : warn
            ? 'text-(--color-bear) hover:bg-(--color-surface-3)'
            : 'text-(--color-text-muted) hover:bg-(--color-surface-3) hover:text-(--color-text)',
        collapsed && 'justify-center',
      )}
      style={active ? { backgroundColor: 'color-mix(in srgb, var(--color-accent) 12%, transparent)' } : {}}
    >
      {active && (
        <span className="absolute left-0 top-0 bottom-0 w-[3px] bg-(--color-accent) rounded-r-sm" />
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

/** The grouped primary nav. Pure/presentational — testable with just a router. */
export function SidebarNav({ collapsed, pathname, isAdmin, kiteBanner }: {
  collapsed: boolean
  pathname: string
  isAdmin: boolean
  kiteBanner?: 'not-connected' | 'expiring' | null
}) {
  const groups = NAV_GROUPS.filter((g) => !g.adminOnly || isAdmin)
  return (
    <nav className="flex-1 py-3 px-2 overflow-y-auto overflow-x-hidden" aria-label="Primary">
      {groups.map((group, gi) => (
        <div key={group.title} className={gi > 0 ? 'mt-3' : ''}>
          {collapsed ? (
            gi > 0 ? <div className="my-2 mx-2 border-t border-(--color-border)" /> : null
          ) : (
            <p className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-(--color-text-muted)">
              {group.title}
            </p>
          )}
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const hasBanner = item.to === '/broker/kite' && !!kiteBanner
              return (
                <SidebarLink
                  key={item.to}
                  item={{
                    ...item,
                    warnIcon: hasBanner ? (kiteBanner === 'not-connected' ? '⚠' : '!') : undefined,
                  }}
                  collapsed={collapsed}
                  active={isNavActive(pathname, item.to)}
                  warn={hasBanner}
                />
              )
            })}
          </div>
        </div>
      ))}
    </nav>
  )
}

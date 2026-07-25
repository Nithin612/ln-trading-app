import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import { SidebarNav } from '@/components/layout/Sidebar'
import { NAV_GROUPS } from '@/components/layout/nav-items'

type NavProps = Parameters<typeof SidebarNav>[0]

function renderNav(props: Partial<NavProps> = {}) {
  return render(
    <MemoryRouter>
      <SidebarNav collapsed={false} pathname="/dashboard" isAdmin={false} {...props} />
    </MemoryRouter>,
  )
}

describe('SidebarNav', () => {
  it('renders grouped section headers', () => {
    renderNav()
    expect(screen.getByText('Markets')).toBeInTheDocument()
    expect(screen.getByText('Trading')).toBeInTheDocument()
    expect(screen.getByText('Analysis')).toBeInTheDocument()
  })

  it('renders links under their groups with correct hrefs', () => {
    renderNav()
    expect(screen.getByRole('link', { name: /Dashboard/ })).toHaveAttribute('href', '/dashboard')
    expect(screen.getByRole('link', { name: /Positions/ })).toHaveAttribute('href', '/trading/positions')
    expect(screen.getByRole('link', { name: /Strategy Lab/ })).toHaveAttribute('href', '/strategy')
  })

  it('hides the Admin group for non-admins', () => {
    renderNav({ isAdmin: false })
    expect(screen.queryByText('Admin')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Users/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(16) // Markets 7 + Styles 4 + Trading 2 + Analysis 3
  })

  it('shows the Admin group for admins', () => {
    renderNav({ isAdmin: true })
    expect(screen.getByText('Admin')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Users/ })).toHaveAttribute('href', '/admin/users')
    expect(screen.getAllByRole('link')).toHaveLength(19) // + 3 admin
  })

  it('marks the active route with aria-current', () => {
    renderNav({ pathname: '/trading/positions' })
    expect(screen.getByRole('link', { name: /Positions/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: /Dashboard/ })).not.toHaveAttribute('aria-current')
  })

  it('hides section labels when collapsed but keeps every link', () => {
    renderNav({ collapsed: true })
    expect(screen.queryByText('Markets')).not.toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(16)
  })

  it('every route appears in exactly one group', () => {
    const all = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.to))
    expect(new Set(all).size).toBe(all.length)
  })
})

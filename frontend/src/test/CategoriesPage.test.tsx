import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CategoriesPage } from '@/features/categories/CategoriesPage'
import { useAuthStore } from '@/store/authStore'
import * as catsApiModule from '@/lib/api/categories'

const adminUser = {
  id: 1, email: 'admin@example.com', full_name: 'Admin', role: 'admin',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper', allow_offmarket_entry: false, profit_lock_enabled: false,
  created_at: '', updated_at: '',
}
const regularUser = { ...adminUser, role: 'user', email: 'user@example.com' }

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

const makeCat = (
  overrides: Partial<catsApiModule.CategoryWithCount> = {},
): catsApiModule.CategoryWithCount => ({
  id: 1,
  name: 'EV',
  slug: 'ev',
  description: 'Electric vehicles',
  created_by: 1,
  created_at: '',
  stock_count: 3,
  ...overrides,
})

describe('CategoriesPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: 'test-token', user: adminUser })
  })

  it('renders category list', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'list').mockResolvedValue([
      makeCat({ id: 1, name: 'EV', stock_count: 3 }),
      makeCat({ id: 2, name: 'Defence', stock_count: 0 }),
    ])

    wrap(<CategoriesPage />)

    await waitFor(() => {
      expect(screen.getByText('EV')).toBeInTheDocument()
      expect(screen.getByText('Defence')).toBeInTheDocument()
    })
    expect(screen.getByText(/3 stocks/)).toBeInTheDocument()
    expect(screen.getByText(/0 stocks/)).toBeInTheDocument()
  })

  it('shows empty state when no categories', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'list').mockResolvedValue([])

    wrap(<CategoriesPage />)

    await waitFor(() =>
      expect(screen.getByText(/No categories yet/)).toBeInTheDocument()
    )
  })

  it('shows create form for admin', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'list').mockResolvedValue([])

    wrap(<CategoriesPage />)

    await waitFor(() =>
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    )
  })

  it('hides create form for non-admin', async () => {
    useAuthStore.setState({ accessToken: 'test-token', user: regularUser })
    vi.spyOn(catsApiModule.categoriesApi, 'list').mockResolvedValue([])

    wrap(<CategoriesPage />)

    await waitFor(() =>
      expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
    )
  })

  it('shows delete button only for admin', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'list').mockResolvedValue([
      makeCat({ name: 'EV' }),
    ])

    wrap(<CategoriesPage />)

    await waitFor(() => expect(screen.getByText('EV')).toBeInTheDocument())
    expect(screen.getByTitle('Delete category')).toBeInTheDocument()
  })

  it('hides delete button for non-admin', async () => {
    useAuthStore.setState({ accessToken: 'test-token', user: regularUser })
    vi.spyOn(catsApiModule.categoriesApi, 'list').mockResolvedValue([
      makeCat({ name: 'EV' }),
    ])

    wrap(<CategoriesPage />)

    await waitFor(() => expect(screen.getByText('EV')).toBeInTheDocument())
    expect(screen.queryByTitle('Delete category')).not.toBeInTheDocument()
  })

  it('shows description and slug', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'list').mockResolvedValue([
      makeCat({ description: 'Electric vehicles', slug: 'ev' }),
    ])

    wrap(<CategoriesPage />)

    await waitFor(() =>
      expect(screen.getByText('Electric vehicles')).toBeInTheDocument()
    )
    expect(screen.getByText(/slug: ev/)).toBeInTheDocument()
  })
})

import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TagPicker } from '@/features/categories/TagPicker'
import { useAuthStore } from '@/store/authStore'
import * as catsApiModule from '@/lib/api/categories'

const adminUser = {
  id: 1, email: 'admin@example.com', full_name: 'Admin', role: 'admin',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper',
  created_at: '', updated_at: '',
}
const regularUser = { ...adminUser, role: 'user' }

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
  description: null,
  created_by: 1,
  created_at: '',
  stock_count: 1,
  ...overrides,
})

describe('TagPicker', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: 'test-token', user: adminUser })
  })

  it('shows existing tags for the stock', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'getStockCategories').mockResolvedValue([
      makeCat({ name: 'EV' }),
      makeCat({ id: 2, name: 'Defence' }),
    ])

    wrap(<TagPicker stockId={1} />)

    await waitFor(() => {
      expect(screen.getByText('EV')).toBeInTheDocument()
      expect(screen.getByText('Defence')).toBeInTheDocument()
    })
  })

  it('shows "Add tag" button for admin', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'getStockCategories').mockResolvedValue([])

    wrap(<TagPicker stockId={1} />)

    await waitFor(() =>
      expect(screen.getByText(/Add tag/)).toBeInTheDocument()
    )
  })

  it('hides "Add tag" button for non-admin', async () => {
    useAuthStore.setState({ accessToken: 'test-token', user: regularUser })
    vi.spyOn(catsApiModule.categoriesApi, 'getStockCategories').mockResolvedValue([])

    wrap(<TagPicker stockId={1} />)

    await waitFor(() =>
      expect(screen.queryByText(/Add tag/)).not.toBeInTheDocument()
    )
  })

  it('shows remove (X) button per tag for admin', async () => {
    vi.spyOn(catsApiModule.categoriesApi, 'getStockCategories').mockResolvedValue([
      makeCat({ name: 'EV' }),
    ])

    wrap(<TagPicker stockId={1} />)

    await waitFor(() => expect(screen.getByText('EV')).toBeInTheDocument())
    expect(screen.getByTitle('Remove tag')).toBeInTheDocument()
  })

  it('hides remove button for non-admin', async () => {
    useAuthStore.setState({ accessToken: 'test-token', user: regularUser })
    vi.spyOn(catsApiModule.categoriesApi, 'getStockCategories').mockResolvedValue([
      makeCat({ name: 'EV' }),
    ])

    wrap(<TagPicker stockId={1} />)

    await waitFor(() => expect(screen.getByText('EV')).toBeInTheDocument())
    expect(screen.queryByTitle('Remove tag')).not.toBeInTheDocument()
  })
})

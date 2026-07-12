import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { WatchlistsPage } from '@/features/watchlists/WatchlistsPage'
import type { Watchlist } from '@/lib/api/watchlists'

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ accessToken: 'tok' }),
}))

vi.mock('@/lib/api/watchlists', () => ({
  watchlistsApi: {
    list: vi.fn(),
    create: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
    addStock: vi.fn(),
    removeStock: vi.fn(),
  },
}))

vi.mock('@/lib/api/stocks', () => ({
  stocksApi: { list: vi.fn() },
}))

import { stocksApi } from '@/lib/api/stocks'
import { watchlistsApi } from '@/lib/api/watchlists'

const WL: Watchlist = {
  id: 1,
  name: 'Breakouts',
  created_at: '2026-07-11T00:00:00Z',
  updated_at: '2026-07-11T00:00:00Z',
  items: [
    {
      stock_id: 42,
      symbol: 'RELIANCE',
      company_name: 'Reliance Industries',
      added_at: '2026-07-11T00:00:00Z',
    },
  ],
}

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <WatchlistsPage />
    </QueryClientProvider>,
  )
}

describe('WatchlistsPage', () => {
  beforeEach(() => {
    vi.mocked(watchlistsApi.list).mockReset()
    vi.mocked(watchlistsApi.create).mockReset()
    vi.mocked(watchlistsApi.addStock).mockReset()
    vi.mocked(watchlistsApi.removeStock).mockReset()
    vi.mocked(stocksApi.list).mockReset()
  })

  it('shows a loading skeleton while fetching', () => {
    vi.mocked(watchlistsApi.list).mockReturnValue(new Promise(() => {}))
    setup()
    expect(screen.getByTestId('watchlists-skeleton')).toBeInTheDocument()
  })

  it('shows the error state with a working retry', async () => {
    vi.mocked(watchlistsApi.list).mockRejectedValueOnce(new Error('boom'))
    vi.mocked(watchlistsApi.list).mockResolvedValueOnce([WL])
    setup()
    await waitFor(() =>
      expect(screen.getByText("Couldn't load watchlists")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Breakouts' })).toBeInTheDocument(),
    )
  })

  it('shows the empty state with the create form', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([])
    setup()
    await waitFor(() =>
      expect(screen.getByText('No watchlists yet')).toBeInTheDocument(),
    )
    expect(screen.getByLabelText('New watchlist name')).toBeInTheDocument()
  })

  it('creates a watchlist from the form', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([])
    vi.mocked(watchlistsApi.create).mockResolvedValue({ ...WL, id: 9, name: 'Momo' })
    setup()
    await waitFor(() =>
      expect(screen.getByText('No watchlists yet')).toBeInTheDocument(),
    )
    fireEvent.change(screen.getByLabelText('New watchlist name'), {
      target: { value: 'Momo' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Create/ }))
    await waitFor(() =>
      expect(watchlistsApi.create).toHaveBeenCalledWith('Momo', 'tok'),
    )
  })

  it('renders lists with item counts and the selected detail', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
    setup()
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText('Reliance Industries')).toBeInTheDocument()
    // picker entry (pressed = selected) + detail header both show the name
    expect(
      screen.getByRole('button', { name: /Breakouts/, pressed: true }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Breakouts' })).toBeInTheDocument()
  })

  it('adds a stock from search results', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
    vi.mocked(stocksApi.list).mockResolvedValue({
      items: [{ id: 77, symbol: 'TCS', company_name: 'Tata Consultancy' }],
      total: 1,
      page: 1,
      page_size: 8,
      pages: 1,
    } as never)
    vi.mocked(watchlistsApi.addStock).mockResolvedValue(WL)
    setup()
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Search stocks to add'), {
      target: { value: 'tc' },
    })
    await waitFor(() => expect(screen.getByText('TCS')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /TCS/ }))
    await waitFor(() =>
      expect(watchlistsApi.addStock).toHaveBeenCalledWith(1, 77, 'tok'),
    )
  })

  it('removes a stock from the selected watchlist', async () => {
    vi.mocked(watchlistsApi.list).mockResolvedValue([WL])
    vi.mocked(watchlistsApi.removeStock).mockResolvedValue({ ...WL, items: [] })
    setup()
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    fireEvent.click(
      screen.getByRole('button', { name: 'Remove RELIANCE from Breakouts' }),
    )
    await waitFor(() =>
      expect(watchlistsApi.removeStock).toHaveBeenCalledWith(1, 42, 'tok'),
    )
  })
})

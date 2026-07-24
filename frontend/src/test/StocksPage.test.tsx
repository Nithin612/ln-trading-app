import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useLiveQuotes', () => ({
  useLiveQuotes: () => ({ quotes: {}, candles: {}, signals: [], connected: false }),
}))
import { StocksPage } from '@/features/stocks/StocksPage'
import { useAuthStore } from '@/store/authStore'
import * as stocksApiModule from '@/lib/api/stocks'

beforeEach(() => {
  useAuthStore.setState({
    accessToken: 'test-token',
    user: { id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
            capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
            max_trades_per_day: 2, is_active: true, trading_mode: 'paper', allow_offmarket_entry: false,
            created_at: '', updated_at: '' },
  })
})

const makeStock = (overrides: Partial<stocksApiModule.Stock> = {}): stocksApiModule.Stock => ({
  id: 1, symbol: 'RELIANCE', exchange: 'NSE', isin: null,
  company_name: 'Reliance Industries Ltd', sector: 'Energy', industry: 'Energy',
  market_cap_cr: null, lot_size: 250, tick_size: '0.05',
  is_fno: true, is_nifty50: true, is_banknifty: false, is_finnifty: false,
  is_active: true, listed_on: null, created_at: '', updated_at: '',
  ...overrides,
})

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('StocksPage', () => {
  it('renders stock table rows from API', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockResolvedValue({
      items: [
        makeStock({ id: 1, symbol: 'RELIANCE', company_name: 'Reliance Industries Ltd' }),
        makeStock({ id: 2, symbol: 'INFY', company_name: 'Infosys Ltd', sector: 'IT', is_nifty50: true }),
      ],
      total: 2, page: 1, page_size: 50, pages: 1,
    })

    wrap(<StocksPage />)

    // Links render the symbol text; getByRole('link') matches anchor elements
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'RELIANCE' })).toBeInTheDocument()
    })
    expect(screen.getByRole('link', { name: 'INFY' })).toBeInTheDocument()
    // Company name is plain text inside a cell
    expect(screen.getByText('Reliance Industries Ltd')).toBeInTheDocument()
  })

  it('shows N50 badge for Nifty50 stocks', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockResolvedValue({
      items: [makeStock({ is_nifty50: true })],
      total: 1, page: 1, page_size: 50, pages: 1,
    })

    wrap(<StocksPage />)

    // Badge text — use regex to tolerate surrounding whitespace
    await waitFor(() => expect(screen.getByText(/^N50$/)).toBeInTheDocument())
  })

  it('shows error state on API failure', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockRejectedValue(new Error('Network error'))

    wrap(<StocksPage />)

    await waitFor(() =>
      expect(screen.getByText(/Failed to load stocks/)).toBeInTheDocument()
    )
  })

  it('links symbol to stock detail page', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockResolvedValue({
      items: [makeStock({ id: 42 })],
      total: 1, page: 1, page_size: 50, pages: 1,
    })

    wrap(<StocksPage />)

    await waitFor(() => {
      const link = screen.getByRole('link', { name: 'RELIANCE' })
      expect(link).toHaveAttribute('href', '/stocks/42')
    })
  })

  it('shows total stock count in header', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockResolvedValue({
      items: [makeStock()],
      total: 2348, page: 1, page_size: 50, pages: 47,
    })

    wrap(<StocksPage />)

    await waitFor(() => expect(screen.getByText(/2,348 stocks/)).toBeInTheDocument())
  })

  it('sector Select trigger shows "All sectors" by default', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockResolvedValue({
      items: [
        makeStock({ id: 1, sector: 'Energy' }),
        makeStock({ id: 2, symbol: 'INFY', company_name: 'Infosys Ltd', sector: 'IT' }),
      ],
      total: 2, page: 1, page_size: 2500, pages: 1,
    })

    wrap(<StocksPage />)

    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'RELIANCE' })).toBeInTheDocument()
    )

    // data-slot uniquely identifies the visible SelectTrigger (base-ui also renders a hidden native select)
    const trigger = document.querySelector('[data-slot="select-trigger"]')
    expect(trigger).toBeTruthy()
    expect(trigger!.textContent).toContain('All sectors')
  })

  it('sector Select shows sector options when opened', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockResolvedValue({
      items: [
        makeStock({ id: 1, sector: 'Energy' }),
        makeStock({ id: 2, symbol: 'INFY', company_name: 'Infosys Ltd', sector: 'IT' }),
      ],
      total: 2, page: 1, page_size: 2500, pages: 1,
    })

    wrap(<StocksPage />)

    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'RELIANCE' })).toBeInTheDocument()
    )

    fireEvent.click(document.querySelector('[data-slot="select-trigger"]')!)

    await waitFor(() => {
      const options = screen.getAllByRole('option')
      expect(options.some(el => el.textContent?.includes('All sectors'))).toBe(true)
      expect(options.some(el => el.textContent?.includes('Energy'))).toBe(true)
      expect(options.some(el => el.textContent?.includes('IT'))).toBe(true)
    })
  })
})

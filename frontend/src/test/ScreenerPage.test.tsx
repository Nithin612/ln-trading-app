import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ScreenerPage } from '@/features/screener/ScreenerPage'
import { useScreenerStore } from '@/features/screener/screenerStore'
import { useAuthStore } from '@/store/authStore'
import * as stocksApiModule from '@/lib/api/stocks'

beforeEach(() => {
  useAuthStore.setState({
    accessToken: 'test-token',
    user: { id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
            capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
            max_trades_per_day: 2, is_active: true, trading_mode: 'paper',
            created_at: '', updated_at: '' },
  })
  useScreenerStore.setState({
    filters: [], logic: 'AND', sortBy: 'symbol', sortDir: 'asc',
    limit: 50, offset: 0, result: null, isRunning: false, activeSavedScreen: null,
  })
  vi.spyOn(stocksApiModule.stocksApi, 'savedList').mockResolvedValue([])
})

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

const makeResult = (): stocksApiModule.ScreenerResult => ({
  items: [{
    id: 1, symbol: 'RELIANCE', exchange: 'NSE', isin: null,
    company_name: 'Reliance Industries Ltd', sector: 'Energy', industry: 'Energy',
    market_cap_cr: null, lot_size: 250, tick_size: '0.05',
    is_fno: true, is_nifty50: true, is_banknifty: false, is_finnifty: false,
    is_active: true, listed_on: null, created_at: '', updated_at: '',
  }],
  total: 1, limit: 50, offset: 0,
})

describe('ScreenerPage', () => {
  it('renders header and add filter button', () => {
    wrap(<ScreenerPage />)
    expect(screen.getByText('Screener')).toBeInTheDocument()
    expect(screen.getByText('Add filter')).toBeInTheDocument()
  })

  it('renders pre-built starter screens', () => {
    wrap(<ScreenerPage />)
    expect(screen.getByText('Nifty 50 only')).toBeInTheDocument()
    expect(screen.getByText('F&O stocks')).toBeInTheDocument()
  })

  it('can add a filter row', async () => {
    wrap(<ScreenerPage />)

    await userEvent.click(screen.getByText('Add filter'))
    // After adding a filter, at least one combobox (Select) appears
    expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0)
  })

  it('shows results after running screen', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'screenerRun').mockResolvedValue(makeResult())

    wrap(<ScreenerPage />)

    await userEvent.click(screen.getByRole('button', { name: /run screen/i }))

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'RELIANCE' })).toBeInTheDocument()
    })
    expect(screen.getByText('1 stocks matched')).toBeInTheDocument()
  })

  it('shows empty result message when no stocks match', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'screenerRun').mockResolvedValue({
      items: [], total: 0, limit: 50, offset: 0,
    })

    wrap(<ScreenerPage />)

    await userEvent.click(screen.getByRole('button', { name: /run screen/i }))

    await waitFor(() =>
      expect(screen.getByText('No stocks matched the filters.')).toBeInTheDocument()
    )
  })

  it('loads starter screen filters on click', async () => {
    wrap(<ScreenerPage />)

    await userEvent.click(screen.getByText('Nifty 50 only'))

    // A filter row should appear after loading the starter screen
    await waitFor(() => {
      expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0)
    })
  })

  it('shows Save Screen button only after running', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'screenerRun').mockResolvedValue(makeResult())

    wrap(<ScreenerPage />)

    // Save button should not exist before running
    expect(screen.queryByRole('button', { name: /save screen/i })).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: /run screen/i }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /save screen/i })).toBeInTheDocument()
    )
  })

  it('opens save dialog when Save Screen is clicked', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'screenerRun').mockResolvedValue(makeResult())

    wrap(<ScreenerPage />)

    await userEvent.click(screen.getByRole('button', { name: /run screen/i }))
    await waitFor(() => screen.getByRole('button', { name: /save screen/i }))
    await userEvent.click(screen.getByRole('button', { name: /save screen/i }))

    await waitFor(() => {
      // Dialog opens with a heading named "Save Screen"
      expect(screen.getByRole('heading', { name: 'Save Screen' })).toBeInTheDocument()
    })
  })
})

import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import { filingsApi, type FilingOut } from '@/lib/api/filings'
import { FilingsPage } from '@/features/filings/FilingsPage'

const mockUser = {
  id: 1, email: 'u@trading.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

function makeFiling(o: Partial<FilingOut> = {}): FilingOut {
  return {
    id: 1, stock_id: 1, symbol: 'RELIANCE', filing_type: 'earnings',
    headline: 'Q1 results beat estimates', body: null,
    filing_date: '2026-07-22', filing_time: '2026-07-22T10:30:00Z',
    source: 'BSE', source_url: 'https://bse.example.com/f/1',
    sentiment_score: null, is_high_impact: true, created_at: '', ...o,
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ accessToken: 'tok', user: mockUser })
})

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><FilingsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FilingsPage', () => {
  it('shows a loading skeleton while filings are pending', () => {
    vi.spyOn(filingsApi, 'getRecent').mockReturnValue(new Promise(() => {}))
    const { container } = setup()
    expect(screen.getByText('Corporate Filings')).toBeInTheDocument()
    expect(container.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('shows the empty state when there are no filings', async () => {
    vi.spyOn(filingsApi, 'getRecent').mockResolvedValue({ total: 0, filings: [] })
    setup()
    await waitFor(() => expect(screen.getByText(/No filings found/i)).toBeInTheDocument())
  })

  it('renders a filing row with symbol, headline and a HIGH-impact badge', async () => {
    vi.spyOn(filingsApi, 'getRecent').mockResolvedValue({ total: 1, filings: [makeFiling()] })
    setup()
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText('Q1 results beat estimates')).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('filters rows client-side by the symbol search box', async () => {
    vi.spyOn(filingsApi, 'getRecent').mockResolvedValue({
      total: 2,
      filings: [
        makeFiling({ id: 1, symbol: 'RELIANCE' }),
        makeFiling({ id: 2, symbol: 'TCS', headline: 'Board meeting scheduled', is_high_impact: false }),
      ],
    })
    setup()
    await waitFor(() => expect(screen.getByText('TCS')).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('e.g. RELIANCE'), { target: { value: 'REL' } })
    await waitFor(() => expect(screen.queryByText('TCS')).toBeNull())  // debounced filter drops the non-match
    expect(screen.getByText('RELIANCE')).toBeInTheDocument()
  })
})

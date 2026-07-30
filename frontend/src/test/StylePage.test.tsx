import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import * as suggestionsApiModule from '@/lib/api/suggestions'
import type { SuggestionOut } from '@/lib/api/suggestions'
import * as tradingApiModule from '@/lib/api/trading'
import { StylePage } from '@/features/styles/StylePage'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, profit_lock_enabled: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: 'tok', user: mockUser })
})

function makeSuggestion(o: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    id: 's1', symbol: 'RELIANCE', direction: 'BUY', classification: 'swing', timeframe: '1d',
    entry_price: '2850.0000', stop_loss: '2800.0000', take_profit: '2950.0000',
    suggested_qty: 35, confidence_pct: 82, headline: 'BUY RELIANCE', factor_scores: {},
    setup_trigger: null, volatility_reduced: false, profile_key: 'rrbo', profile_name: 'RRBO',
    profile_version: 1, style: 'swing',
    validity_until: new Date(Date.now() + 5 * 86400000).toISOString(),
    created_at: new Date().toISOString(),
    ...o,
  }
}

function renderStyle(style = 'swing') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/styles/${style}`]}>
        <Routes>
          <Route path="/styles/:style" element={<StylePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('StylePage', () => {
  it('renders suggestions with the style header', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    renderStyle('swing')
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText(/Swing suggestions/i)).toBeInTheDocument()
    expect(screen.getByText(/▲ BUY/)).toBeInTheDocument()
  })

  it('shows loading skeletons', () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockReturnValue(new Promise(() => {}))
    renderStyle('swing')
    expect(screen.getByLabelText('loading suggestions')).toBeInTheDocument()
  })

  it('shows an empty state when there are no suggestions', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'fno', total: 0, suggestions: [] })
    renderStyle('fno')
    await waitFor(() => expect(screen.getByText(/No F&O suggestions/i)).toBeInTheDocument())
  })

  it('shows an error state with retry', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockRejectedValue(new Error('boom'))
    renderStyle('swing')
    await waitFor(() => expect(screen.getByText(/Could not load/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('rejects an unknown style', () => {
    renderStyle('bogus')
    expect(screen.getByText(/Unknown style/i)).toBeInTheDocument()
  })

  it('paper-trades a suggestion in its own direction', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion({ direction: 'SELL' })] })
    const placeSpy = vi.spyOn(tradingApiModule.tradingApi, 'placeOrder').mockResolvedValue({
      id: 'o1', user_id: 1, signal_id: 's1', stock_id: 1, symbol: 'RELIANCE', mode: 'paper',
      side: 'SELL', order_type: 'MARKET', quantity: 35, price: null, status: 'filled',
      placed_at: '', filled_at: '', filled_price: '2850.0000', filled_qty: 35, error_message: null,
    })
    renderStyle('swing')
    await waitFor(() => screen.getByText('RELIANCE'))
    fireEvent.click(screen.getByTitle('Paper Sell (open short)'))
    await waitFor(() =>
      expect(placeSpy).toHaveBeenCalledWith({ signal_id: 's1', side: 'SELL' }, 'tok'),
    )
  })
})

import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import * as suggestionsApiModule from '@/lib/api/suggestions'
import type { SuggestionOut } from '@/lib/api/suggestions'
import * as analyticsApiModule from '@/lib/api/analytics'
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
    // Each section reports its own failure independently (the provisional
    // panel below has its own "could not load"), so scope to the suggestions one.
    await waitFor(() =>
      expect(screen.getByText(/Could not load Swing suggestions/i)).toBeInTheDocument(),
    )
    expect(screen.getAllByRole('button', { name: /retry/i }).length).toBeGreaterThan(0)
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

  // ── v2 additions (Phase 5 slice 5.3) ──────────────────────────────────────

  it('separates the committed layer from the forming one', async () => {
    // Conflating them is a correctness problem: only committed signals are
    // tradeable, and provisional scores must be labelled as such end-to-end.
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    renderStyle('swing')
    // The tradeable table is badged COMMITTED; the forming leaderboard below
    // carries its own PROVISIONAL badge and lives in a separate panel.
    expect(await screen.findByRole('table', { name: /committed suggestions/i })).toBeInTheDocument()
    expect(screen.getByText('COMMITTED')).toBeInTheDocument()
    expect(screen.getByText('Provisional')).toBeInTheDocument()
    expect(screen.getByText('Live confidence')).toBeInTheDocument()
  })

  it('locks the provisional panel to this style (no style tabs)', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    renderStyle('swing')
    await waitFor(() => expect(screen.getByText('Live confidence')).toBeInTheDocument())
    // The dashboard keeps the tabbed leaderboard; a style page must not offer
    // navigation to a style the page isn't about.
    expect(screen.queryByRole('tablist', { name: /leaderboard style/i })).not.toBeInTheDocument()
  })

  it('shows reward:risk computed from the plan', async () => {
    // entry 2850, SL 2800 (risk 50), TP 2950 (reward 100) → 2.00:1
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    renderStyle('swing')
    await waitFor(() => expect(screen.getByText('2.00:1')).toBeInTheDocument())
  })

  it('opens the factor drawer from the symbol, keyboard-reachable', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle').mockResolvedValue({
      style: 'swing', total: 1,
      suggestions: [makeSuggestion({
        factor_scores: {
          ema_stack: { weight: 0.3, score: 1.0, explanation: 'price above all EMAs' },
          rsi: { weight: 0.2, score: -0.5, explanation: 'RSI rolling over' },
        },
        setup_trigger: { kind: 'range_breakout', level: '2845.00' },
      })],
    })
    renderStyle('swing')
    const symbolButton = await screen.findByRole('button', { name: /Why RELIANCE fired/i })
    fireEvent.click(symbolButton)

    await waitFor(() => expect(screen.getByText('Factor breakdown')).toBeInTheDocument())
    expect(screen.getByText('ema_stack')).toBeInTheDocument()
    expect(screen.getByText('price above all EMAs')).toBeInTheDocument()
    // contribution = weight × score, sign preserved
    expect(screen.getByText(/w 0\.30 × 1\.00 =/)).toBeInTheDocument()
    expect(screen.getByText('+0.30')).toBeInTheDocument()
    expect(screen.getByText('-0.10')).toBeInTheDocument()   // 0.2 × -0.5
    expect(screen.getByText('range_breakout')).toBeInTheDocument()
    expect(screen.getByText('2.00 : 1')).toBeInTheDocument()
  })

  it('orders factors by absolute contribution, not alphabetically', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle').mockResolvedValue({
      style: 'swing', total: 1,
      suggestions: [makeSuggestion({
        factor_scores: {
          aaa_small: { weight: 0.05, score: 0.2, explanation: 'minor' },
          zzz_big: { weight: 0.4, score: 1.0, explanation: 'dominant' },
        },
      })],
    })
    renderStyle('swing')
    fireEvent.click(await screen.findByRole('button', { name: /Why RELIANCE fired/i }))
    await waitFor(() => expect(screen.getByText('zzz_big')).toBeInTheDocument())
    const names = screen.getAllByText(/aaa_small|zzz_big/).map((el) => el.textContent)
    expect(names).toEqual(['zzz_big', 'aaa_small'])   // what drove it, first
  })

  it('renders the per-style stats header from tracked outcomes', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockResolvedValue({
      epoch: '2026-08-06', total_outcomes: 40,
      // REAL backend contract (app/api/v1/analytics.py): hit_rate and
      // entry_rate are FRACTIONS; avg_return_pct is already a PERCENT.
      styles: [{
        style: 'swing', total: 50, entered: 40, wins: 24, losses: 16, no_entry: 8,
        timed_out: 2, pending: 0, sample: 50, hit_rate: 24 / 40, entry_rate: 40 / 50,
        avg_return_pct: 1.4,
      }],
    })
    renderStyle('swing')
    await waitFor(() => expect(screen.getByText('Hit rate')).toBeInTheDocument())
    expect(screen.getByText('60.00%')).toBeInTheDocument()     // 0.6 → 60%
    expect(screen.getByText(/24W \/ 16L · n=40 decided/)).toBeInTheDocument()
    expect(screen.getByText('80.00%')).toBeInTheDocument()     // 0.8 → 80%
    expect(screen.getByText('+1.40%')).toBeInTheDocument()     // already a percent
    // Canary for the units bug: a fraction rendered raw reads as "0.60%".
    expect(screen.queryByText('0.60%')).not.toBeInTheDocument()
    expect(screen.queryByText('0.80%')).not.toBeInTheDocument()
  })

  it('colours a healthy hit rate as profit, not loss (fraction threshold)', async () => {
    // Regression: comparing a 0..1 fraction against 50 made EVERY hit rate red.
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockResolvedValue({
      epoch: '2026-08-06', total_outcomes: 40,
      styles: [{
        style: 'swing', total: 50, entered: 40, wins: 24, losses: 16, no_entry: 8,
        timed_out: 2, pending: 0, sample: 50, hit_rate: 0.6, entry_rate: 0.8,
        avg_return_pct: 1.4,
      }],
    })
    renderStyle('swing')
    const value = await screen.findByText('60.00%')
    expect(value).toHaveStyle({ color: 'var(--color-profit)' })
  })

  it('judges the hit-rate sample on DECIDED outcomes, not resolved ones', async () => {
    // 2W/2L with 30 no-entries: `sample` is 34 but only 4 decisions back the
    // rate — it must not be endorsed just because no_entry inflates the count.
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockResolvedValue({
      epoch: '2026-08-06', total_outcomes: 34,
      styles: [{
        style: 'swing', total: 40, entered: 4, wins: 2, losses: 2, no_entry: 30,
        timed_out: 2, pending: 0, sample: 34, hit_rate: 0.5, entry_rate: 0.1,
        avg_return_pct: 0.2,
      }],
    })
    renderStyle('swing')
    await waitFor(() =>
      expect(screen.getByText(/n=4 decided — too small to read/)).toBeInTheDocument(),
    )
    expect(await screen.findByText('50.00%')).toHaveStyle({ color: 'var(--color-text-muted)' })
  })

  it('refuses to dress up a hit rate computed from too few outcomes', async () => {
    // The binding lesson from docs/analysis: a rate off a handful of outcomes
    // looks like an edge and isn't.
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    vi.spyOn(analyticsApiModule.analyticsApi, 'getOutcomes').mockResolvedValue({
      epoch: '2026-08-06', total_outcomes: 3,
      styles: [{
        style: 'swing', total: 4, entered: 3, wins: 3, losses: 0, no_entry: 1,
        timed_out: 0, pending: 0, sample: 4, hit_rate: 1.0, entry_rate: 0.75,
        avg_return_pct: 2.0,
      }],
    })
    renderStyle('swing')
    await waitFor(() => expect(screen.getByText('100.00%')).toBeInTheDocument())
    expect(screen.getByText(/n=3 decided — too small to read/)).toBeInTheDocument()
    // A perfect 3/3 must NOT be dressed up in profit green.
    expect(screen.getByText('100.00%')).toHaveStyle({ color: 'var(--color-text-muted)' })
  })

  it('virtualizes a large suggestion list instead of rendering every row', async () => {
    const many = Array.from({ length: 300 }, (_, i) =>
      makeSuggestion({ id: `s${i}`, symbol: `SYM${i}` }),
    )
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: many.length, suggestions: many })
    renderStyle('swing')
    const table = await screen.findByRole('table', { name: /committed suggestions/i })

    const symbolButtons = within(table).getAllByRole('button', { name: /^Why SYM\d+ fired$/ })
    expect(symbolButtons.length).toBeGreaterThan(0)
    expect(symbolButtons.length).toBeLessThan(many.length)   // a window, not all 300

    // Spacer rows stand in for the un-rendered ones so the scrollbar still
    // reflects the full dataset.
    const spacers = table.querySelectorAll('[data-slot="virtual-spacer"]')
    expect(spacers.length).toBeGreaterThan(0)
    // The first row is in the window; the last is not.
    expect(within(table).getByRole('button', { name: 'Why SYM0 fired' })).toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: 'Why SYM299 fired' })).toBeNull()
  })

  it('renders every row for a small list (windowing stays off under 200)', async () => {
    const few = Array.from({ length: 12 }, (_, i) =>
      makeSuggestion({ id: `s${i}`, symbol: `SYM${i}` }),
    )
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: few.length, suggestions: few })
    renderStyle('swing')
    const table = await screen.findByRole('table', { name: /committed suggestions/i })
    expect(within(table).getAllByRole('button', { name: /^Why SYM\d+ fired$/ })).toHaveLength(12)
    expect(table.querySelectorAll('[data-slot="virtual-spacer"]')).toHaveLength(0)
  })

  it('shows a live LTP column that starts empty until a tick arrives', async () => {
    vi.spyOn(suggestionsApiModule.suggestionsApi, 'getByStyle')
      .mockResolvedValue({ style: 'swing', total: 1, suggestions: [makeSuggestion()] })
    renderStyle('swing')
    const table = await screen.findByRole('table', { name: /committed suggestions/i })
    expect(within(table).getByText('LTP')).toBeInTheDocument()
    // No socket in tests → PriceCell renders its placeholder, never a stale 0.
    expect(within(table).getAllByText('—').length).toBeGreaterThan(0)
  })
})

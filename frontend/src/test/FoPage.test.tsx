import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { FoPage } from '@/features/fo/FoPage'
import { ApiError } from '@/lib/api/client'
import * as foApiModule from '@/lib/api/fo'
import type {
  ChainLeg, FoAnalytics, IvRank, OptionChain, SpreadCandidate,
} from '@/lib/api/fo'
import { useAuthStore } from '@/store/authStore'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, profit_lock_enabled: false,
  is_active: true, trading_mode: 'paper', created_at: '', updated_at: '',
}

const EXPIRY = '2026-07-30'

function leg(o: Partial<ChainLeg> & Pick<ChainLeg, 'strike' | 'option_type'>): ChainLeg {
  return {
    oi: 100, volume: 50, ltp: '210.00',
    iv: 0.18, delta: 0.5, gamma: 0.0002, vega: 12.5, theta: -8.25,
    ...o,
  }
}

function makeChain(o: Partial<OptionChain> = {}): OptionChain {
  return {
    symbol: 'NIFTY', expiry: EXPIRY, source: 'eod',
    spot: '24600.00', atm_strike: '24600.00',
    legs: [
      leg({ strike: '24500.00', option_type: 'CE', oi: 1200, delta: 0.62 }),
      leg({ strike: '24500.00', option_type: 'PE', oi: 800, delta: -0.38 }),
      leg({ strike: '24600.00', option_type: 'CE', oi: 2400, delta: 0.51 }),
      leg({ strike: '24600.00', option_type: 'PE', oi: 2000, delta: -0.49 }),
    ],
    as_of: '2026-07-20', fut_price: '24620.00', dte: 10,
    ...o,
  }
}

function makeAnalytics(o: Partial<FoAnalytics> = {}): FoAnalytics {
  return {
    symbol: 'NIFTY', expiry: EXPIRY, source: 'eod',
    spot: '24600.00', atm_strike: '24600.00',
    pcr: { pcr_oi: 1.25, pcr_volume: 0.98, total_ce_oi: 4000, total_pe_oi: 5000 },
    max_pain: '24500.00',
    basis: {
      fut_close: '24620.00', underlying_close: '24600.00', basis: '20.00', basis_pct: 0.081,
    },
    vix: { current: '13.40', percentile: 42.0, band: 'normal', sample: 252 },
    ...o,
  }
}

function makeIvRank(o: Partial<IvRank> = {}): IvRank {
  return {
    symbol: 'NIFTY', as_of: '2026-07-20', current_iv: 0.18, rank: 63.0,
    percentile: 61.0, min_iv: 0.10, max_iv: 0.30, sample: 252,
    ...o,
  }
}

function makeCandidate(o: Partial<SpreadCandidate> = {}): SpreadCandidate {
  return {
    structure: 'bull_put',
    legs: [
      { action: 'sell', option_type: 'PE', strike: '24000.00', premium: '95.00' },
      { action: 'buy', option_type: 'PE', strike: '23900.00', premium: '62.00' },
    ],
    net_credit: '33.00', max_profit: '33.00', max_loss: '67.00', width: '100.00',
    breakevens: ['23967.00'], pop: 0.71, expectancy: '-3.20',
    margin_est: '67.00', return_on_margin: 0.4925, short_delta: -0.16,
    dte: 28, expiry: EXPIRY,
    exit_plan: { take_profit_credit: '16.50', stop_loss_amount: '66.00', time_stop_dte: 21 },
    rationale: 'IV-rank 63, 0.16Δ short, above max-pain',
    ...o,
  }
}

/** Every /fo call stubbed with a sane default; individual tests override. */
function stubAll(overrides: {
  chain?: Partial<OptionChain>
  analytics?: Partial<FoAnalytics>
  candidates?: SpreadCandidate[]
} = {}) {
  vi.spyOn(foApiModule.foApi, 'getUnderlyings').mockResolvedValue({
    as_of: '2026-07-20', symbols: ['BANKNIFTY', 'NIFTY'],
  })
  vi.spyOn(foApiModule.foApi, 'getExpiries').mockResolvedValue({
    symbol: 'NIFTY', as_of: '2026-07-20',
    expiries: [{ expiry: EXPIRY, dte: 10 }, { expiry: '2026-08-27', dte: 38 }],
  })
  vi.spyOn(foApiModule.foApi, 'getAnalytics').mockResolvedValue(makeAnalytics(overrides.analytics))
  vi.spyOn(foApiModule.foApi, 'getIvRank').mockResolvedValue(makeIvRank())
  vi.spyOn(foApiModule.foApi, 'getChain').mockResolvedValue(makeChain(overrides.chain))
  vi.spyOn(foApiModule.foApi, 'getSuggestions').mockResolvedValue({
    symbol: 'NIFTY', candidates: overrides.candidates ?? [makeCandidate()],
  })
}

/**
 * Values repeat across the page (a max-pain value is also a strike), so
 * assertions are scoped: `tile()` for an analytics tile, `ladder()` for the
 * chain table. An unscoped getByText would match the wrong element or throw.
 */
function tile(label: string): HTMLElement {
  const el = screen.getByText(label).parentElement
  if (!el) throw new Error(`tile "${label}" has no container`)
  return el
}

function ladder(): Promise<HTMLElement> {
  return screen.findByRole('table', { name: /option chain ladder/i })
}

function renderFo() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/styles/fno']}>
        <FoPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ accessToken: 'tok', user: mockUser })
})

describe('FoPage', () => {
  it('renders the analytics strip from recorded data', async () => {
    stubAll()
    renderFo()
    await waitFor(() => expect(screen.getByText('PCR (OI)')).toBeInTheDocument())
    expect(within(tile('PCR (OI)')).getByText('1.25')).toBeInTheDocument()
    expect(within(tile('Max pain')).getByText('24,500.00')).toBeInTheDocument()
    expect(within(tile('IV rank')).getByText('63.00%')).toBeInTheDocument()
    expect(within(tile('India VIX')).getByText('13.40')).toBeInTheDocument()
    expect(within(tile('Basis')).getByText('20.00')).toBeInTheDocument()
    expect(within(tile('Spot / ATM')).getByText('₹24,600.00')).toBeInTheDocument()
  })

  it('defaults to the nearest open expiry', async () => {
    stubAll()
    renderFo()
    await waitFor(() => expect(foApiModule.foApi.getChain).toHaveBeenCalled())
    expect(foApiModule.foApi.getChain).toHaveBeenCalledWith(
      'NIFTY', EXPIRY, 'tok', expect.objectContaining({ source: 'eod', greeks: true }),
    )
  })

  it('renders the chain ladder with per-strike IV, delta and OI', async () => {
    stubAll()
    renderFo()
    const t = within(await ladder())
    expect(t.getAllByText('24,600.00').length).toBeGreaterThan(0)  // strike
    expect(t.getByText('ATM')).toBeInTheDocument()                 // non-colour marker
    expect(t.getAllByText('18.00%').length).toBeGreaterThan(0)     // IV as a percent
    expect(t.getByText('0.6200')).toBeInTheDocument()              // call delta, 4dp
    expect(t.getByText('-0.3800')).toBeInTheDocument()             // put delta is negative
    expect(t.getByText('2,400')).toBeInTheDocument()               // OI, grouped
    expect(t.getAllByText('-8.25').length).toBeGreaterThan(0)      // theta, 2dp
  })

  it('states the chain provenance so an EOD chain cannot read as live', async () => {
    stubAll()
    renderFo()
    await waitFor(() =>
      expect(screen.getByText(/EOD close 2026-07-20/)).toBeInTheDocument(),
    )
    // One line, stating source + day + the forward and dte the Greeks used.
    expect(
      screen.getByText(/EOD close 2026-07-20 · Greeks off future 24620\.00 · 10d/),
    ).toBeInTheDocument()
  })

  it('shows "—" not 0 for legs that could not be priced', async () => {
    // An unpriced leg must never look like a zero-delta one.
    stubAll({
      chain: {
        legs: [
          leg({
            strike: '24600.00', option_type: 'CE',
            iv: null, delta: null, gamma: null, vega: null, theta: null,
          }),
        ],
        fut_price: null, dte: null, as_of: '2026-07-20',
      },
    })
    renderFo()
    const t = within(await ladder())
    expect(t.queryByText('0.0000')).not.toBeInTheDocument()
    expect(t.getAllByText('—').length).toBeGreaterThan(0)
    // And it explains WHY the Greeks are missing.
    expect(screen.getByText(/no futures close for this expiry/i)).toBeInTheDocument()
  })

  it('toggling Greeks off drops the Γ/V/Θ columns and refetches without them', async () => {
    stubAll()
    renderFo()
    const t = within(await ladder())
    expect(t.getAllByText('Γ').length).toBe(2) // one per side

    await userEvent.click(screen.getByRole('checkbox', { name: /Greeks/i }))
    await waitFor(() =>
      expect(within(screen.getByRole('table', { name: /option chain ladder/i }))
        .queryByText('Γ')).not.toBeInTheDocument(),
    )
    expect(foApiModule.foApi.getChain).toHaveBeenLastCalledWith(
      'NIFTY', EXPIRY, 'tok', expect.objectContaining({ greeks: false }),
    )
  })

  it('renders an option-selling candidate with its full economics', async () => {
    stubAll()
    renderFo()
    const card = within((await screen.findByText('Bull put spread')).closest('article')!)
    expect(card.getByText('▼ SELL')).toBeInTheDocument()
    expect(card.getByText('▲ BUY')).toBeInTheDocument()
    expect(within(card.getByText('Net credit').parentElement!).getByText('₹33.00')).toBeInTheDocument()
    expect(within(card.getByText('Max loss').parentElement!).getByText('₹67.00')).toBeInTheDocument()
    expect(within(card.getByText('POP').parentElement!).getByText('71.00%')).toBeInTheDocument()
    expect(
      within(card.getByText('Return on margin').parentElement!).getByText('49.25%'),
    ).toBeInTheDocument()
    expect(card.getByText(/time stop 21 DTE/)).toBeInTheDocument()
    expect(card.getByText('23,967.00')).toBeInTheDocument()    // breakeven
  })

  it('labels expectancy report-only and the panel forward-tested', async () => {
    // The engine's own correction: a small negative expectancy on a fairly
    // priced spread is EXPECTED, so it must not read as "this loses money".
    stubAll()
    renderFo()
    await waitFor(() => expect(screen.getByText('Bull put spread')).toBeInTheDocument())
    expect(screen.getByText(/report-only/i)).toBeInTheDocument()
    expect(screen.getByText(/Forward-tested, not backtested/i)).toBeInTheDocument()
  })

  it('treats an empty candidate list as a deliberate no-trade answer', async () => {
    stubAll({ candidates: [] })
    renderFo()
    await waitFor(() =>
      expect(screen.getByText(/No candidates clear the gates/i)).toBeInTheDocument(),
    )
    expect(screen.getByText(/fails CLOSED/i)).toBeInTheDocument()
  })

  it('renders the VIX veto as a stand-down when the regime is unknown', async () => {
    // No VIX data must not look OK — the veto fails closed.
    stubAll({ analytics: { vix: null } })
    renderFo()
    await waitFor(() => expect(screen.getByText('India VIX')).toBeInTheDocument())
    expect(screen.getByText('unknown')).toBeInTheDocument()
    expect(screen.getByText(/selling vetoed \(fail-closed\)/i)).toBeInTheDocument()
  })

  it('flags a high-VIX regime as vetoing selling', async () => {
    stubAll({
      analytics: { vix: { current: '28.10', percentile: 96.0, band: 'high', sample: 252 } },
    })
    renderFo()
    await waitFor(() => expect(screen.getByText(/selling vetoed/i)).toBeInTheDocument())
  })

  it('reports missing IV-rank history as an empty state, not an error', async () => {
    stubAll()
    vi.spyOn(foApiModule.foApi, 'getIvRank').mockRejectedValue(
      new ApiError(404, 'insufficient option history to compute IV rank'),
    )
    renderFo()
    await waitFor(() => expect(screen.getByText(/not enough history/i)).toBeInTheDocument())
  })

  it('shows loading skeletons for the chain', async () => {
    stubAll()
    vi.spyOn(foApiModule.foApi, 'getChain').mockReturnValue(new Promise(() => {}))
    renderFo()
    // The skeleton only appears once an expiry has defaulted in and the chain
    // query is actually enabled.
    expect(await screen.findByLabelText('loading option chain')).toBeInTheDocument()
  })

  it('offers a retry when the chain request fails', async () => {
    stubAll()
    vi.spyOn(foApiModule.foApi, 'getChain').mockRejectedValue(new ApiError(500, 'boom'))
    renderFo()
    await waitFor(() => expect(screen.getByText(/Could not load the NIFTY chain/)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('explains an empty intraday chain and points at the EOD source', async () => {
    stubAll({ chain: { legs: [], as_of: null, fut_price: null, dte: null } })
    renderFo()
    await waitFor(() => expect(screen.getByText(/No chain recorded/i)).toBeInTheDocument())
  })

  it('re-defaults the expiry when the underlying changes', async () => {
    stubAll()
    vi.spyOn(foApiModule.foApi, 'getExpiries').mockImplementation(async (sym: string) =>
      sym === 'BANKNIFTY'
        ? { symbol: 'BANKNIFTY', as_of: '2026-07-20', expiries: [{ expiry: '2026-08-27', dte: 38 }] }
        : { symbol: 'NIFTY', as_of: '2026-07-20', expiries: [{ expiry: EXPIRY, dte: 10 }] },
    )
    renderFo()
    await waitFor(() => expect(foApiModule.foApi.getChain).toHaveBeenCalled())

    await userEvent.click(screen.getByText('NIFTY'))
    await userEvent.click(await screen.findByRole('option', { name: 'BANKNIFTY' }))

    // An expiry from the previous underlying would query a chain that cannot exist.
    await waitFor(() =>
      expect(foApiModule.foApi.getChain).toHaveBeenLastCalledWith(
        'BANKNIFTY', '2026-08-27', 'tok', expect.anything(),
      ),
    )
  })
})

/**
 * Queue item 27 — the LTP must not claim a direction it never computed.
 *
 * ⛔ The defect: `StockDetailPage` painted the live price `--color-bull` unconditionally, so
 * a FALLING price rendered green. That is money-correctness on the surface the user looks at
 * most, not a style nit — the colour was an assertion about direction with nothing behind it.
 *
 * ⚠ The live feed cannot supply the answer: `LtpQuote` is `{symbol, ltp, ts}` and carries no
 * reference price. The basis is therefore the last COMPLETED daily close, and where there is
 * none the honest rendering is NEUTRAL — "not assessable" beats a plausible-looking default
 * (A24). These tests pin all three states, because a two-state fix would just relocate the bug.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StockDetailPage } from '@/pages/stocks/StockDetailPage'
import { useAuthStore } from '@/store/authStore'
import * as stocksApiModule from '@/lib/api/stocks'
import * as marketDataApiModule from '@/lib/api/market_data'
import * as signalsApiModule from '@/lib/api/signals'
import * as filingsApiModule from '@/lib/api/filings'
import * as liveQuotesModule from '@/hooks/useLiveQuotes'

// lightweight-charts measures real DOM and throws in jsdom; it is not what is under test.
vi.mock('@/components/charts/CandlestickChart', () => ({
  CandlestickChart: () => null,
}))

const PREV_CLOSE = 500

/** Two completed sessions, both strictly BEFORE today, so the last one is the reference. */
function bars(lastClose = PREV_CLOSE) {
  const mk = (daysAgo: number, close: number) => {
    const d = new Date(Date.now() - daysAgo * 86400000)
    return {
      time: d.toISOString(),
      open: String(close), high: String(close), low: String(close),
      close: String(close), volume: 1000,
    }
  }
  return { bars: [mk(5, lastClose), mk(3, lastClose)] }
}

function mockAll(ltpValue: number | undefined, ohlcv: { bars: unknown[] }) {
  vi.spyOn(stocksApiModule.stocksApi, 'get').mockResolvedValue({
    id: 1, symbol: 'ACME', company_name: 'Acme Ltd', exchange: 'NSE',
    is_nifty50: false, is_banknifty: false, is_finnifty: false, is_fno: false,
    is_active: true,
  } as never)
  vi.spyOn(marketDataApiModule.marketDataApi, 'getOhlcv').mockResolvedValue(ohlcv as never)
  vi.spyOn(signalsApiModule.signalsApi, 'getActive').mockResolvedValue({ signals: [], total: 0 } as never)
  vi.spyOn(filingsApiModule.filingsApi, 'getRecent').mockResolvedValue({ total: 0, filings: [] } as never)
  vi.spyOn(liveQuotesModule, 'useLiveQuotes').mockReturnValue({
    quotes: ltpValue === undefined
      ? {}
      : { ACME: { symbol: 'ACME', ltp: ltpValue, ts: new Date().toISOString() } },
    candles: {},
    signals: [],
    connected: true,
  } as never)
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/stocks/1']}>
        <Routes>
          <Route path="/stocks/:id" element={<StockDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** The rendered LTP element, found by its price text.
 *
 * ⚠ Waits for the COLOUR to settle, not merely for the element to exist. The price comes from
 * the live-quote hook synchronously while the reference close arrives with the OHLCV query, so
 * there is a real interval in which the LTP is on screen and correctly reads "not assessable".
 * Asserting on first paint tests the loading state and calls it a direction bug.
 */
async function ltpEl(price: string, expected: string) {
  const el = await screen.findByText(new RegExp(`₹\\s*${price}`))
  await waitFor(() => expect(el.style.color).toBe(expected))
  return el
}

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ accessToken: 'test-token', user: null as never })
})

describe('item 27 — the LTP colour is a computed direction, not a constant', () => {
  it('⛔ REGRESSION: a FALLING price is not painted bull', async () => {
    mockAll(PREV_CLOSE - 25, bars())   // 500 -> 475
    renderPage()

    const el = await ltpEl('475', 'var(--color-bear)')
    expect(el.style.color).not.toBe('var(--color-bull)')
  })

  it('a RISING price is painted bull', async () => {
    mockAll(PREV_CLOSE + 25, bars())   // 500 -> 525
    renderPage()

    await ltpEl('525', 'var(--color-bull)')
  })

  it('⭐ with NO completed prior close the direction is NOT ASSESSABLE, never green', async () => {
    mockAll(PREV_CLOSE, { bars: [] })
    renderPage()

    const el = await ltpEl('500', 'var(--color-neutral)')
    expect(el.style.color).toBe('var(--color-neutral)')
    expect(await screen.findByText(/— vs prev close/)).toBeTruthy()
  })

  it('an UNCHANGED price is neutral — flat is not up', async () => {
    mockAll(PREV_CLOSE, bars())
    renderPage()

    await ltpEl('500', 'var(--color-neutral)')
  })

  it('⭐ the BASIS is rendered, so the colour can be checked rather than trusted', async () => {
    mockAll(PREV_CLOSE - 25, bars())
    renderPage()

    // -5.00% against the previous close, shown beside the price (A24: ship the assumption
    // the figure inherits in the same visual element).
    await waitFor(async () => {
      expect(await screen.findByText(/-5\.00%\s*vs prev close/)).toBeTruthy()
    })
  })

  it('⚠ liveness is not direction — the Live indicator carries no bull/bear colour', async () => {
    mockAll(PREV_CLOSE - 25, bars())
    renderPage()

    const live = await screen.findByText('Live')
    const styled = live.closest('span') as HTMLElement
    expect(styled.style.color).not.toBe('var(--color-bull)')
    expect(styled.style.color).not.toBe('var(--color-bear)')
  })
})

import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import * as signalsApiModule from '@/lib/api/signals'
import { ScanScope } from '@/components/ui/ScanScope'

/**
 * V1 — the scan-scope footer under an empty signal list.
 *
 * The defect it exists for: during the 2026-09-07 universe outage the signal list read
 * "Nothing meets the confluence gate right now" while the scan was covering a collapsed
 * universe. Those two situations rendered identically, for days.
 */

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper',
  allow_offmarket_entry: false, profit_lock_enabled: false,
  created_at: '', updated_at: '',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: 'test-token', user: mockUser })
})

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

function makeFunnel(
  overrides: Partial<signalsApiModule.FunnelOut> = {},
): signalsApiModule.FunnelOut {
  return {
    known: 3395,
    in_universe: 2291,
    priced_today: 2286,
    admitted_to_scoring: 2102,
    signals_live: 0,
    session: '2026-09-12',
    breadth_median: 2250,
    breadth_shortfall_pct: 0,
    assessed_available: false,
    ...overrides,
  }
}

describe('ScanScope', () => {
  it('states every measured rung of the scan', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(makeFunnel())
    wrap(<ScanScope />)
    await waitFor(() => expect(screen.getByText('3,395')).toBeInTheDocument())
    expect(screen.getByText('2,291')).toBeInTheDocument()
    expect(screen.getByText('2,286')).toBeInTheDocument()
    expect(screen.getByText('in universe')).toBeInTheDocument()
    expect(screen.getByText(/priced on/i)).toBeInTheDocument()
  })

  it('reports the scoring stage as unrecorded rather than zero', async () => {
    // ⭐ The A24 case. `assessed_available` is false today because the scorer does not
    // persist how many panels it evaluated. Rendering a 0 would ASSERT that nothing was
    // scored — a claim we cannot make — so the absence itself has to be readable.
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ assessed_available: false }),
    )
    wrap(<ScanScope />)
    await waitFor(() => expect(screen.getByText(/is not recorded/i)).toBeInTheDocument())
  })

  it('raises a coverage warning when today is far below the 30-session median', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ priced_today: 12, breadth_median: 2250, breadth_shortfall_pct: 99.5 }),
    )
    wrap(<ScanScope />)
    const warning = await screen.findByText(/below the/i)
    // ⛔ REGRESSION: this rounded to "100% below", which ASSERTS zero coverage — while the
    // rung two lines above printed 12 names priced. Truncation can only understate an
    // alarm; rounding overstated it past a claim boundary, in the same visual element.
    expect(warning).toHaveTextContent('99% below')
    expect(warning).not.toHaveTextContent('100%')
    // A24: the shortfall never renders without the median it is a shortfall against.
    expect(warning).toHaveTextContent('2,250-name')
    expect(warning).toHaveTextContent(/data problem/i)
  })

  it('states which session the priced count refers to', async () => {
    // ⛔ A24, and the failure mode the component exists for: before the day's ingest runs
    // the latest session IS the previous one, so an unlabelled "priced today" is wrong in
    // exactly the direction of the outage this is meant to catch. The backend's own field
    // docstring says "Without it the count means nothing" — and the first draft dropped it.
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ session: '2026-09-11' }),
    )
    wrap(<ScanScope />)
    await waitFor(() => expect(screen.getByText(/priced on 11 Sep/i)).toBeInTheDocument())
    expect(screen.queryByText(/priced today/i)).not.toBeInTheDocument()
  })

  it('says the count cannot be judged when there is no coverage reference', async () => {
    // The third branch. With a null median BOTH previous branches were skipped, so the
    // count rendered with no reference AND no statement that the reference was missing —
    // the same A24 rule this component applies correctly one element above.
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ breadth_median: null, breadth_shortfall_pct: null }),
    )
    wrap(<ScanScope />)
    await waitFor(() =>
      expect(screen.getByText(/no 30-session coverage reference/i)).toBeInTheDocument(),
    )
  })

  it('does not cry wolf on ordinary day-to-day variation', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ priced_today: 2100, breadth_shortfall_pct: 6.7 }),
    )
    wrap(<ScanScope />)
    await waitFor(() => expect(screen.getByText('2,100')).toBeInTheDocument())
    expect(screen.queryByText(/data problem/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Typical coverage/i)).toBeInTheDocument()
  })

  it('renders nothing at all when the funnel cannot be loaded', async () => {
    // Supporting context under a message that already stands alone — an error box here
    // would make the diagnostic aid look like the subject of the page.
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockRejectedValue(new Error('boom'))
    const { container } = wrap(<ScanScope />)
    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })
})

describe('ScanScope — attribution when the engine DID produce signals', () => {
  it('blames the filters, not the scan, when active signals exist', async () => {
    /*
      ⛔ THE REGRESSION. An earlier cut decided this in `DashboardPage` from the signals
      query response — whose key carries `direction`, `classification` and `minConfidence`,
      all SERVER-side. Setting min-confidence to 90 emptied the response, and the page then
      rendered "signals are generated nightly" plus the scan-scope funnel: blaming coverage
      for a slider. `signals_live` is unfiltered, so deciding from it needs no knowledge of
      any caller's filter state and cannot drift as filters are added.
    */
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ signals_live: 7 }),
    )
    wrap(<ScanScope />)
    await waitFor(() =>
      expect(screen.getByText(/filters on this view are hiding them/i)).toBeInTheDocument(),
    )
    expect(screen.getByText(/7 active signals/i)).toBeInTheDocument()
    // The scan-scope framing must NOT appear — it would answer a question nobody asked.
    expect(screen.queryByText(/in universe/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Typical coverage/i)).not.toBeInTheDocument()
  })

  it('agrees with itself in the singular', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ signals_live: 1 }),
    )
    wrap(<ScanScope />)
    await waitFor(() => expect(screen.getByText(/1 active signal /i)).toBeInTheDocument())
    expect(screen.getByText(/hiding it\./i)).toBeInTheDocument()
  })

  it('shows the scan scope only when the engine genuinely produced nothing', async () => {
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ signals_live: 0 }),
    )
    wrap(<ScanScope />)
    await waitFor(() => expect(screen.getByText('3,395')).toBeInTheDocument())
    expect(screen.queryByText(/filters on this view/i)).not.toBeInTheDocument()
  })
})

describe('ScanScope — the admission rung (round 5)', () => {
  it('shows the names that were never looked at, instead of crediting the gate', async () => {
    /*
      ⭐⭐ THE ROUND-5 FIX. With four rungs the entire drop from "priced" to "live signals"
      is forced onto the confluence gate, because the gate is the only mechanism a reader
      has left to explain it — so a scan that never looked at 184 names renders as "the
      engine looked at 2,286 and liked none of them". `signal_service` refuses a name with
      fewer than MIN_CANDLES_TO_SCORE daily candles BEFORE scoring, and that drop was
      invisible. Measured 2026-09-14: 184 of 2,286 (8%).
    */
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ priced_today: 2286, admitted_to_scoring: 2102, signals_live: 0 }),
    )
    wrap(<ScanScope />)
    await waitFor(() => expect(screen.getByText('2,102')).toBeInTheDocument())
    expect(screen.getByText(/enough history to score/i)).toBeInTheDocument()
  })

  it('still refuses to credit the residual drop to the gate', async () => {
    // Admission being computable does NOT make the scorer's panel count known.
    vi.spyOn(signalsApiModule.signalsApi, 'getFunnel').mockResolvedValue(
      makeFunnel({ admitted_to_scoring: 2102, signals_live: 0, assessed_available: false }),
    )
    wrap(<ScanScope />)
    await waitFor(() =>
      expect(screen.getByText(/cannot be credited to the confluence gate alone/i))
        .toBeInTheDocument(),
    )
  })
})

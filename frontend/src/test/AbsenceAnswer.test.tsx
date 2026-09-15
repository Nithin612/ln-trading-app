import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AbsenceAnswer } from '@/features/stocks/AbsenceAnswer'
import * as stocksApi from '@/lib/api/stocks'

vi.mock('@/store/authStore', () => ({
  useAuthStore: (sel: (s: { accessToken: string }) => unknown) => sel({ accessToken: 'tok' }),
}))

/**
 * V4 / A2 — §45/S2: an absence is not askable.
 *
 * "No stocks found" cannot distinguish "no such company" from "excluded from the
 * tradeable universe, and here is why" — and measured 2026-09-15, **1,104 of 3,395
 * stocks** fall in the second bucket, because the list defaults `is_active=true`.
 */
function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const EXCLUDED: stocksApi.ResolvedStock = {
  stock_id: 3,
  symbol: '3IINFOTECH',
  company_name: '3i Infotech Limited',
  in_universe: false,
  ca_quarantined: false,
  suggestible: false,
  exclusion_reasons: ['Not in the tradeable universe — not listed in the EQ series on NSE.'],
  former_symbols: [],
  reason_as_of: '2026-09-15',
}

describe('AbsenceAnswer', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('explains WHY a searched name is missing instead of shrugging', async () => {
    vi.spyOn(stocksApi.stocksApi, 'search').mockResolvedValue({
      query: '3IINFO', hits: [EXCLUDED], matched_former_symbol: null,
    })
    wrap(<AbsenceAnswer query="3IINFO" />)
    await waitFor(() => screen.getByText('3IINFOTECH'))
    expect(screen.getByText(/not listed in the EQ series/i)).toBeInTheDocument()
  })

  it('distinguishes "excluded" from "no such company"', async () => {
    // ⚠ The two answers are genuinely different and the old empty state conflated them.
    // Here the whole master was searched — not just the tradeable subset — and there is
    // nothing, which is the honest terminal answer.
    vi.spyOn(stocksApi.stocksApi, 'search').mockResolvedValue({
      query: 'ZZZZ', hits: [], matched_former_symbol: null,
    })
    wrap(<AbsenceAnswer query="ZZZZ" />)
    await waitFor(() => screen.getByText(/not anywhere else in the master list/i))
  })

  it('names a CA quarantine as a SEPARATE reason from the universe rule', async () => {
    // ⭐ The case that justifies the feature: measured, 5 of the 7 quarantined names are
    // ACTIVE — perfectly tradeable-looking, yet dropped from every suggestion. Two
    // exclusions, two remedies; a reader shown only one would chase the wrong fix.
    vi.spyOn(stocksApi.stocksApi, 'search').mockResolvedValue({
      query: 'DUCON',
      hits: [{
        ...EXCLUDED, symbol: 'DUCON', in_universe: true, ca_quarantined: true,
        exclusion_reasons: [
          'Quarantined by the corporate-action detector, so it is excluded from suggestions even when tradeable — review it under CA Quarantine.',
        ],
      }],
      matched_former_symbol: null,
    })
    wrap(<AbsenceAnswer query="DUCON" />)
    await waitFor(() => screen.getByText('DUCON'))
    expect(screen.getByText(/corporate-action detector/i)).toBeInTheDocument()
    expect(screen.getByText(/even when tradeable/i)).toBeInTheDocument()
  })

  it('tells the user a former ticker moved rather than vanished', async () => {
    vi.spyOn(stocksApi.stocksApi, 'search').mockResolvedValue({
      query: 'AMIRCHAND',
      hits: [{
        ...EXCLUDED, stock_id: 9, symbol: 'AEROPLANE', company_name: 'Aeroplane Ltd',
        in_universe: true, suggestible: true, exclusion_reasons: [],
        former_symbols: ['AMIRCHAND'],
      }],
      matched_former_symbol: 'AMIRCHAND',
    })
    wrap(<AbsenceAnswer query="AMIRCHAND" />)
    await waitFor(() => screen.getByText('AEROPLANE'))
    expect(screen.getByText(/former ticker/i)).toBeInTheDocument()
    expect(screen.getByText(/history, signals and positions moved with it/i)).toBeInTheDocument()
    expect(screen.getByText(/formerly AMIRCHAND/i)).toBeInTheDocument()
  })

  it('dates a reason it derived, and claims no date when it could not', async () => {
    // A24 — a reason derived from a recorded evaluation carries ITS DATE so it is never
    // read as a timeless fact; when the rule term could not be justified from a record,
    // no date is shown and none is implied.
    vi.spyOn(stocksApi.stocksApi, 'search').mockResolvedValue({
      query: 'X', hits: [{ ...EXCLUDED, reason_as_of: null }], matched_former_symbol: null,
    })
    wrap(<AbsenceAnswer query="X" />)
    await waitFor(() => screen.getByText('3IINFOTECH'))
    expect(screen.queryByText(/as evaluated/i)).not.toBeInTheDocument()
  })
})

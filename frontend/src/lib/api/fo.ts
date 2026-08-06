/**
 * F&O analytics client — Phase 4 backend (slices 4.1–4.3), Phase 5 UI.
 *
 * Money arrives as Decimal STRINGS and stays that way until a formatter in
 * lib/format.ts renders it; analytical values (IV, Greeks, PCR, POP) are
 * floats by design. `null` on a Greek means "not priced" — never 0.
 */

import { api } from './client'

export interface ChainLeg {
  strike: string
  option_type: 'CE' | 'PE'
  oi: number
  volume: number
  ltp: string | null
  // Present only when the chain was requested with greeks=true AND the quote
  // inverted. null = not priced (deep-ITM at intrinsic, no quote, no forward).
  iv: number | null
  delta: number | null
  gamma: number | null
  vega: number | null
  theta: number | null
}

export interface OptionChain {
  symbol: string
  expiry: string
  source: 'eod' | 'intraday'
  spot: string | null
  atm_strike: string | null
  legs: ChainLeg[]
  /** The chain's own trading day — what the Greeks were priced off. */
  as_of: string | null
  fut_price: string | null
  dte: number | null
}

export interface Pcr {
  pcr_oi: number | null
  pcr_volume: number | null
  total_ce_oi: number
  total_pe_oi: number
}

export interface Basis {
  fut_close: string
  underlying_close: string
  basis: string
  basis_pct: number
}

export interface VixRegime {
  current: string
  percentile: number
  band: 'low' | 'normal' | 'high'
  sample: number
}

export interface FoAnalytics {
  symbol: string
  expiry: string
  source: string
  spot: string | null
  atm_strike: string | null
  pcr: Pcr
  max_pain: string | null
  basis: Basis | null
  vix: VixRegime | null
}

export interface IvRank {
  symbol: string
  as_of: string
  current_iv: number
  rank: number
  percentile: number
  min_iv: number
  max_iv: number
  sample: number
}

export interface OptionLeg {
  action: 'sell' | 'buy'
  option_type: 'CE' | 'PE'
  strike: string
  premium: string
}

export interface ExitPlan {
  take_profit_credit: string
  stop_loss_amount: string
  time_stop_dte: number
}

export type SpreadStructure = 'bull_put' | 'bear_call' | 'iron_condor'

export interface SpreadCandidate {
  structure: SpreadStructure
  legs: OptionLeg[]
  net_credit: string
  max_profit: string
  max_loss: string
  width: string
  breakevens: string[]
  pop: number
  /** Report-only: risk-neutral expectancy is ~0 by construction. Never a gate. */
  expectancy: string
  margin_est: string
  return_on_margin: number
  short_delta: number
  dte: number
  expiry: string
  exit_plan: ExitPlan
  rationale: string
}

export interface SuggestionsResponse {
  symbol: string
  candidates: SpreadCandidate[]
}

export interface UnderlyingsResponse {
  as_of: string | null
  symbols: string[]
}

export interface ExpiryOption {
  expiry: string
  dte: number
}

export interface ExpiriesResponse {
  symbol: string
  as_of: string | null
  expiries: ExpiryOption[]
}

export const foApi = {
  getUnderlyings(token: string): Promise<UnderlyingsResponse> {
    return api.get<UnderlyingsResponse>('/fo/underlyings', token)
  },

  getExpiries(symbol: string, token: string): Promise<ExpiriesResponse> {
    return api.get<ExpiriesResponse>(`/fo/expiries?symbol=${encodeURIComponent(symbol)}`, token)
  },

  getChain(
    symbol: string,
    expiry: string,
    token: string,
    params: { source?: 'eod' | 'intraday'; strikes?: number; greeks?: boolean } = {},
  ): Promise<OptionChain> {
    const q = new URLSearchParams({ symbol, expiry })
    if (params.source) q.set('source', params.source)
    if (params.strikes != null) q.set('strikes', String(params.strikes))
    if (params.greeks) q.set('greeks', 'true')
    return api.get<OptionChain>(`/fo/chain?${q.toString()}`, token)
  },

  getAnalytics(
    symbol: string,
    expiry: string,
    token: string,
    params: { source?: 'eod' | 'intraday' } = {},
  ): Promise<FoAnalytics> {
    const q = new URLSearchParams({ symbol, expiry })
    if (params.source) q.set('source', params.source)
    return api.get<FoAnalytics>(`/fo/analytics?${q.toString()}`, token)
  },

  getIvRank(symbol: string, token: string): Promise<IvRank> {
    return api.get<IvRank>(`/fo/iv-rank?symbol=${encodeURIComponent(symbol)}`, token)
  },

  getSuggestions(symbol: string, token: string): Promise<SuggestionsResponse> {
    return api.get<SuggestionsResponse>(
      `/fo/suggestions?symbol=${encodeURIComponent(symbol)}`,
      token,
    )
  },
}

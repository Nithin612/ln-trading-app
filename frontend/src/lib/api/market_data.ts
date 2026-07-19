import { api } from './client'

export interface OhlcvBar {
  time: string
  open: string
  high: string
  low: string
  close: string
  volume: number
}

export interface OhlcvResponse {
  stock_id: number
  timeframe: string
  bars: OhlcvBar[]
}

export interface FiiDiiRow {
  trade_date: string
  investor_type: 'FII' | 'DII'
  segment: 'cash' | 'futures' | 'options'
  buy_value_cr: string
  sell_value_cr: string
  net_value_cr: string
}

export interface FiiDiiResponse {
  rows: FiiDiiRow[]
  total: number
}

export interface BulkBlockDeal {
  id: number
  trade_date: string
  stock_id: number
  symbol: string | null
  deal_type: 'bulk' | 'block'
  client_name: string | null
  transaction: 'BUY' | 'SELL'
  quantity: number
  price: string
  value_cr: string
  source: string
}

export interface BulkBlockDealsResponse {
  items: BulkBlockDeal[]
  total: number
}

export const marketDataApi = {
  getOhlcv(
    stockId: number,
    params: { fromDate?: string; toDate?: string; limit?: number },
    token: string,
  ): Promise<OhlcvResponse> {
    const q = new URLSearchParams()
    if (params.fromDate) q.set('from_date', params.fromDate)
    if (params.toDate) q.set('to_date', params.toDate)
    if (params.limit) q.set('limit', String(params.limit))
    const qs = q.toString() ? `?${q.toString()}` : ''
    return api.get<OhlcvResponse>(`/stocks/${stockId}/ohlcv${qs}`, token)
  },

  getFiiDii(
    params: {
      fromDate?: string
      toDate?: string
      investorType?: 'FII' | 'DII'
      segment?: 'cash' | 'futures' | 'options'
      limit?: number
    },
    token: string,
  ): Promise<FiiDiiResponse> {
    const q = new URLSearchParams()
    if (params.fromDate) q.set('from_date', params.fromDate)
    if (params.toDate) q.set('to_date', params.toDate)
    if (params.investorType) q.set('investor_type', params.investorType)
    if (params.segment) q.set('segment', params.segment)
    if (params.limit) q.set('limit', String(params.limit))
    return api.get<FiiDiiResponse>(`/market/fii-dii?${q.toString()}`, token)
  },

  getBulkBlockDeals(
    params: {
      fromDate?: string
      toDate?: string
      stockId?: number
      dealType?: 'bulk' | 'block'
      limit?: number
    },
    token: string,
  ): Promise<BulkBlockDealsResponse> {
    const q = new URLSearchParams()
    if (params.fromDate) q.set('from_date', params.fromDate)
    if (params.toDate) q.set('to_date', params.toDate)
    if (params.stockId) q.set('stock_id', String(params.stockId))
    if (params.dealType) q.set('deal_type', params.dealType)
    if (params.limit) q.set('limit', String(params.limit))
    return api.get<BulkBlockDealsResponse>(`/market/bulk-block-deals?${q.toString()}`, token)
  },
}

// ── Provisional leaderboards (Phase 3, slice 3.5) ──────────────────────────
// Derived observability view: provisional-labelled end-to-end, never
// tradeable state. confidence null on an active-signal row = that
// signal's setup no longer passes its gate right now.

export interface ProvisionalRow {
  provisional: true
  stock_id: number
  symbol: string
  profile_key: string | null
  style: string
  tf: string
  confidence: number | null
  direction: 'BUY' | 'SELL' | null
  // true = passes gate · false = real below-gate verdict · null = no data
  gate: boolean | null
  sources: string[]
  signal_id?: string | null
}

export interface ProvisionalLeaderboard {
  provisional: true
  style: string
  as_of: string | null
  rows: ProvisionalRow[]
}

export const provisionalApi = {
  getLeaderboard(style: string, token: string): Promise<ProvisionalLeaderboard> {
    return api.get<ProvisionalLeaderboard>(`/market/provisional/${style}`, token)
  },
}

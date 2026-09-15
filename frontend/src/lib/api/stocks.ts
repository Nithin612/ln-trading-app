import { api } from './client'

export interface Stock {
  id: number
  symbol: string
  exchange: string
  isin: string | null
  company_name: string
  sector: string | null
  industry: string | null
  market_cap_cr: string | null
  lot_size: number
  tick_size: string
  is_fno: boolean
  is_nifty50: boolean
  is_banknifty: boolean
  is_finnifty: boolean
  is_active: boolean
  listed_on: string | null
  created_at: string
  updated_at: string
}

export interface StockListResponse {
  items: Stock[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface StockListParams {
  q?: string
  sector?: string
  is_nifty50?: boolean
  is_banknifty?: boolean
  is_finnifty?: boolean
  is_fno?: boolean
  is_active?: boolean
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface FilterSpec {
  field: string
  op: string
  value: unknown
}

export interface ScreenerRequest {
  filters: FilterSpec[]
  logic: 'AND' | 'OR'
  sort_by: string
  sort_dir: 'asc' | 'desc'
  limit: number
  offset: number
}

export interface ScreenerResult {
  items: Stock[]
  total: number
  limit: number
  offset: number
}

export interface ScreenerFieldInfo {
  field: string
  field_type: string
  allowed_ops: string[]
  available: boolean
  note: string
  /** Active stocks with a non-null value for this field; null when coverage
   *  isn't meaningful. Far below total_active_stocks = the filter will match
   *  almost nothing regardless of the market. */
  populated: number | null
}

export interface ScreenerFieldsResponse {
  total_active_stocks: number
  fields: ScreenerFieldInfo[]
}

export interface SavedScreen {
  id: number
  user_id: number
  name: string
  filter_spec: ScreenerRequest
  created_at: string
  updated_at: string
}

function buildQuery(params: Record<string, unknown>): string {
  const parts: string[] = []
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    }
  }
  return parts.length ? `?${parts.join('&')}` : ''
}

/** A search hit that explains why it is, or is not, usable. */
export interface ResolvedStock {
  stock_id: number
  symbol: string
  company_name: string
  /** Admitted by the universe rule — scannable and orderable at all. */
  in_universe: boolean
  /**
   * ⚠ INDEPENDENT of `in_universe`: a quarantined name can be perfectly tradeable and
   * still absent from every suggestion, which no other surface can explain.
   */
  ca_quarantined: boolean
  /** True only when BOTH hold — what the suggestion universe actually requires. */
  suggestible: boolean
  exclusion_reasons: string[]
  /** Tickers this row used to trade under, newest first. */
  former_symbols: string[]
  /** `null` = the rule term could not be justified from a record, so none is claimed. */
  reason_as_of: string | null
}

export interface StockSearchResponse {
  query: string
  hits: ResolvedStock[]
  /** Set when the query matched a FORMER ticker — "AEROPLANE (formerly AMIRCHAND)". */
  matched_former_symbol: string | null
}

export const stocksApi = {
  list: (params: StockListParams, token: string) =>
    api.get<StockListResponse>(
      `/stocks${buildQuery(params as Record<string, unknown>)}`,
      token,
    ),

  get: (id: number, token: string) =>
    api.get<Stock>(`/stocks/${id}`, token),

  /**
   * V4 — search that answers ABSENCE. Unlike `list`, it does NOT filter by `is_active`,
   * so a name the universe rule excluded comes back WITH its reason instead of returning
   * nothing. It also resolves former tickers after a rename.
   */
  search: (q: string, token: string) =>
    api.get<StockSearchResponse>(
      `/stocks/search?q=${encodeURIComponent(q)}`,
      token,
    ),

  screenerFields: (token: string) =>
    api.get<ScreenerFieldsResponse>('/screener/fields', token),

  screenerRun: (req: ScreenerRequest, token: string) =>
    api.post<ScreenerResult>('/screener/run', req, token),

  savedList: (token: string) =>
    api.get<SavedScreen[]>('/screener/saved', token),

  savedCreate: (name: string, filterSpec: ScreenerRequest, token: string) =>
    api.post<SavedScreen>('/screener/saved', { name, filter_spec: filterSpec }, token),

  savedDelete: (id: number, token: string) =>
    api.delete<void>(`/screener/saved/${id}`, token),
}

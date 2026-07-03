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

export const stocksApi = {
  list: (params: StockListParams, token: string) =>
    api.get<StockListResponse>(
      `/stocks${buildQuery(params as Record<string, unknown>)}`,
      token,
    ),

  get: (id: number, token: string) =>
    api.get<Stock>(`/stocks/${id}`, token),

  screenerRun: (req: ScreenerRequest, token: string) =>
    api.post<ScreenerResult>('/screener/run', req, token),

  savedList: (token: string) =>
    api.get<SavedScreen[]>('/screener/saved', token),

  savedCreate: (name: string, filterSpec: ScreenerRequest, token: string) =>
    api.post<SavedScreen>('/screener/saved', { name, filter_spec: filterSpec }, token),

  savedDelete: (id: number, token: string) =>
    api.delete<void>(`/screener/saved/${id}`, token),
}

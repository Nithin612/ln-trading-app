import { api } from './client'

export interface FilingOut {
  id: number
  stock_id: number
  symbol: string
  filing_type: string
  headline: string
  body: string | null
  filing_date: string
  filing_time: string
  source: string
  source_url: string | null
  sentiment_score: string | null
  is_high_impact: boolean
  created_at: string
}

export interface FilingListResponse {
  total: number
  filings: FilingOut[]
}

export interface EventGuardStatus {
  stock_id: number
  symbol: string
  suppressed: boolean
  reason: string | null
  suppressed_until: string | null
}

export const filingsApi = {
  getRecent(
    params: { hours?: number; filingType?: string; limit?: number; offset?: number },
    token: string,
  ): Promise<FilingListResponse> {
    const q = new URLSearchParams()
    if (params.hours != null) q.set('hours', String(params.hours))
    if (params.filingType) q.set('filing_type', params.filingType)
    if (params.limit != null) q.set('limit', String(params.limit))
    if (params.offset != null) q.set('offset', String(params.offset))
    const qs = q.toString() ? `?${q.toString()}` : ''
    return api.get<FilingListResponse>(`/filings/recent${qs}`, token)
  },

  getByStock(stockId: number, params: { days?: number; limit?: number }, token: string): Promise<FilingListResponse> {
    const q = new URLSearchParams()
    if (params.days != null) q.set('days', String(params.days))
    if (params.limit != null) q.set('limit', String(params.limit))
    const qs = q.toString() ? `?${q.toString()}` : ''
    return api.get<FilingListResponse>(`/filings/by-stock/${stockId}${qs}`, token)
  },

  getGuard(stockId: number, token: string): Promise<EventGuardStatus> {
    return api.get<EventGuardStatus>(`/filings/guard/${stockId}`, token)
  },
}

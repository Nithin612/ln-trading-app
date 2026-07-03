import { api } from './client'

export interface FactorScore {
  weight: number
  score: number
  explanation: string
}

export interface SignalOut {
  id: string
  stock_id: number
  symbol: string
  direction: 'BUY' | 'SELL'
  classification: string
  timeframe: string
  entry_price: string
  stop_loss: string
  take_profit: string
  suggested_qty: number
  confidence_pct: number
  factor_scores: Record<string, FactorScore>
  triggering_patterns: string[] | null
  triggering_indicators: string[] | null
  headline: string
  status: string
  validity_until: string
  created_at: string
}

export interface SignalListResponse {
  total: number
  signals: SignalOut[]
}

export const signalsApi = {
  getActive(
    params: {
      direction?: string
      classification?: string
      minConfidence?: number
      limit?: number
      offset?: number
    },
    token: string,
  ): Promise<SignalListResponse> {
    const q = new URLSearchParams()
    if (params.direction) q.set('direction', params.direction)
    if (params.classification) q.set('classification', params.classification)
    if (params.minConfidence != null) q.set('min_confidence', String(params.minConfidence))
    if (params.limit != null) q.set('limit', String(params.limit))
    if (params.offset != null) q.set('offset', String(params.offset))
    const qs = q.toString() ? `?${q.toString()}` : ''
    return api.get<SignalListResponse>(`/signals/active${qs}`, token)
  },

  getById(id: string, token: string): Promise<SignalOut> {
    return api.get<SignalOut>(`/signals/${id}`, token)
  },
}

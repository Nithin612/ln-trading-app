import { api, ApiError } from './client'

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

// ── Signal outcomes (Phase 3, slice 3.6) ────────────────────────────────────
// Tick-level first-touch record — observability only, never tradeable state.

export interface SignalOutcome {
  signal_id: string
  stock_id: number
  direction: string
  classification: string
  timeframe: string
  validity_until: string
  status:
    | 'open'
    | 'entry_touched'
    | 'tp_first'
    | 'sl_first'
    | 'expired_untouched'
    | 'expired_open'
  entry_touched_at: string | null
  entry_touch_price: string | null
  sl_touched_at: string | null
  sl_touch_price: string | null
  tp_touched_at: string | null
  tp_touch_price: string | null
  resolved_at: string | null
}

export const outcomeApi = {
  /** null = no outcome recorded yet (the row is written lazily). */
  async getOutcome(signalId: string, token: string): Promise<SignalOutcome | null> {
    try {
      return await api.get<SignalOutcome>(`/signals/${signalId}/outcome`, token)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null
      throw err
    }
  },
}

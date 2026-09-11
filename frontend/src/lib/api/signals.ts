import { api, ApiError } from './client'

export interface FactorScore {
  weight: number
  score: number
  explanation: string
}

// U10/U15/U17 — the confluence arithmetic reconstructed server-side for the detail card
// (app/signals/confidence_explain). Detail endpoint only; null on list rows and when the
// stored factor payload is malformed.
export interface FactorContribution {
  name: string
  weight: number
  score: number
  contribution: number // weight × score (signed: BUY positive, SELL negative)
  explanation: string
}

export interface FactorAbstention {
  name: string
  weight: number
  explanation: string
}

export interface ConfidenceBreakdown {
  numerator: number // Σ weight·score over ALL factors
  denominator: number // Σ weight over scoring factors (score ≠ 0)
  normalized: number // numerator / denominator ∈ [-1, 1]
  confidence_pct: number
  direction: string
  scoring: FactorContribution[] // dominant contribution first
  abstained: FactorAbstention[] // present at evaluation, excluded from the divisor
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
  sources_count: number   // how many active signals (base + profiles) collapsed here
  near_expiry: boolean     // ≥80% of the validity window elapsed (stale / little runway)
  days_valid_remaining: number  // calendar days until validity_until (server-computed)
  regime_er: number | null      // daily Kaufman efficiency ratio (0-1); null = insufficient bars
  choppy: boolean               // regime_er below the choppy threshold (~0.30)
  // Order-eligibility preview (2026-09-02). The order path runs seven overlays and
  // 409s on the first ACTIVE rejection; this list used to run none, so 41 of 204 rows
  // showed a Buy button that could only fail. `block_reason` is verbatim the 409 detail.
  blocked: boolean
  blocked_by: string | null     // stable gate slug ("regime" | "entry_quality")
  block_reason: string | null   // the exact message the order path would reject with
  unassessed: string[]          // ACTIVE gates not judged on this path — UNKNOWN, not clear
  confidence_breakdown?: ConfidenceBreakdown | null // detail endpoint only (U10/U15/U17)
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

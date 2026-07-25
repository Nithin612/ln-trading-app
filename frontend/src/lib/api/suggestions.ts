import { api } from './client'

export interface FactorScore {
  weight: number
  score: number
  explanation: string
}

export interface SuggestionOut {
  id: string
  symbol: string
  direction: 'BUY' | 'SELL'
  classification: string
  timeframe: string
  entry_price: string
  stop_loss: string
  take_profit: string
  suggested_qty: number
  confidence_pct: number
  headline: string
  factor_scores: Record<string, FactorScore>
  setup_trigger: Record<string, unknown> | null
  volatility_reduced: boolean | null
  profile_key: string
  profile_name: string
  profile_version: number
  style: string
  validity_until: string
  created_at: string
}

export interface SuggestionListResponse {
  style: string
  total: number
  suggestions: SuggestionOut[]
}

export const PROFILE_STYLES = ['intraday', 'swing', 'fno', 'investment'] as const
export type ProfileStyle = (typeof PROFILE_STYLES)[number]

export const suggestionsApi = {
  getByStyle(
    style: string,
    token: string,
    params: { profile?: string; minConfidence?: number } = {},
  ): Promise<SuggestionListResponse> {
    const q = new URLSearchParams()
    if (params.profile) q.set('profile', params.profile)
    if (params.minConfidence != null) q.set('min_confidence', String(params.minConfidence))
    const qs = q.toString() ? `?${q.toString()}` : ''
    return api.get<SuggestionListResponse>(`/suggestions/${style}${qs}`, token)
  },
}

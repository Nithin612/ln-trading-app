import { api } from './client'

export interface OutcomeStyleStats {
  style: string
  total: number
  entered: number
  wins: number
  losses: number
  no_entry: number
  timed_out: number
  pending: number
  sample: number
  hit_rate: number | null
  entry_rate: number | null
  avg_return_pct: number | null
}

export interface OutcomeAnalyticsResponse {
  epoch: string
  total_outcomes: number
  styles: OutcomeStyleStats[]
}

// U1 — the gate / hypothesis register (H4) as data.
export interface GateHypothesis {
  key: string
  name: string
  status: 'active' | 'shadow' | 'reverted' | 'decided_no' | 'research'
  prediction: string
  bar: string
  stands_at: string
  verdict: string
  counts_as_trial: boolean
  review_due: string | null
}

export interface GateRegisterResponse {
  as_of: string
  trials_attempted: number // observed — a LOWER BOUND on N (variants not yet counted)
  assumed_trials: number // DEFAULT_TRIALS used in the deflation bar
  counts: Record<string, number> // status → count
  due_for_review: string[]
  hypotheses: GateHypothesis[]
}

export const analyticsApi = {
  getOutcomes(token: string): Promise<OutcomeAnalyticsResponse> {
    return api.get<OutcomeAnalyticsResponse>('/analytics/outcomes', token)
  },
  getGateRegister(token: string): Promise<GateRegisterResponse> {
    return api.get<GateRegisterResponse>('/analytics/gate-register', token)
  },
}

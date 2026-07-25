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

export const analyticsApi = {
  getOutcomes(token: string): Promise<OutcomeAnalyticsResponse> {
    return api.get<OutcomeAnalyticsResponse>('/analytics/outcomes', token)
  },
}

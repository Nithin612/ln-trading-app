import { api } from './client'

export interface MonthSeasonality {
  month: number // 1..12
  n: number // yearly observations for this month
  positive: number
  pct_positive: number | null // null when n === 0
  avg_return_pct: number | null
  median_return_pct: number | null
  best_return_pct: number | null
  worst_return_pct: number | null
  avg_positive_pct: number | null
  avg_negative_pct: number | null
}

export interface Seasonality {
  stock_id: number
  total_observations: number
  years_covered: number
  first_month: string | null // ISO date (first of month)
  last_month: string | null
  months: MonthSeasonality[] // always 12, ordered month 1..12
}

export const seasonalityApi = {
  get: (stockId: number, token: string) =>
    api.get<Seasonality>(`/seasonality/${stockId}`, token),
}

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
  has_cohort: boolean // U20 — a would-block cohort drill-down exists for this gate
}

export interface GateRegisterResponse {
  as_of: string
  trials_attempted: number // observed — a LOWER BOUND on N (variants not yet counted)
  assumed_trials: number // DEFAULT_TRIALS used in the deflation bar
  counts: Record<string, number> // status → count
  due_for_review: string[]
  hypotheses: GateHypothesis[]
}

// U11 — NIFTY buy-and-hold aligned to a backtest run's equity curve.
export interface BenchmarkCurveResponse {
  run_id: number
  symbol: string
  available: boolean
  reason: string | null // why unavailable (e.g. no index data for the window)
  points: number[] // benchmark indexed to 100, PARALLEL to the run's equity_curve; [] if unavailable
  benchmark_return_pct: number | null
  strategy_return_pct: number | null
}

// U20 — the trades a gate would block, as chartable data (the "contact sheet" cohort).
export interface CohortBar {
  t: string // ISO date
  o: number
  h: number
  low: number
  c: number
}

export interface CohortTrade {
  signal_id: string
  symbol: string
  direction: string
  entry: number
  stop_loss: number
  take_profit: number
  confidence_pct: number
  reason: string
  outcome_status: string | null
  realized_pnl_pct: number | null
  realized_r: number | null
  entry_date: string
  bars: CohortBar[]
}

export interface GateCohortResponse {
  gate_key: string
  gate: string
  gate_status: string | null
  supported: boolean
  reason: string | null
  scanned: number
  cohort_count: number
  cohort_realized_r: number | null
  cohort_realized_pnl_pct: number | null
  trades: CohortTrade[]
}

export const analyticsApi = {
  getOutcomes(token: string): Promise<OutcomeAnalyticsResponse> {
    return api.get<OutcomeAnalyticsResponse>('/analytics/outcomes', token)
  },
  getGateRegister(token: string): Promise<GateRegisterResponse> {
    return api.get<GateRegisterResponse>('/analytics/gate-register', token)
  },
  getBenchmarkCurve(runId: number, token: string): Promise<BenchmarkCurveResponse> {
    return api.get<BenchmarkCurveResponse>(`/analytics/benchmark-curve?run_id=${runId}`, token)
  },
  getGateCohort(gateKey: string, token: string): Promise<GateCohortResponse> {
    return api.get<GateCohortResponse>(`/analytics/cohort/${encodeURIComponent(gateKey)}`, token)
  },
}

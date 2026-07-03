import { api } from './client'

export interface RunBacktestRequest {
  name: string
  description?: string
  timeframe: '1d' | '1h' | '15m' | '5m' | '1m'
  universe: string
  period_start: string   // ISO datetime
  period_end: string
  capital: string        // Decimal as string
  risk_pct: string
  min_confidence: number
  weight_multipliers: Record<string, number>
  symbols?: string[]
}

export interface PresetScanRequest {
  timeframe: '1d' | '1h' | '15m' | '5m' | '1m'
  universe: string
  period_start: string
  period_end: string
  capital: string
  risk_pct: string
  min_confidence: number
  symbols?: string[]
}

export interface TradeRecordOut {
  stock: string
  direction: string
  classification: string
  confidence_pct: number
  entry_date: string
  entry_price: number
  stop_loss: number
  take_profit: number
  qty: number
  exit_date: string | null
  exit_price: number | null
  pnl_pct: number | null
  hit_target: boolean
  hit_sl: boolean
}

export interface StrategyRunOut {
  id: number
  name: string
  description: string | null
  timeframe: string
  universe: string
  period_start: string
  period_end: string
  status: string
  factor_weights: Record<string, number>
  capital: string | null
  risk_pct: string | null
  min_confidence: number | null
  total_trades: number
  winning_trades: number
  losing_trades: number | null
  win_rate_pct: string | null
  total_pnl_pct: string | null
  avg_pnl_pct: string | null
  avg_rr: string | null
  sharpe: string | null
  sortino: string | null
  max_drawdown_pct: string | null
  avg_holding_days: string | null
  ranking: number | null
  equity_curve: number[] | null
  trades_json: TradeRecordOut[] | null
  created_at: string
}

export interface StrategyRunListResponse {
  total: number
  runs: StrategyRunOut[]
}

export interface PresetScanEntry {
  preset_name: string
  weight_multipliers: Record<string, number>
  total_trades: number
  win_rate_pct: number
  sharpe: number
  sortino: number
  max_drawdown_pct: number
  avg_rr: number
  avg_holding_days: number
  equity_curve: number[]
}

export interface PresetScanResponse {
  entries: PresetScanEntry[]
}

export const strategyApi = {
  createRun: (req: RunBacktestRequest, token: string): Promise<StrategyRunOut> =>
    api.post<StrategyRunOut>('/strategy/runs', req, token),

  listRuns: (
    token: string,
    sortBy = 'sharpe',
    limit = 50,
    offset = 0,
  ): Promise<StrategyRunListResponse> =>
    api.get<StrategyRunListResponse>(
      `/strategy/runs?sort_by=${sortBy}&limit=${limit}&offset=${offset}`,
      token,
    ),

  getRun: (id: number, token: string): Promise<StrategyRunOut> =>
    api.get<StrategyRunOut>(`/strategy/runs/${id}`, token),

  deleteRun: (id: number, token: string): Promise<void> =>
    api.delete<void>(`/strategy/runs/${id}`, token),

  presetScan: (req: PresetScanRequest, token: string): Promise<PresetScanResponse> =>
    api.post<PresetScanResponse>('/strategy/preset-scan', req, token),
}

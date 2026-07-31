import { api } from './client'

export interface HealthReason {
  code: 'thesis_break' | 'trend_dead' | 'rr_inverted' | 'deep_mae' | 'stale'
  severity: 'watch' | 'cut'
  detail: string
}

export interface PositionHealth {
  verdict: 'hold' | 'watch' | 'cut'
  reasons: HealthReason[]
  drawdown_r: number | null
  rr_remaining: number | null
  regime_er: number | null
}

export interface PositionOut {
  id: string
  user_id: number
  stock_id: number
  symbol: string
  mode: string
  side: 'LONG' | 'SHORT'
  quantity: number
  avg_entry_price: string
  current_sl: string | null
  current_tp: string | null
  trail_state: 'none' | 'breakeven' | 'trailing_1' | 'trailing_2'
  unrealized_pnl: string | null
  realized_pnl: string
  charges: string | null
  exit_price: string | null
  exit_reason: 'sl_hit' | 'tp_hit' | 'manual' | null
  current_price: string | null
  peak_price: string | null
  peak_pnl: string | null
  health: PositionHealth | null
  opened_at: string
  closed_at: string | null
  signal_id: string | null
}

export interface PositionListResponse {
  total: number
  positions: PositionOut[]
}

export interface OrderOut {
  id: string
  user_id: number
  signal_id: string | null
  stock_id: number
  symbol: string
  mode: string
  side: 'BUY' | 'SELL'
  order_type: string
  quantity: number
  price: string | null
  status: string
  placed_at: string
  filled_at: string | null
  filled_price: string | null
  filled_qty: number | null
  error_message: string | null
}

export interface DailyPnlOut {
  trade_date: string
  realized_pnl: string
  total_unrealized_pnl: string
  open_count: number
  closed_count: number
  circuit_breaker_triggered: boolean
  daily_loss_limit_inr: string
  trades_taken_today: number
  max_trades_per_day: number
}

export interface PaperDayRow {
  date: string
  realized_pnl: string
  charges: string
  trades: number
  profitable: boolean
  cumulative_pnl: string
}

export interface PaperRecordOut {
  days: PaperDayRow[]
  total_days_traded: number
  profitable_days: number
  losing_days: number
  current_streak: number
  best_streak: number
  total_realized_pnl: string
  total_charges: string
  total_trades: number
  win_rate_pct: string
  target_days: number
  start_date: string | null
  last_date: string | null
}

// Profit-lock shadow comparator (read-only evidence — controls no orders).
export interface ShadowPolicy {
  policy: string
  exit_price: string | null
  exit_time: string | null
  exit_net: string | null
  still_open: boolean
  capture_pct: number | null
}

export interface ShadowComparison {
  position_id: string
  symbol: string
  side: 'LONG' | 'SHORT'
  quantity: number
  entry: string
  original_sl: string
  classification: string
  bars: number
  peak_price: string | null
  peak_gross: string | null
  actual_exit_price: string | null
  actual_net: string | null
  actual_capture_pct: number | null
  actual_exit_off_tape: boolean
  policies: ShadowPolicy[]
  note: string | null
}

export interface ShadowCompareResponse {
  total: number
  comparisons: ShadowComparison[]
}

export const tradingApi = {
  placeOrder(
    params: { signal_id: string; side?: string; quantity?: number },
    token: string,
  ): Promise<OrderOut> {
    return api.post<OrderOut>('/trading/orders', params, token)
  },

  getOpenPositions(token: string): Promise<PositionListResponse> {
    return api.get<PositionListResponse>('/trading/positions', token)
  },

  closePosition(
    positionId: string,
    exitPrice: string | undefined,
    token: string,
  ): Promise<PositionOut> {
    return api.post<PositionOut>(
      `/trading/positions/${positionId}/close`,
      { exit_price: exitPrice ?? null },
      token,
    )
  },

  updateSl(positionId: string, newSl: string, token: string): Promise<PositionOut> {
    return api.post<PositionOut>(
      `/trading/positions/${positionId}/update-sl`,
      { new_sl: newSl },
      token,
    )
  },

  getHistory(
    params: { limit?: number; offset?: number },
    token: string,
  ): Promise<PositionListResponse> {
    const q = new URLSearchParams()
    if (params.limit != null) q.set('limit', String(params.limit))
    if (params.offset != null) q.set('offset', String(params.offset))
    const qs = q.toString() ? `?${q.toString()}` : ''
    return api.get<PositionListResponse>(`/trading/history${qs}`, token)
  },

  getDailyPnl(token: string): Promise<DailyPnlOut> {
    return api.get<DailyPnlOut>('/trading/daily-pnl', token)
  },

  getShadowCompare(
    params: { limit?: number },
    token: string,
  ): Promise<ShadowCompareResponse> {
    const qs = params.limit != null ? `?limit=${params.limit}` : ''
    return api.get<ShadowCompareResponse>(`/trading/shadow-compare${qs}`, token)
  },

  getPaperRecord(token: string, targetDays = 30): Promise<PaperRecordOut> {
    return api.get<PaperRecordOut>(`/trading/paper-record?target_days=${targetDays}`, token)
  },
}

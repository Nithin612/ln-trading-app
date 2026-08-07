import { api } from './client'

export interface UserOut {
  id: number
  email: string
  full_name: string
  role: string
  capital_inr: string
  risk_per_trade_pct: string
  daily_loss_limit_pct: string
  max_trades_per_day: number
  allow_offmarket_entry: boolean
  profit_lock_enabled: boolean
  is_active: boolean
  trading_mode: string
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserOut
}

export interface AccessTokenResponse {
  access_token: string
  token_type: string
}

export const authApi = {
  // Anonymous by construction: login has no token yet, and refresh authenticates
  // with the httpOnly cookie — sending the expired bearer it is replacing would
  // be misleading at best.
  login: (email: string, password: string) =>
    api.anon.post<TokenResponse>('/auth/login', { email, password }),

  refresh: () => api.anon.post<AccessTokenResponse>('/auth/refresh', {}),

  logout: (token: string) => api.post<{ message: string }>('/auth/logout', {}, token),

  me: (token: string) => api.get<UserOut>('/auth/me', token),
}

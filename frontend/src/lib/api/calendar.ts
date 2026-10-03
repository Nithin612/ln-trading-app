import { api } from './client'

/** `GET /calendar/constraints` (A4) — what is legal NOW, from the backend's owners. */
export interface SessionNow {
  as_of: string
  today_ist: string // YYYY-MM-DD
  is_trading_day: boolean
  is_regular_session: boolean
  open_ist: string | null // HH:MM:SS
  close_ist: string | null
  in_session: boolean
  next_open: string | null // ISO UTC
  session_close: string | null // ISO UTC
}

export interface ValidityRule {
  classification: string
  rule: string
  valid_until: string
}

export interface DataLimit {
  timeframe: string
  earliest: string | null
  latest: string | null
}

export interface Constraints {
  session: SessionNow
  validity: ValidityRule[]
  offmarket_entry_allowed: boolean
  offmarket_rule: string
  data_limits: DataLimit[]
}

export const calendarApi = {
  /** The pill passes `dataLimits: false` — it needs only the session, not a scan per table. */
  constraints: (token: string, opts: { dataLimits?: boolean } = {}) =>
    api.get<Constraints>(
      `/calendar/constraints?data_limits=${opts.dataLimits === false ? 'false' : 'true'}`, token),
}

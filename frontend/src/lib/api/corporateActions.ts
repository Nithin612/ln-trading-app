import { api } from './client'

/** One stock the CA detector is holding out of every suggestion universe. */
export interface CaQuarantineOut {
  stock_id: number
  symbol: string
  /** When the detector flagged it (ISO, UTC). */
  flagged_at: string
  /** The detector's own gap description, e.g. "open 2.26 vs prev close 3.08 (-26.6%)". */
  reason: string | null
  /**
   * ⚠ Quarantined names are listed whether or not they are currently tradeable: the flag
   * and the universe rule are independent, and a reviewer should see the whole queue
   * rather than today's tradeable subset.
   */
  is_active: boolean
}

/** One entry in the append-only quarantine log — a machine flag, or a human release. */
export interface CaFlagEventOut {
  id: number
  stock_id: number
  event: 'flagged' | 'cleared'
  at: string
  reason: string
  /** NULL for a machine flag; the admin who reviewed it on a clear. */
  actor_user_id: number | null
}

export const corporateActionsApi = {
  /** The review queue, oldest first. */
  getQuarantine: (token: string) =>
    api.get<CaQuarantineOut[]>('/corporate-actions/quarantine', token),

  /** Every flag and clear for one stock, oldest first. */
  getQuarantineHistory: (stockId: number, token: string) =>
    api.get<CaFlagEventOut[]>(`/corporate-actions/quarantine/${stockId}/history`, token),

  /**
   * Release a stock from quarantine. `reason` is required and must be substantive —
   * the backend rejects anything under 10 characters with a 422.
   */
  clearQuarantine: (stockId: number, reason: string, token: string) =>
    api.post<CaQuarantineOut>(
      `/corporate-actions/quarantine/${stockId}/clear`,
      { reason },
      token,
    ),
}

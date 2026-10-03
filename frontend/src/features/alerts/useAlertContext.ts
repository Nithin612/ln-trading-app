/**
 * useAlertContext — resolves the two lookups every alert view needs
 * (Phase 5 slice 5.4; extracted from AlertBell so the bell and the Live
 * Signals page share one implementation).
 *
 * Alert frames are deliberately thin: the Redis stream carries a `sid` and an
 * optional `signal_id`, not a symbol or a trade plan.
 *
 * A stock's symbol IS immutable intraday, so it keeps `staleTime: Infinity`.
 * A signal's *plan* never repaints either — but since 2026-09-02 the signal payload
 * also carries an order-eligibility verdict (`blocked`/`block_reason`) computed from
 * LIVE settings, a live ATR and the live price, so the row is no longer immutable and
 * `staleTime: Infinity` would pin a stale ⊘ Blocked (or a stale enabled Buy) for the
 * whole session (bug-hunter LOW, 2026-09-02). Bounded instead.
 */

import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";

import type { LiveAlert } from "@/hooks/useAlertStream";
import { signalsApi, type SignalOut } from "@/lib/api/signals";
import { stocksApi } from "@/lib/api/stocks";

/**
 * The user-facing ENTRY alert: a BUY crossing UP through its entry (a SELL crossing DOWN).
 *
 * It was `entry_zone` — a symmetric ±0.5% band that also fired for a BUY drifting DOWN into
 * its entry, i.e. an alert claiming a direction it never checked (Bucket C #2, 2026-10-03).
 * `entry_zone` still streams (outcome recording consumes it) and is labelled as a
 * direction-free band touch. Only entry alerts carry a signal, so only they look one up.
 */
export const ENTRY_SOURCE = "entry_trigger";

/** How long a fetched signal row (plan + eligibility verdict) stays fresh. */
export const SIGNAL_STALE_MS = 60_000;

export interface AlertContext {
  symbolBySid: Map<number, string>;
  signalById: Map<string, SignalOut>;
}

export function useAlertContext(alerts: LiveAlert[], token: string | null): AlertContext {
  const enabled = token !== null;

  const sids = useMemo(() => [...new Set(alerts.map((a) => a.sid))], [alerts]);
  const stockQueries = useQueries({
    queries: sids.map((sid) => ({
      queryKey: ["alert-stock", sid],
      queryFn: () => stocksApi.get(sid, token ?? ""),
      staleTime: Infinity,
      enabled,
    })),
  });
  const symbolBySid = useMemo(() => {
    const m = new Map<number, string>();
    for (const q of stockQueries) {
      if (q.data) m.set(q.data.id, q.data.symbol);
    }
    return m;
  }, [stockQueries]);

  // Only entry alerts carry a signal, so only they trigger a lookup.
  const signalIds = useMemo(
    () => [
      ...new Set(
        alerts
          .filter((a) => a.source === ENTRY_SOURCE && a.signalId)
          .map((a) => a.signalId as string),
      ),
    ],
    [alerts],
  );
  const signalQueries = useQueries({
    queries: signalIds.map((id) => ({
      queryKey: ["alert-signal", id],
      queryFn: () => signalsApi.getById(id, token ?? ""),
      // Bounded, NOT Infinity — the eligibility verdict on this payload is live state.
      staleTime: SIGNAL_STALE_MS,
      enabled,
    })),
  });
  const signalById = useMemo(() => {
    const m = new Map<string, SignalOut>();
    for (const q of signalQueries) {
      if (q.data) m.set(q.data.id, q.data);
    }
    return m;
  }, [signalQueries]);

  return { symbolBySid, signalById };
}

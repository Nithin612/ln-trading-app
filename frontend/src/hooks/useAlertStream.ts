/**
 * useAlertStream — live tick-trigger alerts via the backend WebSocket
 * (/api/v1/ws/live, `subscribe_alerts` protocol — Phase 3.5).
 *
 * One socket per mount; the bell mounts once in AppShell, so the stream
 * is session-scoped: the server tails the alerts stream from "$" (new
 * entries only) and reconnect reconciliation over REST is the documented
 * model. Alerts are the provisional/observability layer — display only.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuthStore } from "@/store/authStore";

export interface LiveAlert {
  id: string; // stream entry id — unique per session, stable list key
  sid: number;
  levelId: string;
  tag: string; // zone_enter | cross_up | cross_down | near | volume_burst
  price: string; // Decimal string from the backend — display only
  ts: number; // epoch seconds, exchange time
  day: string;
  source: string; // pdh | pdl | entry_zone | sl_near | tp_near | sr_* | vburst
  style: string; // market | scalp | intraday | swing | positional
  signalId: string | null;
}

/** Alert frames arrive with all-string values (Redis stream hash). */
export function parseAlert(raw: unknown): LiveAlert | null {
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  const sid = Number(r.sid);
  const ts = Number(r.ts);
  if (!Number.isFinite(sid) || !Number.isFinite(ts)) return null;
  if (typeof r.id !== "string" || typeof r.tag !== "string") return null;
  // Keep price as the Decimal STRING for display, but refuse frames whose
  // price wouldn't render as a number (₹NaN misleads — ui-reviewer LOW).
  if (typeof r.price !== "string" || !Number.isFinite(Number(r.price))) return null;
  return {
    id: r.id,
    sid,
    levelId: String(r.level_id ?? ""),
    tag: r.tag,
    price: r.price,
    ts,
    day: String(r.day ?? ""),
    source: String(r.source ?? ""),
    style: String(r.style ?? "market"),
    signalId: r.signal_id != null ? String(r.signal_id) : null,
  };
}

interface UseAlertStreamResult {
  alerts: LiveAlert[]; // newest first, capped
  connected: boolean;
  authFailed: boolean; // server closed 4401 — reconnect needs a fresh login
  styles: string[]; // active server-side filter; [] = all styles
  setStyles: (styles: string[]) => void;
  watchlist: number | null; // server-side watchlist scope; null = all stocks
  setWatchlist: (id: number | null) => void;
}

// wss under https, ws under http; JWT goes as ?token= (validated server-side
// before the upgrade is accepted — close code 4401 means auth failure).
function buildWsUrl(token: string | null): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const base = `${proto}://${window.location.host}/api/v1/ws/live`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

const WS_CLOSE_UNAUTHORIZED = 4401;
const RECONNECT_DELAY_MS = 3000;
// Bursts (an open-auction XADD batch fans out as individual frames) flush
// as ONE state update per window — never one setState per alert.
const FLUSH_INTERVAL_MS = 200;
const MAX_ALERTS = 100;

// Server contract: `true` = everything; a dict REPLACES the filter set.
// The watchlist's stock set snapshots server-side at subscribe time —
// re-sending (e.g. after editing the watchlist) refreshes it.
function subscribeMsg(styles: string[], watchlist: number | null): string {
  if (styles.length === 0 && watchlist === null) {
    return JSON.stringify({ subscribe_alerts: true });
  }
  return JSON.stringify({
    subscribe_alerts: {
      ...(styles.length ? { styles } : {}),
      ...(watchlist !== null ? { watchlist } : {}),
    },
  });
}

export function useAlertStream(): UseAlertStreamResult {
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const [connected, setConnected] = useState(false);
  const [authFailed, setAuthFailed] = useState(false);
  const [styles, setStylesState] = useState<string[]>([]);
  const [watchlist, setWatchlistState] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const stylesRef = useRef<string[]>(styles);
  const watchlistRef = useRef<number | null>(watchlist);
  const bufferRef = useRef<LiveAlert[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let unmounted = false;

    const flush = () => {
      flushTimerRef.current = null;
      const fresh = bufferRef.current;
      if (fresh.length === 0) return;
      bufferRef.current = [];
      // fresh is in arrival order; the list renders newest first
      setAlerts((prev) => [...fresh.reverse(), ...prev].slice(0, MAX_ALERTS));
    };

    function connect() {
      // Read the token at (re)connect time so a refreshed token is picked up.
      const token = useAuthStore.getState().accessToken;
      ws = new WebSocket(buildWsUrl(token));
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setAuthFailed(false);
        ws.send(subscribeMsg(stylesRef.current, watchlistRef.current));
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as { type: string; data: unknown };
          if (msg.type !== "alert") return;
          const alert = parseAlert(msg.data);
          if (alert === null) return;
          bufferRef.current.push(alert);
          flushTimerRef.current ??= setTimeout(flush, FLUSH_INTERVAL_MS);
        } catch {
          // malformed frame — ignore (at-most-once observability layer)
        }
      };

      ws.onclose = (ev) => {
        setConnected(false);
        if (unmounted) return;
        // 4401 = server rejected the token; reconnecting with the same
        // credentials would just loop. Surface it and wait for a remount
        // with a fresh session instead.
        if (ev.code === WS_CLOSE_UNAUTHORIZED) {
          setAuthFailed(true);
          return;
        }
        reconnectTimeout = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimeout);
      if (flushTimerRef.current !== null) clearTimeout(flushTimerRef.current);
      ws?.close();
    };
  }, []);

  const resend = useCallback(() => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(subscribeMsg(stylesRef.current, watchlistRef.current));
    }
  }, []);

  const setStyles = useCallback(
    (next: string[]) => {
      stylesRef.current = next;
      setStylesState(next);
      resend();
    },
    [resend],
  );

  const setWatchlist = useCallback(
    (id: number | null) => {
      watchlistRef.current = id;
      setWatchlistState(id);
      resend();
    },
    [resend],
  );

  return { alerts, connected, authFailed, styles, setStyles, watchlist, setWatchlist };
}

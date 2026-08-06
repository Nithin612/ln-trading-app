/**
 * useLiveQuotes v2 (Phase 5) — live LTP / candle / signal push from the
 * backend WebSocket (/api/v1/ws/live).
 *
 * Usage:
 *   const { quotes, candles } = useLiveQuotes(["RELIANCE", "TATAMOTORS"]);
 *   quotes["RELIANCE"]?.ltp  // current LTP
 *
 * What v2 fixes (v1 was written for a handful of instruments):
 *
 * 1. **rAF-batched application.** v1 did one `setState` per tick, each
 *    cloning the whole quote map — at full-universe tick rates that is a
 *    render per tick and O(n) copying per tick. v2 buffers frames in a ref
 *    and applies them in ONE state update per animation frame; repeated
 *    ticks for the same symbol inside a frame collapse to the newest (for a
 *    last-traded price, latest wins — nothing is lost by coalescing).
 * 2. **Connect once per mount.** v1 keyed the connect effect on the symbol
 *    list, so every watchlist edit tore down and reopened the socket; and a
 *    second effect re-sent `subscribe` on EVERY render (callers pass a fresh
 *    array literal each time). v2 opens one socket per mount and sends
 *    subscribe/unsubscribe DELTAS when the symbol set actually changes.
 * 3. **Symbols are unsubscribed.** v1 never sent `unsubscribe`, so a long
 *    session leaked server-side Redis subscriptions for every symbol ever
 *    viewed. Dropped symbols now unsubscribe and their stale quotes are
 *    pruned (a stale price under a symbol you stopped tracking is a
 *    money-UI hazard, not just waste).
 * 4. **`authFailed` is surfaced**, matching useAlertStream/useProvisionalStream.
 *
 * Only the LTP/candle layer is coalesced — `signal` frames are rare and are
 * appended in the same flush.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { buildWsUrl, WS_CLOSE_UNAUTHORIZED, WS_RECONNECT_DELAY_MS } from "@/lib/ws";
import { useAuthStore } from "@/store/authStore";

export interface LtpQuote {
  symbol: string;
  ltp: number;
  ts: string;
}

export interface LiveCandle {
  symbol: string;
  timeframe: string;
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_complete: boolean;
}

export interface LiveSignal {
  [key: string]: unknown;
}

interface UseQuotesResult {
  quotes: Record<string, LtpQuote>;
  candles: Record<string, LiveCandle>; // key = "{symbol}:{timeframe}"
  signals: LiveSignal[];
  connected: boolean;
  authFailed: boolean;
}

const MAX_SIGNALS = 50;

/**
 * Schedule on the next animation frame, falling back to a macrotask where
 * rAF is unavailable (a background tab never fires rAF — the fallback keeps
 * state converging either way).
 */
function scheduleFlush(fn: () => void): () => void {
  if (typeof requestAnimationFrame === "function") {
    const id = requestAnimationFrame(() => fn());
    return () => cancelAnimationFrame(id);
  }
  const id = setTimeout(fn, 16);
  return () => clearTimeout(id);
}

export function useLiveQuotes(symbols: string[]): UseQuotesResult {
  const [quotes, setQuotes] = useState<Record<string, LtpQuote>>({});
  const [candles, setCandles] = useState<Record<string, LiveCandle>>({});
  const [signals, setSignals] = useState<LiveSignal[]>([]);
  const [connected, setConnected] = useState(false);
  const [authFailed, setAuthFailed] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  // Symbols the server is currently sending, and the set we WANT. They
  // diverge between a symbol-set change and the socket being open.
  const subscribedRef = useRef<Set<string>>(new Set());
  const wantRef = useRef<Set<string>>(new Set());

  // Per-frame buffers. Quote/candle buffers are keyed maps (coalescing);
  // signals are a list (each one matters).
  const pendingQuotes = useRef<Map<string, LtpQuote>>(new Map());
  const pendingCandles = useRef<Map<string, LiveCandle>>(new Map());
  const pendingSignals = useRef<LiveSignal[]>([]);
  const cancelFlushRef = useRef<(() => void) | null>(null);

  const flush = useCallback(() => {
    cancelFlushRef.current = null;

    if (pendingQuotes.current.size > 0) {
      const batch = pendingQuotes.current;
      pendingQuotes.current = new Map();
      setQuotes((prev) => {
        const next = { ...prev };
        for (const [symbol, q] of batch) next[symbol] = q;
        return next;
      });
    }

    if (pendingCandles.current.size > 0) {
      const batch = pendingCandles.current;
      pendingCandles.current = new Map();
      setCandles((prev) => {
        const next = { ...prev };
        for (const [key, c] of batch) next[key] = c;
        return next;
      });
    }

    if (pendingSignals.current.length > 0) {
      const batch = pendingSignals.current;
      pendingSignals.current = [];
      // batch is in arrival order; the feed renders newest first
      setSignals((prev) => [...batch.reverse(), ...prev].slice(0, MAX_SIGNALS));
    }
  }, []);

  const scheduleIfNeeded = useCallback(() => {
    cancelFlushRef.current ??= scheduleFlush(flush);
  }, [flush]);

  // One socket per mount. Deliberately no `symbols` dependency — the
  // subscription-delta effect below drives what the socket is watching.
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let unmounted = false;

    function connect() {
      // Read the token at (re)connect time so a refreshed token is picked up.
      const token = useAuthStore.getState().accessToken;
      // `socket` is per-invocation on purpose. Handlers must close over THEIR
      // OWN socket: a shared outer variable is reassigned on reconnect, so a
      // stale socket's late close would compare equal to the live one and pass
      // any "is this still current?" guard.
      const socket = new WebSocket(buildWsUrl(token));
      ws = socket;
      wsRef.current = socket;

      socket.onopen = () => {
        if (unmounted || wsRef.current !== socket) return;
        setConnected(true);
        setAuthFailed(false);
        // A reconnect starts from a clean server-side subscription set, so
        // re-send the full want-set rather than a delta against stale state.
        const want = [...wantRef.current];
        subscribedRef.current = new Set(want);
        if (want.length > 0) socket.send(JSON.stringify({ subscribe: want }));
      };

      socket.onmessage = (ev) => {
        if (wsRef.current !== socket) return; // ticks from a superseded socket
        try {
          const msg = JSON.parse(ev.data as string) as { type: string; data: unknown };
          if (msg.type === "ltp") {
            const d = msg.data as LtpQuote;
            pendingQuotes.current.set(d.symbol, d);
            scheduleIfNeeded();
          } else if (msg.type === "candle") {
            const d = msg.data as LiveCandle;
            pendingCandles.current.set(`${d.symbol}:${d.timeframe}`, d);
            scheduleIfNeeded();
          } else if (msg.type === "signal") {
            pendingSignals.current.push(msg.data as LiveSignal);
            scheduleIfNeeded();
          }
        } catch {
          // ignore malformed messages
        }
      };

      socket.onclose = (ev) => {
        // Guard FIRST. StrictMode double-mounts, so an aborted socket's close
        // can land after the live one has opened; letting it run would clear
        // `connected` while ticks flow and empty `subscribedRef`, after which
        // every symbol removal computes an empty delta and no `unsubscribe` is
        // ever sent again — resurrecting the v1 leak for the whole session.
        if (unmounted || wsRef.current !== socket) return;
        setConnected(false);
        subscribedRef.current = new Set();
        // 4401 = server rejected the token; reconnecting with the same
        // credentials would just loop. Surface it and wait for a remount
        // with a fresh session instead.
        if (ev.code === WS_CLOSE_UNAUTHORIZED) {
          setAuthFailed(true);
          return;
        }
        reconnectTimeout = setTimeout(connect, WS_RECONNECT_DELAY_MS);
      };

      socket.onerror = () => socket.close();
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimeout);
      cancelFlushRef.current?.();
      cancelFlushRef.current = null;
      ws?.close();
    };
  }, [scheduleIfNeeded]);

  // Callers pass a fresh array literal every render, so this effect keys off
  // the SET's content, not the array identity — otherwise it resubscribes on
  // every render (the v1 bug).
  const symbolsKey = [...new Set(symbols)].sort().join(",");

  useEffect(() => {
    const want = new Set(symbolsKey ? symbolsKey.split(",") : []);
    const prevWant = wantRef.current;
    wantRef.current = want;

    // Pruning is driven by what the CALLER dropped (prevWant → want), not by
    // `subscribedRef`: while the socket is down, `subscribedRef` is empty, so a
    // subscribedRef-based diff would find nothing to drop and leave a stale
    // price on screen under a symbol that is no longer tracked.
    const dropped = [...prevWant].filter((s) => !want.has(s));

    const add = [...want].filter((s) => !subscribedRef.current.has(s));
    const unsub = [...subscribedRef.current].filter((s) => !want.has(s));

    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN && (add.length > 0 || unsub.length > 0)) {
      if (add.length > 0) ws.send(JSON.stringify({ subscribe: add }));
      if (unsub.length > 0) ws.send(JSON.stringify({ unsubscribe: unsub }));
      subscribedRef.current = want;
    }

    if (dropped.length > 0) {
      // Also discard anything already buffered for a dropped symbol, or the
      // next frame's flush would re-insert the very price we just pruned.
      for (const s of dropped) pendingQuotes.current.delete(s);
      setQuotes((prev) => {
        const next = { ...prev };
        let changed = false;
        for (const s of dropped) {
          if (s in next) {
            delete next[s];
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }
  }, [symbolsKey]);

  return { quotes, candles, signals, connected, authFailed };
}

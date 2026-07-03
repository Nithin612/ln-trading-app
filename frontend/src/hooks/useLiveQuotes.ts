/**
 * useLiveQuotes — subscribes to live LTP and candle updates via the backend
 * WebSocket (/api/v1/ws/live).
 *
 * Usage:
 *   const { quotes, candles } = useLiveQuotes(["RELIANCE", "TATAMOTORS"]);
 *   quotes["RELIANCE"]?.ltp  // current LTP
 */

import { useEffect, useRef, useState } from "react";

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
  candles: Record<string, LiveCandle>;  // key = "{symbol}:{timeframe}"
  signals: LiveSignal[];
  connected: boolean;
}

const WS_URL = `ws://${window.location.host}/api/v1/ws/live`;

export function useLiveQuotes(symbols: string[]): UseQuotesResult {
  const [quotes, setQuotes] = useState<Record<string, LtpQuote>>({});
  const [candles, setCandles] = useState<Record<string, LiveCandle>>({});
  const [signals, setSignals] = useState<LiveSignal[]>([]);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const symbolsRef = useRef<string[]>(symbols);

  useEffect(() => {
    symbolsRef.current = symbols;
  });

  useEffect(() => {
    if (symbols.length === 0) return;

    let ws: WebSocket;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let unmounted = false;

    function connect() {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        ws.send(JSON.stringify({ subscribe: symbolsRef.current }));
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as { type: string; data: unknown };
          if (msg.type === "ltp") {
            const d = msg.data as LtpQuote;
            setQuotes((prev) => ({ ...prev, [d.symbol]: d }));
          } else if (msg.type === "candle") {
            const d = msg.data as LiveCandle;
            const key = `${d.symbol}:${d.timeframe}`;
            setCandles((prev) => ({ ...prev, [key]: d }));
          } else if (msg.type === "signal") {
            setSignals((prev) => [msg.data as LiveSignal, ...prev].slice(0, 50));
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!unmounted) {
          reconnectTimeout = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimeout);
      ws?.close();
    };
  }, [symbols.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  // Send subscribe/unsubscribe when symbol list changes
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ subscribe: symbols }));
    }
  }, [symbols]);

  return { quotes, candles, signals, connected };
}

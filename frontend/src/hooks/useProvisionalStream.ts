/**
 * useProvisionalStream — live per-style provisional leaderboards via the
 * backend WebSocket (/api/v1/ws/live, `subscribe_provisional` protocol —
 * Phase 3 slice 3.5).
 *
 * Each frame is a FULL per-style snapshot (not a delta), so state is just
 * "latest payload per style"; the REST endpoint
 * (`provisionalApi.getLeaderboard`) reconciles initial mount and
 * reconnects. Frames arrive at the worker's refresh cadence (~1/3 s per
 * style) — no batching needed at that rate.
 *
 * Everything here is the provisional/observability layer — display only,
 * labelled as such end-to-end.
 */

import { useEffect, useState } from "react";

import type { ProvisionalLeaderboard } from "@/lib/api/market_data";
import { useAuthStore } from "@/store/authStore";

const WS_CLOSE_UNAUTHORIZED = 4401;
const RECONNECT_DELAY_MS = 3000;

function buildWsUrl(token: string | null): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const base = `${proto}://${window.location.host}/api/v1/ws/live`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export function parseLeaderboard(raw: unknown): ProvisionalLeaderboard | null {
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  if (r.provisional !== true) return null; // labelled end-to-end, or refused
  if (typeof r.style !== "string" || !Array.isArray(r.rows)) return null;
  return {
    provisional: true,
    style: r.style,
    as_of: typeof r.as_of === "string" ? r.as_of : null,
    rows: r.rows as ProvisionalLeaderboard["rows"],
  };
}

interface UseProvisionalStreamResult {
  boards: Record<string, ProvisionalLeaderboard>; // latest snapshot per style
  connected: boolean;
  authFailed: boolean;
}

export function useProvisionalStream(styles: string[]): UseProvisionalStreamResult {
  const [boards, setBoards] = useState<Record<string, ProvisionalLeaderboard>>({});
  const [connected, setConnected] = useState(false);
  const [authFailed, setAuthFailed] = useState(false);

  // subscription is style-set-scoped; resubscribe only when the SET changes
  const stylesKey = [...styles].sort().join(",");

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let unmounted = false;
    const want = stylesKey ? stylesKey.split(",") : [];

    function connect() {
      const token = useAuthStore.getState().accessToken;
      ws = new WebSocket(buildWsUrl(token));

      ws.onopen = () => {
        setConnected(true);
        setAuthFailed(false);
        ws.send(
          JSON.stringify({
            subscribe_provisional: want.length ? want : true,
          }),
        );
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as { type: string; data: unknown };
          if (msg.type !== "provisional") return;
          const board = parseLeaderboard(msg.data);
          if (board === null) return;
          setBoards((prev) => ({ ...prev, [board.style]: board }));
        } catch {
          // malformed frame — ignore (at-most-once observability layer)
        }
      };

      ws.onclose = (ev) => {
        setConnected(false);
        if (unmounted) return;
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
      ws?.close();
    };
  }, [stylesKey]);

  return { boards, connected, authFailed };
}

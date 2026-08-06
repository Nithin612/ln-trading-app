/**
 * Shared WebSocket plumbing for the live layer (/api/v1/ws/live).
 *
 * The three live hooks (useLiveQuotes, useAlertStream, useProvisionalStream)
 * each open their own socket but must agree on url construction, the
 * auth-failure close code, and the reconnect delay — so those live here
 * rather than being retyped per hook.
 */

/** App-level close code mirroring HTTP 401 (server closes with this on a bad token). */
export const WS_CLOSE_UNAUTHORIZED = 4401;

/** Backoff before a reconnect attempt after a non-auth close. */
export const WS_RECONNECT_DELAY_MS = 3000;

/**
 * wss under https, ws under http — never a hardcoded scheme (a hardcoded
 * `ws://` breaks the moment the app is served over TLS). The JWT travels as
 * `?token=`; the server validates it BEFORE accepting the upgrade, so an
 * invalid token surfaces as close code 4401 rather than a network error.
 */
export function buildWsUrl(token: string | null, path = "/api/v1/ws/live"): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const base = `${proto}://${window.location.host}${path}`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

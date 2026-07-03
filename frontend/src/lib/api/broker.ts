import { api } from "./client";

export interface TokenStatus {
  connected: boolean;
  expires_at: string | null;
  consumer_running: boolean;
}

export interface InstrumentSyncResult {
  synced: number;
}

export const brokerApi = {
  getKiteLoginUrl(token: string): Promise<{ login_url: string }> {
    return api.get("/broker/kite/login", token);
  },

  exchangeKiteToken(
    requestToken: string,
    token: string,
  ): Promise<{ detail: string; expires_at: string }> {
    return api.get(`/broker/kite/exchange?request_token=${encodeURIComponent(requestToken)}`, token);
  },

  getKiteStatus(token: string): Promise<TokenStatus> {
    return api.get("/broker/kite/status", token);
  },

  syncKiteInstruments(token: string): Promise<InstrumentSyncResult> {
    return api.post("/broker/kite/instruments/sync", undefined, token);
  },

  startConsumer(token: string): Promise<{ detail: string }> {
    return api.post("/broker/kite/consumer/start", undefined, token);
  },

  stopConsumer(token: string): Promise<{ detail: string }> {
    return api.post("/broker/kite/consumer/stop", undefined, token);
  },
};

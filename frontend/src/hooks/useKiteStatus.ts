import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { brokerApi } from "../lib/api/broker";
import { useAuth } from "./useAuth";

export interface KiteStatusResult {
  connected: boolean;
  expiringSoon: boolean;
  minutesLeft: number | null;
  consumerRunning: boolean;
}

export function useKiteStatus(): KiteStatusResult {
  const { accessToken, isAdmin } = useAuth();

  const { data } = useQuery({
    queryKey: ["kite-status"],
    queryFn: () => brokerApi.getKiteStatus(accessToken!),
    enabled: !!accessToken && isAdmin,
    refetchInterval: 5 * 60 * 1000,
    staleTime: 2 * 60 * 1000,
  });

  // Tick every minute so expiry countdown stays current without re-fetching.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setTick((n) => n + 1);
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  const computed = useMemo(() => {
    if (!data?.connected || !data.expires_at) {
      return { expiringSoon: false, minutesLeft: null };
    }
    // tick is intentionally used to invalidate memo every minute.
    void tick;
    const msLeft = new Date(data.expires_at).getTime() - Date.now(); // eslint-disable-line react-hooks/purity
    const mins = Math.max(0, Math.floor(msLeft / 60_000));
    return { expiringSoon: mins <= 60, minutesLeft: mins };
  }, [data, tick]);

  if (!data) {
    return { connected: false, expiringSoon: false, minutesLeft: null, consumerRunning: false };
  }

  return {
    connected: data.connected,
    expiringSoon: computed.expiringSoon,
    minutesLeft: computed.minutesLeft,
    consumerRunning: data.consumer_running,
  };
}

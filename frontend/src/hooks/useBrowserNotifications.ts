/**
 * useBrowserNotifications — opt-in desktop notifications for live alerts
 * (Phase 5 slice 5.4).
 *
 * Design decisions worth knowing:
 *
 * - **Opt-in, persisted, and never auto-requested.** Permission is only asked
 *   for on an explicit user action; browsers penalise unsolicited prompts and
 *   a denied permission is effectively permanent.
 * - **Notifies regardless of tab visibility.** The point is the case where the
 *   browser is behind an IDE or chart window — `document.hidden` is false there
 *   (the tab is the active one in its window), so gating on it would suppress
 *   exactly the alerts that matter most.
 * - **Bursts coalesce.** The open-auction XADD batch can fan out dozens of
 *   alerts in one flush; firing one popup each would be unusable, so anything
 *   above `BURST_CAP` in a single batch becomes ONE summary notification.
 * - **Alerts already seen never re-notify**, and the batch present at mount (or
 *   at the moment notifications are switched on) is marked seen WITHOUT
 *   notifying — enabling the toggle must not dump the backlog on screen.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { LiveAlert } from "@/hooks/useAlertStream";
import { SOURCE_LABEL, TAG_META } from "@/features/alerts/alertPresentation";

const ENABLED_KEY = "alerts:notify";

/** More than this many new alerts in one batch collapses to a summary. */
export const BURST_CAP = 3;

export interface UseBrowserNotificationsResult {
  /** False where the Notification API does not exist at all. */
  supported: boolean;
  permission: NotificationPermission | "unsupported";
  enabled: boolean;
  /** Turning on requests permission; a denial leaves `enabled` false. */
  setEnabled: (on: boolean) => void | Promise<void>;
}

function loadEnabled(): boolean {
  try {
    return localStorage.getItem(ENABLED_KEY) === "1";
  } catch {
    return false;
  }
}

function storeEnabled(on: boolean): void {
  try {
    localStorage.setItem(ENABLED_KEY, on ? "1" : "0");
  } catch {
    /* private mode / storage disabled — the toggle just won't persist */
  }
}

function alertTitle(a: LiveAlert): string {
  const tag = TAG_META[a.tag]?.label ?? a.tag;
  const source = SOURCE_LABEL[a.source] ?? a.source;
  return `${tag} · ${source}`;
}

export function useBrowserNotifications(alerts: LiveAlert[]): UseBrowserNotificationsResult {
  // Probe the VALUE, not just the key: `"Notification" in window` is true even
  // when the property exists set to undefined, and reading `.permission` off
  // that throws.
  const supported = typeof window !== "undefined" && typeof window.Notification === "function";

  const [enabled, setEnabledState] = useState<boolean>(() => supported && loadEnabled());
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    supported ? Notification.permission : "unsupported",
  );

  // Alert ids already accounted for. Seeded on the first pass so a page load
  // with a full buffer stays silent.
  const seenRef = useRef<Set<string>>(new Set());
  const primedRef = useRef(false);

  const setEnabled = useCallback(
    async (on: boolean) => {
      if (!on) {
        setEnabledState(false);
        storeEnabled(false);
        return;
      }
      if (!supported) return;
      let perm = Notification.permission;
      if (perm === "default") {
        // Only ever from a user gesture.
        perm = await Notification.requestPermission();
      }
      setPermission(perm);
      const granted = perm === "granted";
      setEnabledState(granted);
      storeEnabled(granted);
    },
    [supported],
  );

  useEffect(() => {
    if (!supported) return;

    // Newest-first from useAlertStream; notify oldest-first so the newest
    // popup is the one left on top.
    const fresh = alerts.filter((a) => !seenRef.current.has(a.id)).reverse();
    for (const a of fresh) seenRef.current.add(a.id);

    // Bound the set so a long session can't grow it without limit; the stream
    // itself only retains 100, so anything evicted here can't reappear.
    if (seenRef.current.size > 500) {
      seenRef.current = new Set(alerts.map((a) => a.id));
    }

    if (!primedRef.current) {
      primedRef.current = true; // first pass: mark seen, stay silent
      return;
    }
    // Toggling `enabled`/`permission` re-runs this effect, but every alert is
    // already in `seenRef` by then, so `fresh` is empty and nothing re-fires —
    // which is also why switching notifications on never dumps the backlog.
    if (fresh.length === 0 || !enabled || permission !== "granted") return;

    try {
      if (fresh.length > BURST_CAP) {
        new Notification(`${fresh.length} new alerts`, {
          body: "Open Live Signals to review the burst.",
          tag: "alerts-burst",
        });
        return;
      }
      for (const a of fresh) {
        new Notification(alertTitle(a), {
          body: `₹${a.price} · ${a.style}`,
          // Same id never stacks twice if the effect somehow re-runs.
          tag: `alert-${a.id}`,
        });
      }
    } catch {
      /* some browsers throw for Notification outside a service worker */
    }
  }, [alerts, supported, enabled, permission]);

  return { supported, permission, enabled, setEnabled };
}

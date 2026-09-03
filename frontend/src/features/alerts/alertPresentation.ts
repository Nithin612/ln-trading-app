/**
 * Presentation vocabulary for live tick-trigger alerts (Phase 3.5).
 *
 * `tag` comes from the Rust trigger engine (TriggerTag::as_str — WHAT
 * fired); `source`/`style` come from the host level registry
 * (live_levels.py — what the level MEANS). Unknown values render as raw
 * strings so new backend vocabulary degrades visibly instead of hiding
 * alerts.
 */

import type { SignalOut } from "@/lib/api/signals";

export const ALERT_STYLES = ["market", "scalp", "intraday", "swing", "positional"] as const;

// Anti-chase guardrail. A signal is meant to be entered at its `entry_price`.
// Once price runs past that by ~a third of the trade's risk (entry→SL distance
// = 1R), the reward:risk you were shown is materially gone — buying there is
// chasing. We surface that ceiling/floor and flag when the trigger price has
// already blown through it. Static: derived from the signal alone.
export const CHASE_R_FRACTION = 0.33;

export interface ChaseInfo {
  isBuy: boolean;
  entry: number;
  limit: number; // don't-chase price (entry ± 0.33R)
  extended: boolean; // trigger price already past the limit
  pastEntryPct: number; // signed % beyond entry in the trade's direction
}

export function chaseGuidance(signal: SignalOut, triggerPrice: number): ChaseInfo | null {
  const entry = Number(signal.entry_price);
  const stop = Number(signal.stop_loss);
  if (!Number.isFinite(entry) || !Number.isFinite(stop) || entry <= 0) return null;
  const risk = Math.abs(entry - stop);
  if (risk <= 0) return null;
  const isBuy = signal.direction === "BUY";
  const limit = isBuy ? entry + CHASE_R_FRACTION * risk : entry - CHASE_R_FRACTION * risk;
  const beyond = isBuy ? triggerPrice - entry : entry - triggerPrice;
  return {
    isBuy,
    entry,
    limit,
    extended: isBuy ? triggerPrice > limit : triggerPrice < limit,
    pastEntryPct: (beyond / entry) * 100,
  };
}

// ── Trade-plan context (surfaced alongside the anti-chase guardrail) ─────────
// Everything below is derived from the committed signal alone — no live data,
// no backend change. It answers the three things a user can't judge from a bare
// alert: what the plan is (SL/TP/reward:risk), when it was generated, and how
// long it stays valid ("when only to consider").

export interface TradePlan {
  sl: number;
  tp: number;
  rr: number | null; // reward:risk = |tp − entry| / |entry − sl|; null if risk ≤ 0
}

export function tradePlan(signal: SignalOut): TradePlan | null {
  const entry = Number(signal.entry_price);
  const sl = Number(signal.stop_loss);
  const tp = Number(signal.take_profit);
  if (![entry, sl, tp].every(Number.isFinite)) return null;
  const risk = Math.abs(entry - sl);
  return { sl, tp, rr: risk > 0 ? Math.abs(tp - entry) / risk : null };
}

/**
 * "just now" / "5m ago" / "3h ago" / "2d ago" — how long since the confluence
 * engine committed this signal. `now` is injectable for deterministic tests.
 */
export function signalAgeLabel(createdAtIso: string, now: number = Date.now()): string {
  const t = new Date(createdAtIso).getTime();
  if (!Number.isFinite(t)) return "";
  const mins = Math.floor((now - t) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const IST_HHMM = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/**
 * "when only to consider" — how much runway is left before the signal expires.
 * Intraday plans (validity same-session) show the IST cut-off time ("till
 * 15:15"); multi-day plans (swing/positional) show trading-days remaining
 * ("4d left"), both server-computed on `days_valid_remaining`.
 */
export function validityLabel(signal: SignalOut): string {
  const days = signal.days_valid_remaining;
  if (Number.isFinite(days) && days >= 1) return `${Math.floor(days)}d left`;
  const until = new Date(signal.validity_until);
  if (Number.isNaN(until.getTime())) return "expires today";
  return `till ${IST_HHMM.format(until)}`;
}

// The signal is "stale" once ≥80% of its validity window has elapsed (mirrors the backend
// `near_expiry` flag). So the useful trade window is entry → that 80% mark; past it the edge
// has decayed (a positional signal traded on ~day 25 of 30 is exactly this failure).
export const NEAR_EXPIRY_FRACTION = 0.8;

const IST_DAYMON = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
});

/**
 * How far into its validity window a signal is, as a percent (0 = just committed, 100 = at
 * expiry, >100 = lapsed). `null` when timestamps are unparseable/degenerate. The signal-age
 * evidence shows the edge lives ≤40% elapsed and decays past it, so this feeds conviction ranking.
 */
export function pctElapsed(signal: SignalOut, now: number = Date.now()): number | null {
  const created = new Date(signal.created_at).getTime();
  const until = new Date(signal.validity_until).getTime();
  if (!Number.isFinite(created) || !Number.isFinite(until) || until <= created) return null;
  return ((now - created) / (until - created)) * 100;
}

/**
 * "best by 12 Aug" / "best by 14:30" — the end of the useful trade window (the 80%-elapsed
 * mark), after which the signal weakens. Date for multi-day plans, IST time for intraday.
 * "" when the timestamps are unparseable or degenerate.
 */
export function bestByLabel(signal: SignalOut): string {
  const created = new Date(signal.created_at).getTime();
  const until = new Date(signal.validity_until).getTime();
  if (!Number.isFinite(created) || !Number.isFinite(until) || until <= created) return "";
  const span = until - created;
  const bestBy = new Date(created + NEAR_EXPIRY_FRACTION * span);
  const label = span > 24 * 60 * 60 * 1000 ? IST_DAYMON.format(bestBy) : IST_HHMM.format(bestBy);
  return `best by ${label}`;
}

export interface TagMeta {
  label: string;
  glyph: string;
  tone: "profit" | "loss" | "info" | "warning";
}

export const TAG_META: Record<string, TagMeta> = {
  cross_up: { label: "Crossed above", glyph: "▲", tone: "profit" },
  cross_down: { label: "Crossed below", glyph: "▼", tone: "loss" },
  zone_enter: { label: "Entered zone", glyph: "◆", tone: "info" },
  near: { label: "Approaching", glyph: "≈", tone: "warning" },
  volume_burst: { label: "Volume burst", glyph: "⚡", tone: "warning" },
};

export const SOURCE_LABEL: Record<string, string> = {
  pdh: "PDH",
  pdl: "PDL",
  entry_zone: "Entry zone",
  sl_near: "Stop loss",
  tp_near: "Target",
  sr_support: "Support",
  sr_resistance: "Resistance",
  vburst: "Volume",
};

// Direction/tone always glyph + color, never color alone (UI_GUIDELINES).
export const TONE_CLASS: Record<TagMeta["tone"], string> = {
  profit: "text-(--color-profit)",
  loss: "text-(--color-loss)",
  info: "text-(--color-info)",
  warning: "text-(--color-warning)",
};

const IST_TIME = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

/** Alerts are market events — timestamps always display as IST. */
export function formatAlertTime(tsEpochSec: number): string {
  return IST_TIME.format(new Date(tsEpochSec * 1000));
}

// ── Order-eligibility presentation (2026-09-02) ─────────────────────────────
// A signal the ACTIVE gates would reject must not offer a live Buy button. The BACKEND
// decides (`app/signals/eligibility.py` → `blocked`/`block_reason`); this only renders
// that verdict. Centralised because the first pass wired only two of the FOUR Buy
// surfaces and left the Dashboard — the landing page, and the widest one — still firing
// orders that could only 409 (bug-hunter, 2026-09-02). Every surface calls this, so a
// fifth cannot silently miss the rule.

export interface TradeBlock {
  blocked: boolean;
  /**
   * An ACTIVE gate the server could NOT judge on this path (`unassessed`). NOT blocked —
   * we do not know — so the action stays available, but it MUST be visibly marked:
   * ui-reviewer (2026-09-02) found the first version returned this field and no surface
   * read it, while its own docstring promised the opposite. `unknownLabel` is the visible
   * marker; render it next to the row's other flags.
   */
  unknown: boolean;
  /**
   * `disabled` ONLY for genuinely transient non-interactive states (in-flight order, kill
   * switch). A BLOCKED button uses `ariaDisabled` instead, because a native `disabled`
   * removes the element from the tab order AND (via the Button primitive's
   * `disabled:pointer-events-none`) kills its own tooltip — so the reason became
   * unreachable by keyboard *and* mouse (ui-reviewer HIGH, 2026-09-02). Blocked buttons
   * stay focusable, keep their focus ring, and are made inert by the click guard below.
   */
  nativeDisabled: boolean;
  ariaDisabled: true | undefined;
  /** True when the click must not fire — check this first in every onClick. */
  inert: boolean;
  title: string;
  ariaLabel: string;
  /** The one blocked label for all surfaces: glyph + word, never colour alone. */
  label: string;
  /** The one "unknown" marker for all surfaces. */
  unknownLabel: string;
}

/** Single visual+a11y vocabulary for the eligibility state, shared by all FIVE Buy
 *  surfaces (AlertBell · OpportunitiesTable · DashboardPage · LiveSignalsPage ·
 *  StylePage). ui-reviewer found five variations of one state when each surface rendered
 *  it by hand; everything visible now comes from here. */
export function tradeBlock(
  signal: Partial<Pick<SignalOut, "blocked" | "block_reason" | "unassessed" | "direction">>,
  opts: {
    symbol?: string;
    halted?: boolean;
    isTrading?: boolean;
    normalTitle: string;
    normalAria: string;
  },
): TradeBlock {
  const reason = signal.block_reason ?? "Blocked by an active eligibility gate";
  const blocked = signal.blocked === true;
  const gaps = signal.unassessed ?? [];
  const unknown = !blocked && gaps.length > 0;
  const note = ` · ⚠ not fully checked here (${gaps.join(", ")}) — the order path may still reject it`;
  return {
    blocked,
    unknown,
    nativeDisabled: opts.halted === true || opts.isTrading === true,
    ariaDisabled: blocked ? true : undefined,
    inert: blocked || opts.halted === true || opts.isTrading === true,
    title: blocked
      ? reason
      : opts.halted
        ? "Trading is halted — release the kill switch on Go Live"
        : opts.normalTitle + (unknown ? note : ""),
    ariaLabel: blocked
      ? `${opts.symbol ?? "signal"} not tradeable: ${reason}`
      : opts.normalAria + (unknown ? ", eligibility not fully checked" : ""),
    label: "⊘ Blocked",
    unknownLabel: "⚠ unchecked",
  };
}

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

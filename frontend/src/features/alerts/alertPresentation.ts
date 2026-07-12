/**
 * Presentation vocabulary for live tick-trigger alerts (Phase 3.5).
 *
 * `tag` comes from the Rust trigger engine (TriggerTag::as_str — WHAT
 * fired); `source`/`style` come from the host level registry
 * (live_levels.py — what the level MEANS). Unknown values render as raw
 * strings so new backend vocabulary degrades visibly instead of hiding
 * alerts.
 */

export const ALERT_STYLES = ["market", "scalp", "intraday", "swing", "positional"] as const;

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

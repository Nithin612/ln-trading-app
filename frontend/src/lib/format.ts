const INR_NUM = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
})

const INR_INT = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
})

const INR_CURRENCY = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
})

/** "1,23,456.78" — no symbol */
export const formatINR = (n: number) => INR_NUM.format(n)

/** "1,23,456" — integer (lot sizes, share counts) */
export const formatInt = (n: number) => INR_INT.format(n)

/** "₹1,23,456.78" — with INR symbol */
export const formatCurrency = (n: number) => INR_CURRENCY.format(n)

/** Compact: "1.52 Cr" / "23.45 L" / "9,234.56" */
export const formatLakh = (n: number) => {
  const abs = Math.abs(n)
  if (abs >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`
  if (abs >= 1e5) return `${(n / 1e5).toFixed(2)} L`
  return INR_NUM.format(n)
}

/** "+2.34%" / "-1.12%" — signed by default */
export const formatPct = (n: number, opts?: { signed?: boolean }) => {
  const signed = opts?.signed ?? true
  const sign = signed && n > 0 ? "+" : ""
  return `${sign}${n.toFixed(2)}%`
}

const IST_DATETIME = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
})

/**
 * Market datetimes ALWAYS display as IST, never the browser's zone: a signal's
 * validity deadline read in the wrong timezone is a trading hazard, and storage
 * is UTC while market logic is IST (.claude/rules/trading-domain.md).
 * Returns "—" for an unparseable value rather than "Invalid Date".
 */
export const formatIstDateTime = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "—" : `${IST_DATETIME.format(d)} IST`
}

/**
 * Greeks and other small analytical values: fixed decimals, no grouping.
 * Delta/gamma need 4 dp (index gamma is ~1e-4); vega/theta read better at 2.
 * Lives here so feature code never reaches for `toFixed` (.claude/rules/ui.md).
 */
export const formatGreek = (n: number, dp = 4) => n.toFixed(dp)

/**
 * Reward:risk (and similar unit-less ratios) as "N.N" — one decimal, no
 * grouping, no unit. Callers append ":1" when they mean a ratio-to-one.
 * Lives here so feature code never reaches for `toFixed` (.claude/rules/ui.md).
 * Non-finite (0-risk trade) → "—".
 */
export const formatRatio = (n: number) => (Number.isFinite(n) ? n.toFixed(1) : "—")

/** "▲ +2.34%" / "▼ -1.12%" / "— 0.00%" — directional glyph included */
export const formatChange = (n: number) => {
  const epsilon = 0.005
  if (n > epsilon) return `▲ +${n.toFixed(2)}%`
  if (n < -epsilon) return `▼ ${n.toFixed(2)}%`
  return `— 0.00%`
}

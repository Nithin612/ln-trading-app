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

/** "▲ +2.34%" / "▼ -1.12%" / "— 0.00%" — directional glyph included */
export const formatChange = (n: number) => {
  const epsilon = 0.005
  if (n > epsilon) return `▲ +${n.toFixed(2)}%`
  if (n < -epsilon) return `▼ ${n.toFixed(2)}%`
  return `— 0.00%`
}

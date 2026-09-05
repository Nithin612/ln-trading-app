# UI rules (distilled from docs/UI_GUIDELINES.md — read that for full detail)

The dashboard shows money. Rendering mistakes mislead trades. These are the
rules ui-reviewer enforces; UI_GUIDELINES.md sections are cited in reviews.

## Colors — tokens only

- All color via CSS custom properties from `src/styles/tokens.css`. The app
  has 5 themes (slate default, midnight, carbon, ocean, daybreak) switched
  by `data-theme` — hardcoded colors break four of them.
- Profit/loss/directional: `--color-profit` / `--color-loss` (+ `-bg`
  variants). NEVER `text-green-500`-style palette classes, never raw hex in
  feature code, never `dark:` variants.
- Direction always glyph + color (▲/▼ or icons), never color alone.

## Numbers

- Formatted exclusively via `lib/format.ts`: `formatCurrency` (₹, Indian
  grouping), `formatINR`, `formatLakh` (L/Cr), `formatPct`, `formatChange`.
  No `toFixed`/`toLocaleString` in features.
- Numeric table columns right-aligned, `tabular-nums` (the `numeric` variant
  on TableHead/TableCell). Prices to 2 decimals display (4 in storage);
  quantities as integers with grouping.

## Tables (the app is mostly tables)

- Sticky, OPAQUE header (`--color-surface`); zebra rows via `--color-row-alt`;
  hover state; sortable headers show direction.
- ≥200 rows or live-updating → TanStack Virtual + memoized rows.
- Loading = Skeleton rows matching the real layout; explicit empty state
  with a next action; error state with retry.
- Live prices flash via the `PriceCell` pattern (250ms bg pulse on change) —
  no full-row re-render per tick.

## Panels, layout, focus

- Floating panels: Portal + solid `--color-surface` bg + strong border +
  shadow + z-50+. Sidebar z-20, topbar z-30. No transparency on solid
  surfaces (no `bg-*/50`).
- Themed controls only (`SimpleSelect`, `Checkbox`, `Slider`, `Dialog`…);
  native controls fail review.
- Focus-visible ring on every interactive element; aria-label on icon-only
  buttons; Escape closes any panel; 44px minimum touch targets.

## Uncertainty — never render a precise figure without it (A24)

A precise number reads as a confidence signal whether or not it is one. Two decimal places
say "this was measured"; a calendar date says "this will happen". The failure mode we are
specifically exposed to is converting a wish into a timeline — a 2–3%/day goal invites
exactly that.

- **No bare point estimate for anything predictive** — a date, a target, a "confidence",
  an expected return, a projected balance. Ship the interval, the sample it rests on, or
  the assumption it inherits, in the same visual element. Not a tooltip.
- **A projection must depend on what it projects.** The external review's worst example was
  a "probable exit date" carrying no volatility term that **did not even depend on the
  target price it was the date for**. If changing the input does not move the number, the
  number is decoration.
- **Round to the precision you actually have.** `+14.7382%` on 44 trades claims six
  significant figures from a sample that supports one. Match displayed precision to the
  evidence, not to the float.
- **A sample size travels with its statistic** (H11): `n=44` is never rendered without
  `needs ≈N`, and `n/20`-style progress bars must be labelled as process conventions, not
  statistical thresholds.
- **"Not assessable" is a legitimate rendering** and beats a plausible-looking default.
  `—` for undefined, `>50` for a value at its cap (H6) — the three cases (undefined,
  off-scale, measured) must stay visually distinct.
- Corollary for copy: a caveat must branch on the data. A fixed hedge that is wrong in some
  branch is worse than none — see `buy_and_hold._deployment_note`, where "we were
  under-deployed" excuses a shortfall against a *rising* index and emphatically does not
  against a falling one.

## New-component checklist

When adding from shadcn/base-ui: strip `dark:` classes, replace
`bg-muted/50`-style semi-transparent surfaces, verify `text-foreground`
tokens resolve in tokens.css, wire the Portal, then test in daybreak (light)
AND carbon (highest contrast) — not just the default theme.

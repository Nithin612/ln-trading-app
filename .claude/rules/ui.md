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

## New-component checklist

When adding from shadcn/base-ui: strip `dark:` classes, replace
`bg-muted/50`-style semi-transparent surfaces, verify `text-foreground`
tokens resolve in tokens.css, wire the Portal, then test in daybreak (light)
AND carbon (highest contrast) — not just the default theme.

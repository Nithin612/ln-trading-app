# UI Guidelines

Mandatory reading for anyone (human or Claude Code) writing UI in this project. These rules are why our app reads like a tool traders trust, not a generic SaaS dashboard.

> If anything here **conflicts with the existing code**, surface the conflict before changing it. Some violations are intentional legacy debt; others are bugs. Don't blindly bulldoze.

---

## §0 — How to use this doc

Read fully on first session. After that, jump to the relevant section when you're about to:
- Add a token (colour, spacing, radius) → §2
- Render a number, price, percent, or currency → §3
- Pick a colour for profit/loss/status/direction → §5
- Build or modify a table → §6
- Show a loading or real-time state → §7
- Use an `<input>`, `<select>`, `<button>` directly → §8
- Lay out a new page → §9
- Decide on an animation or transition → §11

Before committing, run the pre-commit checklist in §13.

---

## §1 — Cardinal rules (the short list)

These are non-negotiable. If a PR violates any of them, reject it.

1. **Numbers use `font-variant-numeric: tabular-nums`.** Set globally in `tokens.css`. Verify before merge.
2. **Numeric table columns are right-aligned.** Symbol/name left-aligned; everything else (price, %, qty, P&L, volume) right.
3. **Money/percentages route through `lib/format.ts`.** Never `{`₹${value}`}` or `{value.toFixed(2) + "%"}`.
4. **Profit/loss colours come from tokens**, never raw `text-green-*` / `text-red-*`.
5. **Direction is encoded by glyph + colour**, never colour alone.
6. **Themed components only.** No raw `<button>`, `<input>`, `<select>`, `<input type="checkbox">` in feature code.
7. **No `/50` `/30` `/20` opacity on solid surface backgrounds.** Use a dedicated solid token.
8. **Sticky table headers, opaque background, never transparent.**
9. **Loading states are `<Skeleton>` shaped like the final content**, never `<div>Loading...</div>`.
10. **Focus-visible rings on every interactive element.**

---

## §2 — Design tokens

All tokens live in `frontend/src/styles/tokens.css`. Tailwind classes consume them via `(--token-name)` bracket syntax.

### §2.1 Colour — dark theme

```css
:root {
  /* Surfaces */
  --color-bg:             #0b1220;   /* page background — deepest */
  --color-surface:        #111a2c;   /* cards, panels */
  --color-surface-2:      #1a2438;   /* nested surfaces, table headers */
  --color-surface-3:      #1f2a3e;   /* hover states on surface */
  --color-border:         #2a3650;   /* subtle borders */
  --color-border-strong:  #3a4870;   /* emphasized borders */

  /* Text — 3 tiers */
  --color-text:           #e2e8f0;   /* slate-200 — primary values, headings */
  --color-text-secondary: #94a3b8;   /* slate-400 — column headers, labels, descriptions */
  --color-text-muted:     #64748b;   /* slate-500 — ISINs, row numbers, metadata */

  /* Semantic — financial */
  --color-profit:         #10b981;   /* emerald-500 — gains, buy, uptrend */
  --color-profit-bg:      #064e3b;   /* emerald-900 — tinted highlight */
  --color-loss:           #ef4444;   /* red-500 — losses, sell, downtrend */
  --color-loss-bg:        #7f1d1d;   /* red-900 — tinted highlight */
  --color-neutral:        #64748b;   /* slate-500 — flat / no change */
  --color-warning:        #f59e0b;   /* amber-500 — pending, caution */
  --color-info:           #3b82f6;   /* blue-500 — informational */

  /* Brand / interactive accent */
  --color-accent:         #6366f1;   /* indigo-500 — primary buttons, focus rings */
  --color-accent-hover:   #818cf8;   /* indigo-400 */
}
```

### §2.2 Colour — light theme

```css
[data-theme="light"] {
  --color-bg:             #f8fafc;
  --color-surface:        #ffffff;
  --color-surface-2:      #f1f5f9;
  --color-surface-3:      #e2e8f0;
  --color-border:         #cbd5e1;
  --color-border-strong:  #94a3b8;

  --color-text:           #0f172a;   /* slate-900 */
  --color-text-secondary: #475569;   /* slate-600 */
  --color-text-muted:     #94a3b8;   /* slate-400 */

  --color-profit:         #059669;   /* emerald-600 — darker for white-bg contrast */
  --color-profit-bg:      #d1fae5;   /* emerald-100 */
  --color-loss:           #dc2626;   /* red-600 */
  --color-loss-bg:        #fee2e2;   /* red-100 */
  --color-warning:        #d97706;
  --color-info:           #2563eb;
  --color-accent:         #4f46e5;   /* indigo-600 */
}
```

### §2.3 Typography scale

Use only these sizes. Pick the one whose intent matches.

| Token / Tailwind class | Size | Weight | Use case |
|---|---|---|---|
| `text-2xl font-semibold` | 24px | 600 | Page titles |
| `text-xl font-semibold` | 20px | 600 | Card titles, section headers |
| `text-lg font-medium` | 18px | 500 | Sub-section headers, modal titles |
| `text-base` | 16px | 400 | Body, primary values |
| `text-sm` | 14px | 400 | Dense table cells, descriptions |
| `text-xs font-semibold uppercase tracking-wider` | 12px | 600 | Table column headers — always this exact combo |
| `text-xs` | 12px | 400 | Metadata, ISINs, timestamps |
| `text-[10px]` | 10px | 500 | Badges, pills (use sparingly) |

Font family: system sans for everything (`font-sans` via Tailwind config). Tabular numerics inherited from body globally.

### §2.4 Spacing scale

Tailwind defaults are fine but stay disciplined. Allowed: `gap-1` (4px), `gap-2` (8px), `gap-3` (12px), `gap-4` (16px), `gap-6` (24px), `gap-8` (32px). **Do not mix `gap-3` and `gap-5` in the same layout** — pick a rhythm.

Per-context rhythm:
- Tight dense table cells: `p-2` (8px)
- Card interior padding: `p-4` (16px) for normal, `p-6` (24px) for hero/feature cards
- Stack between sections on a page: `gap-4` or `gap-6`
- Stack inside a card: `gap-3`

### §2.5 Border radius

| Class | Value | Use |
|---|---|---|
| `rounded-sm` | 4px | Pills, mini-chips |
| `rounded-md` | 6px | `xs`/`sm` buttons, inputs, small badges |
| `rounded-lg` | 8px | Default buttons, cards, panels |
| `rounded-xl` | 12px | Large cards, modal dialogs |
| `rounded-2xl` | 16px | Hero sections only — used sparingly |
| `rounded-full` | full | Avatars, circular icon buttons |

**Pill effect rule:** any button shorter than `h-8` (32px) must use `rounded-md`, never `rounded-lg` (causes a toy-like pill that doesn't match the dense financial aesthetic).

### §2.6 Z-index hierarchy

Use these — never raw numbers like `z-50`.

| Token | Value | Use |
|---|---|---|
| `z-0` | 0 | Base |
| `z-10` | 10 | Sticky table headers, sticky page headers |
| `z-20` | 20 | Dropdowns, popovers, comboboxes |
| `z-30` | 30 | Tooltips |
| `z-40` | 40 | Modals, dialogs, sheets |
| `z-50` | 50 | Toasts, notifications |
| `z-[60]` | 60 | Command palette / global overlays only |

Floating panels that open from inside `<main>` must use `createPortal` to escape stacking contexts — never just bump z-index.

### §2.7 Transitions

Allowed durations: `duration-150` (150ms — colour/opacity), `duration-200` (200ms — transforms), `duration-250` (250ms — tick flash). **No 300ms+ transitions anywhere.**

Allowed easings: `ease-out` (default), `ease-in-out` (for two-way state).

Banned: `animate-bounce`, `animate-pulse` on anything except `<Skeleton>`, any spring or elastic easing, `transition-all` on tables (causes flicker on tick updates).

---

## §3 — Numbers, currency, percentages

This is the section most easily violated and most damaging when it is.

### §3.1 Global tabular numbers

In `tokens.css` or `globals.css`:

```css
html {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
```

That's it. Once set, every digit is the same width, columns of numbers align, and the eye can scan.

### §3.2 The `lib/format.ts` utility — single source of truth

Every number rendered to the user goes through this:

```ts
// frontend/src/lib/format.ts

const INR_NUM = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
});

const INR_INT = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
});

const INR_CURRENCY = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

/** "1,23,456.78" — no symbol */
export const formatINR = (n: number) => INR_NUM.format(n);

/** "1,23,456" — integer (lot sizes, share counts) */
export const formatInt = (n: number) => INR_INT.format(n);

/** "₹1,23,456.78" — with INR symbol */
export const formatCurrency = (n: number) => INR_CURRENCY.format(n);

/** Compact: "1.52 Cr" / "23.45 L" / "9,234.56" */
export const formatLakh = (n: number) => {
  const abs = Math.abs(n);
  if (abs >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `${(n / 1e5).toFixed(2)} L`;
  return INR_NUM.format(n);
};

/** "+2.34%" / "-1.12%" — signed by default */
export const formatPct = (n: number, opts?: { signed?: boolean }) => {
  const signed = opts?.signed ?? true;
  const sign = signed && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
};

/** "▲ +2.34%" / "▼ -1.12%" / "— 0.00%" — directional */
export const formatChange = (n: number) => {
  const epsilon = 0.005;
  if (n > epsilon) return `▲ +${n.toFixed(2)}%`;
  if (n < -epsilon) return `▼ ${n.toFixed(2)}%`;
  return `— 0.00%`;
};
```

Anywhere you see a raw number being rendered, audit. The grep:

```bash
grep -rE "₹\s*\{|toFixed\(|\.toString\(\)|\$\{[a-zA-Z_]+\.(ltp|price|change|pnl|qty)\}" frontend/src/features/
```

Every hit should route through `format.ts`.

### §3.3 Sign and direction

Profit and loss numbers always show the sign. `+2.34%` not `2.34%`. `-₹1,234` not `₹-1,234`. This is what `formatPct` and `formatCurrency` do already if you pass the signed number.

For directional change cells, prefer `formatChange()` so you get the glyph for free — see §5.2.

---

## §4 — Tables

Trading apps live in tables. Every detail matters.

### §4.1 Structure

```tsx
<Table>
  <TableHeader>   {/* sticky, opaque, semibold uppercase tracked headers */}
    <TableRow>
      <TableHead>Symbol</TableHead>
      <TableHead numeric>LTP</TableHead>
      <TableHead numeric>Change %</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>      {/* rows with bottom border, hover background */}
    {rows.map(r => (
      <TableRow key={r.id}>
        <TableCell>{r.symbol}</TableCell>
        <TableCell numeric>{formatCurrency(r.ltp)}</TableCell>
        <TableCell numeric className={r.change >= 0 ? "text-(--color-profit)" : "text-(--color-loss)"}>
          {formatChange(r.change)}
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

### §4.2 TableHeader — required classes

```tsx
// Inside table.tsx
<thead className="sticky top-0 z-10 bg-(--color-surface-2) border-b border-(--color-border)">
```

The bg must be **opaque** — never `/80` or `/50` opacity. Rows must scroll *behind* it cleanly.

### §4.3 TableHead — column header typography

```tsx
const TableHead = ({ className, numeric, ...props }) => (
  <th
    className={cn(
      "h-10 px-2 align-middle whitespace-nowrap",
      "text-xs font-semibold uppercase tracking-wider",
      "text-(--color-text-secondary)",
      numeric && "text-right",
      className
    )}
    {...props}
  />
);
```

### §4.4 TableRow — borders and hover

```tsx
const TableRow = ({ className, ...props }) => (
  <tr
    className={cn(
      "border-b border-(--color-border)",
      "hover:bg-(--color-surface-3)",
      "transition-colors duration-150 ease-out",
      className
    )}
    {...props}
  />
);
```

Plus the existing TableBody class `[&_tr:last-child]:border-0` to suppress the last row's border.

### §4.5 TableCell — numeric variant

```tsx
const TableCell = ({ className, numeric, ...props }) => (
  <td
    className={cn(
      "p-2 align-middle",
      numeric && "text-right tabular-nums",
      className
    )}
    {...props}
  />
);
```

### §4.6 Density modes

Two modes. Pass via context or prop on `<Table>`.

| Mode | Row height | Padding | Use |
|---|---|---|---|
| `comfortable` | 40px (`h-10`) | `p-2` | Default — readable, easier hover targets |
| `compact` | 28px (`h-7`) | `px-2 py-1` | Power users scanning 100+ rows |

Don't introduce a third "spacious" mode. Two is plenty.

### §4.7 Sortable columns

When a column is sortable:
- Header cursor: `cursor-pointer hover:text-(--color-text)`
- Inline arrow icon (lucide `ChevronUp` / `ChevronDown` 12px) appears for the active sort column only
- Inactive sortable columns show no icon but reveal a dim `ChevronsUpDown` on header hover

### §4.8 Empty and loading states

- Empty: full-table-width row with centred `<EmptyState icon message description action />` component
- Loading: 8–12 `<SkeletonRow />` matching column structure — never collapse the table to a "Loading..." string

### §4.9 Large lists — virtualization

If a table renders more than 200 rows of live-updating data, use `@tanstack/react-virtual`. Decision point: WebSocket-pushed signals dashboard yes; static stock master no.

---

## §5 — Colour semantics

### §5.1 Profit / loss

Always via tokens. The only acceptable usage:

```tsx
className={value >= 0 ? "text-(--color-profit)" : "text-(--color-loss)"}
```

For backgrounds (e.g., tick flash, status pill fill):
```tsx
className={value >= 0 ? "bg-(--color-profit-bg)" : "bg-(--color-loss-bg)"}
```

Banned everywhere in `frontend/src/features/`:
```
text-green-*, text-red-*, text-emerald-*, text-rose-*
bg-green-*, bg-red-*, bg-emerald-*, bg-rose-*
```

The grep audit:
```bash
grep -rE "(text|bg)-(green|red|emerald|rose|lime|orange)-(300|400|500|600|700|800|900)" frontend/src/features/
```
Must return zero results.

### §5.2 Never colour alone

Every direction/state cell pairs colour with a glyph or icon. Examples:

```tsx
// ✅ good
<span className={cls}>▲ +2.34%</span>
<span className={cls}><ArrowUpRight className="inline w-3 h-3" /> +2.34%</span>

// ❌ bad
<span className="text-(--color-profit)">+2.34%</span>
```

`formatChange()` gives you the glyph automatically.

For BUY/SELL signal badges:

```tsx
<StatusPill kind={signal.direction.toLowerCase()}>
  {signal.direction === "BUY" ? "↑ BUY" : "↓ SELL"}
</StatusPill>
```

### §5.3 Status colour map

| Status | Token | Icon |
|---|---|---|
| `active` | `--color-info` | `Circle` (filled, animated pulse opt) |
| `pending` | `--color-warning` | `Clock` |
| `filled` / `hit_tp` | `--color-profit` | `CheckCircle2` |
| `rejected` / `hit_sl` | `--color-loss` | `XCircle` |
| `expired` | `--color-text-muted` | `MinusCircle` |
| `cancelled` | `--color-text-muted` | `Ban` |

Implemented as the `<StatusPill>` component — never hand-rolled.

### §5.4 Index badge colours

Defined once in `globals.css`:

```css
@layer components {
  .badge-n50  { @apply bg-blue-950   text-blue-300   border border-blue-800; }
  .badge-bn   { @apply bg-purple-950 text-purple-300 border border-purple-800; }
  .badge-fn   { @apply bg-teal-950   text-teal-300   border border-teal-800; }
  .badge-fno  { @apply bg-amber-950  text-amber-300  border border-amber-800; }
}
```

Used as: `<Badge className="badge-n50">N50</Badge>`. Never hardcode the colour triplet again.

---

## §6 — Tables (extended — see §4)

(Section reserved for future expansion: column resizing, column pinning, multi-sort.)

---

## §7 — Real-time feedback

### §7.1 Tick flash on price update

`<PriceCell>` component diffs the previous value via `useRef` and toggles a class for 250ms:

```tsx
// up tick:   bg-(--color-profit-bg)/40, removes after 250ms
// down tick: bg-(--color-loss-bg)/40,   removes after 250ms
// no change: nothing
```

Use everywhere a live (WebSocket-pushed) price renders. EOD/historical prices use plain `<TableCell>`.

### §7.2 Skeleton loaders

Every `if (isLoading) return ...` returns skeleton shapes matching final layout:

```tsx
// ✅ good
if (isLoading) return <StocksTableSkeleton rows={10} />;

// ❌ bad
if (isLoading) return <div>Loading...</div>;
```

`<Skeleton>` is the shadcn primitive. Compose it into context-specific skeletons:
- `<SkeletonTableRow columns={5} />`
- `<SkeletonCard />`
- `<SkeletonChart />`

### §7.3 Toasts

- Position: top-right, stacked, max 3 visible
- Duration: 5s default, sticky for errors
- Variants: `success` (profit colour), `error` (loss colour), `warning`, `info`
- Component: `<Toast>` from shadcn/sonner — never hand-rolled

### §7.4 Optimistic updates

For actions where the round-trip is ≤300ms (placing an order, toggling a watchlist), apply the change immediately to UI, mark the row as `data-optimistic` with a slight opacity, and revert on error with a toast.

---

## §8 — Components & forms

### §8.1 Banned raw elements (in `frontend/src/features/`)

| Banned | Use instead |
|---|---|
| `<button>` | `<Button>` from `@/components/ui/button` |
| `<input>` (text) | `<Input>` |
| `<input type="checkbox">` | `<Checkbox>` |
| `<input type="radio">` | `<RadioGroup>` + `<RadioGroupItem>` |
| `<input type="range">` | `<Slider>` |
| `<select>` | `<Select>` with `<SelectTrigger>` / `<SelectContent>` |
| `<textarea>` | `<Textarea>` |
| `<dialog>` | `<Dialog>` |

Exceptions are allowed only inside `@/components/ui/*` (the primitive layer).

### §8.2 Button sizes and radii

| Size | Height | Padding | Radius |
|---|---|---|---|
| `xs` | `h-6` (24px) | `px-2` | `rounded-md` |
| `sm` | `h-8` (32px) | `px-3` | `rounded-md` |
| default | `h-9` (36px) | `px-4` | `rounded-lg` |
| `lg` | `h-11` (44px) | `px-6` | `rounded-lg` |

### §8.3 Button variants — explicit text colour

`outline` and `ghost` variants must declare their text colour explicitly. The base `<Button>` defaults are not enough:

```tsx
outline: "border border-(--color-border) bg-transparent text-(--color-text-secondary) hover:bg-(--color-surface-2) hover:text-(--color-text)"
ghost:   "bg-transparent text-(--color-text-secondary) hover:bg-(--color-surface-2) hover:text-(--color-text)"
```

### §8.4 Forms

- Labels via `<Label>` component, never raw `<label>` in features
- Validation errors via `<FormMessage>` styled with `text-(--color-loss)`
- Field gap: `gap-2` within a field group, `gap-4` between field groups
- Submit button row: right-aligned, `gap-2`, primary action rightmost

---

## §9 — Layout

### §9.1 Page-level scaffolding

Every feature page uses this shape:

```tsx
export default function FeaturePage() {
  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header — title + actions */}
      <div className="flex-shrink-0 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-(--color-text)">Page Title</h1>
        <div className="flex items-center gap-2">{/* actions */}</div>
      </div>

      {/* Optional filter strip */}
      <div className="flex-shrink-0 rounded-lg border border-l-2 border-(--color-border) border-l-(--color-accent)/40 bg-(--color-surface-2) p-3">
        {/* filters */}
      </div>

      {/* Main content — fills remaining height, scrolls independently */}
      <div className="flex-1 min-h-0 rounded-lg border border-(--color-border) bg-(--color-surface) overflow-hidden">
        <div className="h-full overflow-auto">
          {/* table / chart / content */}
        </div>
      </div>
    </div>
  );
}
```

Key rules:
- Root: `h-full flex flex-col` — never `space-y-*` on a viewport-filling page
- Fixed regions: `flex-shrink-0`
- Scrollable region: `flex-1 min-h-0 overflow-hidden` containing an inner `overflow-auto h-full`
- Filter strip gets a left-accent border for visual identity

### §9.2 Card pattern

```tsx
<div className="rounded-lg border border-(--color-border) bg-(--color-surface) p-4">
  {/* content */}
</div>
```

Nested cards: use `bg-(--color-surface-2)`. Never opacity-tinted surface backgrounds.

### §9.3 Two-column dashboard pattern

When a page has a sidebar (saved screens, watchlist, etc.) and a main panel:

```tsx
<div className="h-full flex flex-col gap-4">
  <Header />
  <div className="flex-1 min-h-0 grid grid-cols-[260px_1fr] gap-4 overflow-hidden">
    <aside className="h-full overflow-y-auto">{/* sidebar */}</aside>
    <main className="h-full flex flex-col overflow-hidden">{/* main */}</main>
  </div>
</div>
```

---

## §10 — Keyboard & focus

### §10.1 Focus rings

Every interactive element renders a visible ring on `:focus-visible`:

```css
focus-visible:outline-none
focus-visible:ring-2
focus-visible:ring-(--color-accent)
focus-visible:ring-offset-2
focus-visible:ring-offset-(--color-bg)
```

Set this in the base `<Button>`, `<Input>`, `<Select>`, etc. so it propagates.

### §10.2 Global keyboard shortcuts

| Shortcut | Action |
|---|---|
| `/` | Focus the global search |
| `Esc` | Close modal/popover, or blur search |
| `g` then `d` | Go to Dashboard |
| `g` then `s` | Go to Signals |
| `g` then `w` | Go to Watchlist |
| `g` then `j` | Go to Journal |
| `?` | Open keyboard shortcut cheat-sheet |

Implement once globally via `useHotkeys` (react-hotkeys-hook).

### §10.3 Table row navigation

In tables of signals/positions/orders:
- `↑` / `↓` move highlighted row (keyboard focus visual)
- `Enter` opens detail
- `Esc` clears selection

Encapsulate in `useTableKeyboardNav` hook used by all data tables.

---

## §11 — Animation discipline

Trading users want their UI to feel fast and trustworthy. Bouncy or delightful animations work against that.

### §11.1 Allowed

- Colour and opacity transitions: `transition-colors duration-150 ease-out`
- Hover lifts: `hover:translate-y-[-1px] transition-transform duration-150`
- Tick flash: 250ms bg colour decay
- Skeleton shimmer (CSS gradient animation, infinite)
- Slide-in/out for sheets and toasts: max 200ms `ease-out`

### §11.2 Banned

- `animate-bounce` anywhere except a deliberate "attention" badge (rare)
- `animate-pulse` outside `<Skeleton>`
- Spring or elastic easings
- `transition-all` on tables or list rows (causes flicker on data updates)
- Any animation longer than 250ms in feature code
- Decorative motion (confetti, particle effects, etc.)

---

## §12 — Anti-patterns gallery

Read once, internalize. Each pattern below has appeared in real code somewhere.

### §12.1 Numbers

```tsx
// ❌ wrong
<span>₹{stock.ltp.toFixed(2)}</span>
<span>{stock.changePct > 0 ? "+" : ""}{stock.changePct}%</span>
<span>{Math.round(stock.volume / 100000)} L</span>

// ✅ right
<span>{formatCurrency(stock.ltp)}</span>
<span>{formatPct(stock.changePct)}</span>
<span>{formatLakh(stock.volume)}</span>
```

### §12.2 Colours

```tsx
// ❌ wrong
<span className="text-green-500">+2.34%</span>
<span className="text-red-500">-1.12%</span>
<div className="bg-green-500/20 text-green-300">PROFIT</div>

// ✅ right
<span className="text-(--color-profit)">▲ +2.34%</span>
<span className="text-(--color-loss)">▼ -1.12%</span>
<StatusPill kind="filled">PROFIT</StatusPill>
```

### §12.3 Direction by colour alone

```tsx
// ❌ wrong — colour-blind users miss this
<td className={change > 0 ? "text-green-500" : "text-red-500"}>
  {change.toFixed(2)}%
</td>

// ✅ right — colour + glyph
<td className={cn("tabular-nums text-right",
                  change > 0 ? "text-(--color-profit)" : "text-(--color-loss)")}>
  {formatChange(change)}
</td>
```

### §12.4 Loading states

```tsx
// ❌ wrong
{isLoading ? <p>Loading stocks...</p> : <StocksTable data={data} />}

// ✅ right
{isLoading ? <StocksTableSkeleton rows={10} /> : <StocksTable data={data} />}
```

### §12.5 Raw elements

```tsx
// ❌ wrong
<button onClick={onClick} className="px-3 py-1 bg-indigo-600 rounded">Save</button>
<select value={v} onChange={e => setV(e.target.value)}>...</select>
<input type="checkbox" checked={c} onChange={e => setC(e.target.checked)} />

// ✅ right
<Button onClick={onClick}>Save</Button>
<Select value={v} onValueChange={setV}>...</Select>
<Checkbox checked={c} onCheckedChange={setC} />
```

### §12.6 Opacity on solid surfaces

```tsx
// ❌ wrong — solid card with /50 opacity reads grey, fails contrast
<div className="bg-(--color-surface)/50 border">...</div>

// ✅ right — use a dedicated surface token
<div className="bg-(--color-surface-2) border border-(--color-border)">...</div>
```

### §12.7 Page layout drift

```tsx
// ❌ wrong — full-page scroll, no viewport fill
<div className="space-y-5">
  <Header />
  <FilterBar />
  <Table />  {/* scrolls page, not itself */}
</div>

// ✅ right — viewport fill, table scrolls independently
<div className="h-full flex flex-col gap-4">
  <Header />
  <FilterBar />
  <div className="flex-1 min-h-0 overflow-hidden">
    <TableWrapper className="h-full overflow-auto">
      <Table />
    </TableWrapper>
  </div>
</div>
```

### §12.8 Mixed spacing rhythm

```tsx
// ❌ wrong — gap-3, gap-5, gap-7 in the same component
<div className="space-y-3"> <X />
  <div className="gap-5"> <Y /> </div>
  <div className="space-y-7"> <Z /> </div>
</div>

// ✅ right — one rhythm
<div className="space-y-4">
  <X />
  <div className="gap-4"><Y /></div>
  <div className="space-y-4"><Z /></div>
</div>
```

### §12.9 Hardcoded z-index numbers

```tsx
// ❌ wrong
<div style={{ zIndex: 9999 }}>...</div>
<div className="z-[100]">...</div>

// ✅ right — use the documented scale (§2.6)
<div className="z-40">...</div>  // modal
<div className="z-50">...</div>  // toast
```

### §12.10 Missing focus rings

```tsx
// ❌ wrong — keyboard users have no idea where they are
<button className="px-3 py-1 hover:bg-slate-700">...</button>

// ✅ right — visible ring on focus-visible
<Button>...</Button>  // ring built into the primitive
```

---

## §13 — Pre-commit checklist

Run all of these before opening a PR or pushing to main. Automate where possible.

### §13.1 Grep audits — must return zero hits in `frontend/src/features/`

```bash
# Raw banned elements
grep -rE "<(button|select|input|textarea)[ >]" frontend/src/features/

# Raw colour utilities (use tokens instead)
grep -rE "(text|bg)-(green|red|emerald|rose|lime)-(300|400|500|600|700|800|900)" frontend/src/features/

# Unformatted prices/percentages
grep -rE "\.toFixed\(2\)\s*\+\s*['\"]%|₹\s*\{[a-zA-Z_]+(\.[a-zA-Z_]+)?\}" frontend/src/features/

# Loading text strings
grep -rE "<(div|p|span)[^>]*>Loading\.{0,3}<" frontend/src/features/

# Opacity on solid surface tokens (paren = live v4 form; bracket = dead
# pre-v4 form — any bracket hit is a regression to syntax that renders
# as NOTHING, see the 2026-07-11 migration in the phase-3 ledger)
grep -rE "bg-[\[(]--color-(surface|bg|sidebar|topbar|row-alt)[^)\]]*[\])]/[0-9]" frontend/src/features/
grep -rE -- "-\[--color-" frontend/src/

# Hardcoded z-index
grep -rE "z-\[[0-9]+\]" frontend/src/features/
```

### §13.2 Visual sweep

Open each of these in the browser and verify:

- [ ] Stocks page: prices align column-wise (tabular nums working)
- [ ] Stocks page: scroll down — header stays opaque, rows don't ghost through
- [ ] Signals page: every gain/loss has a ▲/▼ or arrow icon
- [ ] Signals page: clicking a signal opens detail without z-index conflict
- [ ] Dashboard: skeleton loaders appear before live data, not "Loading..."
- [ ] Journal: long company names truncate cleanly with title attribute
- [ ] Tab key: navigates through interactive elements, ring is always visible
- [ ] Light theme: switch and re-verify all of the above; nothing reads white-on-white

### §13.3 Automated checks

```bash
npm run typecheck --prefix frontend
npm run lint --prefix frontend
npm test --prefix frontend
```

All three must be clean.

### §13.4 Sanity test in narrow viewport

Resize browser to 375px wide. Stocks and Signals pages must render usably (cards may stack, table may scroll horizontally). Not pretty but not broken.

---

## §14 — When in doubt

When a design question isn't answered here:

1. Find the closest existing pattern in `frontend/src/features/stocks/` (the most-polished feature)
2. If still unclear, propose two alternatives with trade-offs to the user before implementing
3. If you settle on a new pattern, add it to this doc in the same PR

Never invent a new pattern silently.

---

## §15 — Multi-theme system

We ship four themes. Each is a finance-context fit, not a brand expression.

### §15.1 The four themes

| Theme | Vibe | When it shines |
|---|---|---|
| `midnight` (default) | Deep navy with cyan accents | Default. Mid-day, sustained focus. |
| `carbon` | True black with amber, CRT-style green/red | Night sessions. Bloomberg Terminal feel. |
| `ocean` | Dark teal with mint | Calmer alternative to midnight. Long days. |
| `daybreak` | Clean off-white with indigo | Daylight, presenting to others, screenshots. |

Theme is set via `data-theme="..."` on `<html>`. Default attribute on first paint comes from `localStorage["theme"] ?? "midnight"` to avoid flash.

### §15.2 Full token sets

Add to `frontend/src/styles/tokens.css`:

```css
/* ───── MIDNIGHT (default dark) ───── */
:root, [data-theme="midnight"] {
  --color-bg:             #0a0f1c;
  --color-surface:        #0f172a;
  --color-surface-2:      #182338;
  --color-surface-3:      #1f2d47;
  --color-border:         #1e293b;   /* MORE SUBTLE than v1 — fixes 'whitish' complaint */
  --color-border-strong:  #334155;

  --color-text:           #e2e8f0;
  --color-text-secondary: #94a3b8;
  --color-text-muted:     #64748b;

  --color-profit:         #10b981;
  --color-profit-bg:      #022c22;
  --color-loss:           #ef4444;
  --color-loss-bg:        #450a0a;
  --color-neutral:        #64748b;
  --color-warning:        #f59e0b;
  --color-warning-bg:     #451a03;
  --color-info:           #3b82f6;
  --color-info-bg:        #172554;

  --color-accent:         #06b6d4;   /* cyan — primary brand */
  --color-accent-hover:   #22d3ee;
  --color-accent-bg:      #083344;
}

/* ───── CARBON (Bloomberg-inspired) ───── */
[data-theme="carbon"] {
  --color-bg:             #000000;
  --color-surface:        #0a0a0a;
  --color-surface-2:      #141414;
  --color-surface-3:      #1f1f1f;
  --color-border:         #1f1f1f;
  --color-border-strong:  #3f3f3f;

  --color-text:           #fafafa;
  --color-text-secondary: #a3a3a3;
  --color-text-muted:     #737373;

  --color-profit:         #22c55e;
  --color-profit-bg:      #052e16;
  --color-loss:           #ef4444;
  --color-loss-bg:        #450a0a;
  --color-warning:        #f59e0b;
  --color-info:           #fb923c;

  --color-accent:         #f59e0b;   /* amber — terminal classic */
  --color-accent-hover:   #fbbf24;
  --color-accent-bg:      #451a03;
}

/* ───── OCEAN (dark teal) ───── */
[data-theme="ocean"] {
  --color-bg:             #0c1c1f;
  --color-surface:        #11272b;
  --color-surface-2:      #173238;
  --color-surface-3:      #1e4046;
  --color-border:         #1d3a40;
  --color-border-strong:  #2a5760;

  --color-text:           #d1fae5;
  --color-text-secondary: #6ee7b7;
  --color-text-muted:     #4ade80;

  --color-profit:         #34d399;
  --color-profit-bg:      #064e3b;
  --color-loss:           #fb7185;
  --color-loss-bg:        #4c0519;
  --color-warning:        #fbbf24;
  --color-info:           #38bdf8;

  --color-accent:         #2dd4bf;   /* teal */
  --color-accent-hover:   #5eead4;
  --color-accent-bg:      #134e4a;
}

/* ───── DAYBREAK (light) ───── */
[data-theme="daybreak"] {
  --color-bg:             #f8fafc;
  --color-surface:        #ffffff;
  --color-surface-2:      #f1f5f9;
  --color-surface-3:      #e2e8f0;
  --color-border:         #e2e8f0;
  --color-border-strong:  #cbd5e1;

  --color-text:           #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted:     #94a3b8;

  --color-profit:         #059669;
  --color-profit-bg:      #d1fae5;
  --color-loss:           #dc2626;
  --color-loss-bg:        #fee2e2;
  --color-warning:        #d97706;
  --color-info:           #2563eb;

  --color-accent:         #4f46e5;   /* indigo */
  --color-accent-hover:   #6366f1;
  --color-accent-bg:      #eef2ff;
}
```

### §15.3 Theme switcher UI

In Appearance Settings, replace the binary Dark/Light toggle with a 4-card grid showing the theme's actual background + accent preview:

```tsx
const themes = [
  { id: "midnight", label: "Midnight", desc: "Deep navy · cyan", bgPreview: "#0a0f1c", accentPreview: "#06b6d4" },
  { id: "carbon",   label: "Carbon",   desc: "Pure black · amber",  bgPreview: "#000000", accentPreview: "#f59e0b" },
  { id: "ocean",    label: "Ocean",    desc: "Dark teal · mint",    bgPreview: "#0c1c1f", accentPreview: "#2dd4bf" },
  { id: "daybreak", label: "Daybreak", desc: "Light · indigo",      bgPreview: "#f8fafc", accentPreview: "#4f46e5" },
];
```

Each card: 160×100, accent border on selected, click sets `document.documentElement.dataset.theme = id` and writes localStorage.

---

## §16 — Typography: continuous slider + finance font stack

### §16.1 Font size slider

Replace the three discrete buttons (Small/Medium/Large) with a continuous Slider plus preset chips.

Component spec:

```tsx
// frontend/src/features/settings/FontSizeControl.tsx
const PRESETS = [
  { label: "Compact",     px: 13 },
  { label: "Default",     px: 15 },
  { label: "Comfortable", px: 17 },
  { label: "Large",       px: 19 },
  { label: "X-Large",     px: 21 },
];

<div className="space-y-4">
  {/* Live preview pane */}
  <div className="rounded-lg border border-(--color-border) bg-(--color-surface-2) p-4"
       style={{ fontSize: `${size}px` }}>
    Preview: RELIANCE INFY TCS — ₹2,345.50 +1.2% BUY signal
  </div>

  {/* Slider */}
  <div className="flex items-center gap-4">
    <span className="text-xs text-(--color-text-muted)" style={{ fontSize: 11 }}>A</span>
    <Slider min={12} max={22} step={1} value={[size]} onValueChange={([v]) => setSize(v)} className="flex-1" />
    <span className="text-base text-(--color-text)" style={{ fontSize: 22 }}>A</span>
    <span className="w-12 text-right tabular-nums text-sm text-(--color-text-secondary)">
      {size}px
    </span>
  </div>

  {/* Preset chips */}
  <div className="flex flex-wrap gap-2">
    {PRESETS.map(p => (
      <Button key={p.label}
              variant={size === p.px ? "default" : "outline"}
              size="xs"
              onClick={() => setSize(p.px)}>
        {p.label} <span className="ml-1 text-[10px] opacity-70">{p.px}px</span>
      </Button>
    ))}
  </div>
</div>
```

Persistence: localStorage key `ui-font-size`. Applied via:

```css
:root { font-size: var(--ui-font-size, 15px); }
```

And on bootstrap:
```ts
document.documentElement.style.setProperty(
  "--ui-font-size",
  `${localStorage.getItem("ui-font-size") ?? 15}px`
);
```

### §16.2 Split font system — UI font vs numeric font

Numbers in finance UIs deserve their own font. We expose two independent selections.

**UI fonts** (sidebars, headings, body text):

| Font | Best for | Weight range |
|---|---|---|
| Inter | Default. Neutral, well-tested | 400–700 |
| Geist | Modern geometric, slightly futuristic | 400–600 |
| IBM Plex Sans | Institutional, trustworthy | 400–600 |
| Roboto | Google's neutral, very readable at small sizes | 400–500 |

**Numeric fonts** (prices, P&L, all numbers in tables):

| Font | Best for |
|---|---|
| JetBrains Mono | Dev-grade tabular, sharp ones/zeros |
| IBM Plex Mono | Pairs with IBM Plex Sans |
| Roboto Mono | Pairs with Roboto |
| Inter (tabular) | Just use Inter's tabular variant for unified look |

Tokens:

```css
:root {
  --font-ui:  'Inter', system-ui, sans-serif;
  --font-num: 'JetBrains Mono', ui-monospace, monospace;
}
```

CSS usage:

```css
html { font-family: var(--font-ui); font-variant-numeric: tabular-nums; }
.tabular, [data-numeric] { font-family: var(--font-num); }
```

Tailwind utility shortcut: use `font-num` everywhere a price renders. Add to tailwind.config:

```js
fontFamily: {
  ui:  ['var(--font-ui)'],
  num: ['var(--font-num)'],
}
```

### §16.3 Loading fonts

Use `@fontsource` packages for self-hosted, offline-safe loading:

```bash
npm i @fontsource/inter @fontsource/geist @fontsource-variable/jetbrains-mono \
      @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono \
      @fontsource/roboto @fontsource/roboto-mono
```

Import in `main.tsx`:

```ts
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource-variable/jetbrains-mono';
// …others as needed
```

### §16.4 Settings UI

The font section in Appearance Settings becomes two side-by-side selects (or radio grids):

```
┌─ UI Font ────────────────┐ ┌─ Numeric Font ───────────────┐
│  ● Inter                 │ │  ● JetBrains Mono            │
│  ○ Geist                 │ │  ○ IBM Plex Mono             │
│  ○ IBM Plex Sans         │ │  ○ Roboto Mono               │
│  ○ Roboto                │ │  ○ Inter (tabular)           │
└──────────────────────────┘ └──────────────────────────────┘
Preview: Buy RELIANCE @ ₹2,345.50 — Qty 100, P&L +1,234.56
```

---

## §17 — Portal & z-index (hard rules, extended)

The previous attempt missed this — every dropdown still bleeds. Restate the rules with zero ambiguity.

### §17.1 The two failure modes

| Symptom | Root cause |
|---|---|
| Dropdown appears *behind* page content | Component nested in `overflow: hidden` parent, OR component does not use Portal |
| Dropdown background is transparent and text bleeds through | Content className uses opacity (`/50`, `/80`, etc.) on background |

### §17.2 Mandatory pattern

For **every** Select, DropdownMenu, Popover, Combobox, ContextMenu, HoverCard:

```tsx
// ✅ correct — Portal + opaque content + visible border + shadow
<DropdownMenu.Root>
  <DropdownMenu.Trigger asChild>
    <Button variant="ghost">...</Button>
  </DropdownMenu.Trigger>

  <DropdownMenu.Portal>
    <DropdownMenu.Content
      sideOffset={6}
      align="end"
      className={cn(
        "z-50",
        "min-w-[220px]",
        "bg-(--color-surface)",                         // SOLID — no /50 /80
        "border border-(--color-border-strong)",        // strong border, not subtle
        "rounded-lg",
        "shadow-2xl shadow-black/50",
        "p-1",
        "animate-in fade-in-0 zoom-in-95 duration-150"
      )}
    >
      {/* items */}
    </DropdownMenu.Content>
  </DropdownMenu.Portal>
</DropdownMenu.Root>
```

Hard rules:
1. **Always wrap Content in Portal.** Even if it seems to work without — it breaks the moment any ancestor gets `transform`, `filter`, `overflow:hidden`, or `position:fixed`.
2. **Background must be solid token.** Never `bg-card/50`, `bg-(--color-surface)/80`. Use `bg-(--color-surface)` flat.
3. **Border must use `--color-border-strong`** for floating panels. Subtle border on a floating panel looks "stuck to the page."
4. **Add shadow** — `shadow-2xl shadow-black/50` in dark themes — to lift the panel visually.
5. **`z-50` minimum.** Modals are `z-40`, dropdowns are `z-50` (sit above modal triggers but below modal scrim — adjust if you discover stacking conflicts).

### §17.3 Native `<select>` is banned

Cannot be styled, cannot use Portal. Any remaining native `<select>` in `frontend/src/features/` is a bug. Audit:

```bash
grep -rnE "<select[ >]" frontend/src/features/
```

Must return zero. Replace with `<Select>` from `@/components/ui/select`.

### §17.4 Profile dropdown specifically

The profile dropdown was the most visible failure. Reference implementation:

```tsx
// src/components/layout/UserMenu.tsx
<DropdownMenu.Root>
  <DropdownMenu.Trigger asChild>
    <Button variant="ghost" className="gap-2">
      <Avatar size="sm">{initial}</Avatar>
      <span className="text-sm">{user.name}</span>
      <ChevronDown className="w-3 h-3 opacity-60" />
    </Button>
  </DropdownMenu.Trigger>

  <DropdownMenu.Portal>
    <DropdownMenu.Content
      sideOffset={8}
      align="end"
      className="z-50 w-72 bg-(--color-surface) border border-(--color-border-strong) rounded-xl shadow-2xl shadow-black/50 p-2"
    >
      {/* user identity header */}
      <div className="px-3 py-3 border-b border-(--color-border) flex items-center gap-3">
        <Avatar size="md">{initial}</Avatar>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-(--color-text) truncate">{user.name}</div>
          <div className="text-xs text-(--color-text-secondary) truncate">{user.email}</div>
          <div className="flex gap-1 mt-1">
            <Badge variant="info">Admin</Badge>
            <Badge variant="warning">Paper Trading</Badge>
          </div>
        </div>
      </div>

      {/* menu items */}
      <DropdownMenu.Item className="px-3 py-2 rounded-md text-sm text-(--color-text-secondary) hover:bg-(--color-surface-2) hover:text-(--color-text) cursor-pointer flex items-center gap-2">
        <UserIcon className="w-4 h-4" /> My Profile
      </DropdownMenu.Item>
      <DropdownMenu.Item className="...">
        <SettingsIcon className="w-4 h-4" /> Appearance Settings
      </DropdownMenu.Item>
      <DropdownMenu.Separator className="my-1 h-px bg-(--color-border)" />
      <DropdownMenu.Item className="px-3 py-2 rounded-md text-sm text-(--color-loss) hover:bg-(--color-loss-bg)/40 cursor-pointer flex items-center gap-2">
        <LogOutIcon className="w-4 h-4" /> Sign out
      </DropdownMenu.Item>
    </DropdownMenu.Content>
  </DropdownMenu.Portal>
</DropdownMenu.Root>
```

This matches the BMN reference's profile menu visual quality.

---

## §18 — Login page patterns

### §18.1 Required elements

A login page must include:

1. **Brand identity** — logo or wordmark + tagline
2. **Show-password toggle** — eye/eye-off icon button, basic UX
3. **Visible feedback** — loading state on submit, clear error message slot
4. **Background interest** — not a flat color (see §18.3)

### §18.2 Show-password component

```tsx
// src/components/ui/PasswordInput.tsx
import { Eye, EyeOff } from 'lucide-react';

export function PasswordInput({ value, onChange, ...props }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <Input
        type={shown ? "text" : "password"}
        value={value}
        onChange={onChange}
        className="pr-10"
        {...props}
      />
      <button
        type="button"
        onClick={() => setShown(s => !s)}
        aria-label={shown ? "Hide password" : "Show password"}
        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-(--color-text-muted) hover:text-(--color-text) hover:bg-(--color-surface-2) transition-colors duration-150"
      >
        {shown ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}
```

### §18.3 Background — three approved patterns

Pick **one** per theme. Lightweight, CSS/SVG only — no large image downloads.

**Pattern A — Glow orbs + chart grid (recommended default)**

```css
.login-bg {
  position: relative;
  min-height: 100vh;
  background: var(--color-bg);
  overflow: hidden;
}
.login-bg::before {
  content: '';
  position: absolute; inset: 0;
  background:
    radial-gradient(circle at 18% 28%, color-mix(in srgb, var(--color-accent) 18%, transparent), transparent 45%),
    radial-gradient(circle at 82% 72%, color-mix(in srgb, var(--color-info) 14%, transparent), transparent 45%);
  pointer-events: none;
}
.login-bg::after {
  content: '';
  position: absolute; inset: 0;
  background-image:
    linear-gradient(to right, color-mix(in srgb, var(--color-text-muted) 8%, transparent) 1px, transparent 1px),
    linear-gradient(to bottom, color-mix(in srgb, var(--color-text-muted) 8%, transparent) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(circle at center, black 30%, transparent 75%);
  pointer-events: none;
}
```

**Pattern B — Candlestick SVG overlay (finance-themed)**

```tsx
<div className="login-bg">
  <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice">
    <g opacity="0.06" stroke="currentColor" strokeWidth="2" fill="none">
      {/* generate ~40 candlesticks across the canvas */}
      {Array.from({ length: 40 }, (_, i) => {
        const x = i * 50 + 20;
        const isGreen = (i * 7 + 3) % 5 < 3;
        const high = 200 + ((i * 13) % 600);
        const low  = high + 120 + ((i * 17) % 240);
        const open = high + ((i * 11) % (low - high - 20)) + 10;
        const close = isGreen ? low - 30 : high + 30;
        return (
          <g key={i} className={isGreen ? 'text-(--color-profit)' : 'text-(--color-loss)'}>
            <line x1={x} y1={high} x2={x} y2={low} />
            <rect x={x - 8} y={Math.min(open, close)} width={16} height={Math.abs(close - open)} />
          </g>
        );
      })}
    </g>
  </svg>
</div>
```

Pair with Pattern A for the richest effect: orbs + grid + faint candlesticks.

**Pattern C — Animated ticker tape (subtle data feel)**

A thin strip at the very top and bottom of the page running ticker symbols at opacity 0.08. Implementation note: pause animation when user focuses the form to avoid distraction.

### §18.4 Reference layout

```
┌────────────────────────────────────────────────────┐
│ [glow orbs + grid background]                      │
│                                                    │
│              ┌────────────────────────┐            │
│              │     ⚡ Brand Logo       │            │
│              │     PLATFORM NAME      │            │
│              │  tagline below logo    │            │
│              │                        │            │
│              │  Email                 │            │
│              │  [.......................]         │
│              │                        │            │
│              │  Password              │            │
│              │  [.................][👁] │           │
│              │                        │            │
│              │  ☐ Remember me         │            │
│              │                        │            │
│              │     [   Sign in   ]    │            │
│              │                        │            │
│              │   Trouble logging in?  │            │
│              └────────────────────────┘            │
│                                                    │
│                [candlestick SVG overlay opacity 6%]│
└────────────────────────────────────────────────────┘
```

### §18.5 What login MUST NOT include

- Public signup link or "Create account" CTA — users are admin-created only
- Social login buttons
- Marketing copy
- More than one CTA — just Sign In
- A hardcoded "default credentials" hint in production builds

---

## §19 — Table richness standards

This is what makes the difference between "intern table" and "MAANG financial dashboard table."

### §19.1 Column-specific styling

| Column type | Style |
|---|---|
| Row index (`#`) | `text-(--color-text-muted) text-xs tabular-nums w-12` |
| Symbol | `font-num font-semibold text-(--color-accent) tracking-wide` |
| Company name | `font-medium text-(--color-text)` |
| Industry / Sector | `text-(--color-text-secondary) text-sm` |
| Numeric (LTP, MktCap, Volume, Qty) | `font-num tabular-nums text-right` |
| Change % / P&L | `font-num tabular-nums text-right` + `--color-profit`/`--color-loss` + glyph |
| Status / Segment / Series badges | Status pill classes (see §19.3) |
| ISIN / metadata | `font-num text-xs text-(--color-text-muted)` |
| Actions | Ghost icon-buttons with per-action hover color (§19.4) |

### §19.2 Row design

Apply at TableRow base:
- Border bottom: `border-b border-(--color-border)`
- Last row no border: covered by existing `[&_tr:last-child]:border-0` selector
- Hover: `hover:bg-(--color-surface-2)` (do NOT use `bg-(--color-surface)/50` — opacity bug)
- Active row (e.g., focused for keyboard nav): `data-[selected]:bg-(--color-accent-bg)`
- Transition: `transition-colors duration-150`

### §19.3 Status pill component

```tsx
// src/components/ui/StatusPill.tsx
const variants = {
  active:   "bg-(--color-info-bg)    text-(--color-info)    border-(--color-info)/30",
  closed:   "bg-(--color-surface-3)  text-(--color-text-secondary) border-(--color-border)",
  profit:   "bg-(--color-profit-bg)  text-(--color-profit)  border-(--color-profit)/30",
  loss:     "bg-(--color-loss-bg)    text-(--color-loss)    border-(--color-loss)/30",
  open:     "bg-(--color-warning-bg) text-(--color-warning) border-(--color-warning)/30",
  pending:  "bg-(--color-warning-bg) text-(--color-warning) border-(--color-warning)/30",
  filled:   "bg-(--color-profit-bg)  text-(--color-profit)  border-(--color-profit)/30",
  rejected: "bg-(--color-loss-bg)    text-(--color-loss)    border-(--color-loss)/30",
  expired:  "bg-(--color-surface-3)  text-(--color-text-muted) border-(--color-border)",
};

export function StatusPill({ status, children, className }) {
  const cls = variants[status] ?? variants.closed;
  return (
    <span className={cn(
      "inline-flex items-center gap-1",
      "px-2 py-0.5 rounded-md border",
      "text-[11px] font-semibold uppercase tracking-wider",
      "font-num", // tabular feel
      cls,
      className
    )}>
      {children}
    </span>
  );
}
```

Use everywhere status is rendered — Stocks (active/inactive), Signals (active/expired/hit_tp/hit_sl), Orders (pending/filled/rejected), Journal (open/closed + profit/loss).

### §19.4 Action icon buttons

Three actions, three colors. Always icon-buttons in ghost variant.

```tsx
<div className="flex items-center justify-end gap-0.5">
  <Button variant="ghost" size="xs" className="hover:text-(--color-info)" aria-label="View">
    <Eye className="w-4 h-4" />
  </Button>
  <Button variant="ghost" size="xs" className="hover:text-(--color-accent)" aria-label="Edit">
    <Pencil className="w-4 h-4" />
  </Button>
  <Button variant="ghost" size="xs" className="hover:text-(--color-loss)" aria-label="Delete">
    <Trash2 className="w-4 h-4" />
  </Button>
</div>
```

Aria labels mandatory. Hover colors instantly tell the user "this one is dangerous."

### §19.5 KPI cards — accent borders

Stop using uniform card styling for KPI cards. Each KPI card type gets a left-accent border:

```tsx
// src/components/ui/KpiCard.tsx
const accents = {
  primary:  "border-l-(--color-accent)",
  success:  "border-l-(--color-profit)",
  info:     "border-l-(--color-info)",
  warning:  "border-l-(--color-warning)",
  danger:   "border-l-(--color-loss)",
};

export function KpiCard({ label, value, sublabel, icon, accent = "primary" }) {
  return (
    <div className={cn(
      "rounded-lg border border-(--color-border)",
      "border-l-4", accents[accent],
      "bg-(--color-surface)",
      "p-4 flex items-start justify-between"
    )}>
      <div className="space-y-1">
        <div className="text-xs font-semibold uppercase tracking-wider text-(--color-text-secondary)">
          {label}
        </div>
        <div className="text-2xl font-num font-semibold tabular-nums text-(--color-text)">
          {value}
        </div>
        {sublabel && (
          <div className="text-xs text-(--color-text-muted)">{sublabel}</div>
        )}
      </div>
      {icon && (
        <div className={cn(
          "w-10 h-10 rounded-lg flex items-center justify-center",
          "bg-(--color-surface-2) text-(--color-accent)"
        )}>
          {icon}
        </div>
      )}
    </div>
  );
}
```

Reference example (matches BMN screenshot 7):

```tsx
<KpiCard label="Total Stocks" value="25"  accent="primary" icon={<BarChart3 />} />
<KpiCard label="Active"        value="25"  accent="success" icon={<Activity />} />
<KpiCard label="Industries"    value="13"  accent="info"    icon={<Building2 />} />
<KpiCard label="Watchlist"     value="0"   accent="warning" icon={<Star />} />
```

---

## §20 — Contrast refinement (fixes "whitish" feel)

The previous polish made text legible but the chrome (borders, separators) feels too prominent. Adjust:

1. **`--color-border` drops to `#1e293b`** in midnight theme — much more subtle.
2. **`--color-border-strong` becomes `#334155`** — used only for floating panels and emphasized borders.
3. **More surface tiers** — `--color-surface-3` introduced for hover states; cards no longer all the same flat shade.
4. **Color anchors via badges and accents** — the eye should land on a colored symbol, a status pill, a P&L number, not on a card edge.

Visual rule: in a typical screen, the user's eye should be drawn to **data colors** (symbols, prices, badges, P&L), not to **chrome colors** (borders, separators, card edges). If borders are the most visible thing, the design is failing.

---
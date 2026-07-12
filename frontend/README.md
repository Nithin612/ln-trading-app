# Frontend — Trading Platform SPA

React 19 · TypeScript · Vite · Tailwind v4 (token-driven, 5 themes) ·
Zustand + TanStack Query · Vitest + RTL. Full setup lives in the
[root README](../README.md); the design law is
[`docs/UI_GUIDELINES.md`](../docs/UI_GUIDELINES.md) (distilled into
`.claude/rules/ui.md` + `typescript.md`).

```bash
pnpm install
pnpm dev          # :5173 — proxies /api AND the /ws/live WebSocket to :8000
pnpm test         # vitest (jsdom, RTL)
pnpm lint         # eslint
pnpm typecheck    # tsc --noEmit
```

## Conventions that get PRs rejected

- **Colors only via tokens** from `src/styles/tokens.css`, written in the
  Tailwind v4 var form `bg-(--color-surface)` — the old `bg-[--color-x]`
  bracket form silently compiles to NOTHING on v4 (repo-wide migration
  2026-07-11; the §13.1 audit grep flags any regression). Never palette
  classes (`text-green-500`), never `dark:`, never raw hex in features.
- **Numbers only via `src/lib/format.ts`** (`formatCurrency`, `formatINR`,
  `formatLakh`, `formatPct`, `formatChange`) — `toFixed`/`toLocaleString`
  in feature code is a review failure. Numeric table cells right-aligned
  with `tabular-nums`.
- **API calls only through `src/lib/api/*`** typed modules; live data via
  `src/hooks/useLiveQuotes` / `useAlertStream` (batched flushes — never a
  setState per tick). Server state = TanStack Query; client state =
  Zustand; no server data copied into stores.
- **Themed components only** (`components/ui/`): `SimpleSelect`,
  `Checkbox`, `Dialog`, `Popover`… — raw `<select>`/`<input type=…>`
  fail review. Floating panels render through a Portal with a SOLID
  surface (see `popover.tsx`).
- **Every page/component ships tests**: data render, loading skeleton,
  empty state, error state, primary interaction — queried by role/visible
  text, mocked at the `@/lib/api/*` module boundary (never fetch).

Test in **daybreak** (light) and **carbon** (high-contrast) before calling
UI work done — not just the default theme.

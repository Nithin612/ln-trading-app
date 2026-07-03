# TypeScript / React rules (frontend/)

React 19 · TypeScript 6 · Vite 8 · Tailwind 4 (token-driven) · Zustand +
TanStack Query · Vitest + RTL. `npm run lint` + `npm run typecheck` stay
green. UI law lives in docs/UI_GUIDELINES.md and .claude/rules/ui.md — this
file is the code-level side.

## Components

- Function components + hooks only. Feature pages under `src/features/<area>/`,
  shared primitives under `src/components/ui/`, layout under
  `src/components/layout/`.
- Never raw `<select>`/`<input type="checkbox">`/`<input type="range">` in
  feature code — themed equivalents from `@/components/ui/` only.
- Floating panels (dropdown/popover/dialog/tooltip) render through a Portal
  with solid `--color-surface` backgrounds (no `/50`-style opacity on
  surfaces), `--color-border-strong`, shadow, z-50+.
- Props typed explicitly; no `any` (use `unknown` + narrowing); component
  files export one main component.

## Data & state

- Server state via TanStack Query (stable query keys, explicit staleTime);
  client state via Zustand. No server data copied into Zustand except
  transient live-stream values.
- API calls only through `src/lib/api/*` typed modules using the shared
  `api` client (auth header + ApiError handling built in). No raw fetch in
  components.
- Live data: WebSocket via `useLiveQuotes` (token as `?token=`; ws/wss from
  page protocol; no auto-reconnect on close code 4401). Apply tick updates
  batched (rAF or interval-flush) — never one setState per tick on a list.
- Numbers through `lib/format.ts` (formatCurrency/formatINR/formatPct/
  formatChange). `toFixed`/`toLocaleString` in feature code is a review
  failure.

## Performance

- Lists that can exceed ~200 rows or receive live updates: TanStack Virtual +
  memoized rows + stable keys (never array index for dynamic lists).
- Route-level code splitting for heavy pages (charts, strategy lab).
- Effects: correct dep arrays; subscriptions created once per mount, cleaned
  up on unmount; no resubscribe churn.

## Tests

- Vitest + RTL; user-facing assertions (`getByRole`, visible text) over
  implementation details. Mock at the API-module boundary
  (`vi.mock("@/lib/api/...")`), not fetch. Every new page/component ships
  with tests covering: renders with data, loading skeleton, empty state,
  error state, and the primary interaction.

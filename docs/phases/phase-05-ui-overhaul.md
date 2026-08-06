# Phase 5 — UI overhaul

> **Status: slices 5.1–5.4 built 2026-08-06** (branch `worktree-phase5-ui-overhaul`).
> Frontend suite **257 → 332**; backend F&O suite **31 → 49**; eslint · tsc ·
> ruff · mypy clean. The one **live-gated** exit item is the in-browser 60 fps
> verdict under replayed full-rate ticks — see §6.
>
> **Full backend run in this worktree: 1032 passed, 9 failed, 13 errors.** All 22
> non-passes are `FileNotFoundError` on the worktree's missing root `.env` — the
> `tests/goldens` and `tests/parity` harnesses read it. **Verified** by running
> those two directories alone: identical 9 failed + 13 errors, so nothing in the
> Phase-5 diff contributes a single failure. They pass in the main checkout, where
> `.env` exists; re-run the gate there (or with `.env` present) before
> `/phase-gate`. Everything else in this worktree runs with an inline
> `JWT_SECRET_KEY=…`, because symlinking `.env` is (correctly) blocked.

## 1. Goal & why

`docs/UPGRADE_PLAN.md` §"Phase 5 — UI overhaul": new IA + slate theme default,
four style pages, the F&O chain ladder + strategy cards, Live Signals feed with
an alert centre, `useLiveQuotes` v2, and a measured perf pass.

Two of those were **already done** before this phase opened, during the Phase-3
Tailwind v4 token migration: the grouped sidebar IA (`nav-items.tsx`, its
comment already read "Phase-5 IA overhaul") and **slate as the default theme**
(`tokens.css`: bare `:root` ≡ slate, five themes total). Route-level code
splitting and `wss://` support also already existed. So the real work was the
four remaining items, and the phase re-scoped to them rather than re-doing
finished work.

The sharpest motivation was **Phase 4 had shipped a complete F&O backend with no
screen at all** — chain, PCR, max-pain, basis, VIX regime, IV-rank, Rust
IV/Greeks, and the option-selling engine were reachable only by curl.

## 2. Slice 5.1 — live-data infrastructure

`useLiveQuotes` was written for a handful of instruments and did **one
`setState` per tick, each cloning the whole quote map**. Rewritten to buffer
frames in a ref and apply them in **one state update per animation frame**,
coalescing repeated ticks per symbol to the newest (sound because a last-traded
price is latest-wins — asserted explicitly in `livePerf.test.ts`).

Three real bugs surfaced while rewriting, all fixed:

| Bug | Consequence |
|---|---|
| Connect effect keyed on the symbol **list** | every watchlist edit tore down and reopened the WebSocket |
| A second effect re-sent `subscribe` on **every render** | callers pass a fresh array literal each render, so this fired constantly |
| `unsubscribe` was **never sent** | a long session leaked a server-side Redis subscription for every symbol ever viewed |

The subscription now keys off the symbol **set's content** and sends deltas; a
reconnect re-sends the full want-set (the server starts clean, so a delta would
silently under-subscribe); dropped symbols unsubscribe **and their stale quotes
are pruned** — a price displayed under a symbol you stopped tracking is a
money-UI hazard, not just waste. `authFailed` is surfaced, matching the other
two live hooks.

Also: `src/lib/ws.ts` centralises `buildWsUrl` + the close-code/reconnect
constants that were retyped in all three live hooks.

### The virtualization deviation (decision, recorded)

The plan named `@tanstack/react-virtual`. **It cannot be installed on this
machine.** A snap refresh pruned pnpm store revision 238, and
`frontend/node_modules` is hard-linked to that store — so `pnpm add` fails with
`ERR_PNPM_UNEXPECTED_STORE` and any new dependency requires a full ~900-package
reinstall. (This is the real cause behind the long-standing "pnpm add is
blocked" note; the memory recorded the symptom, not the cause.)

**Decision:** write `useVirtualRows` (fixed-height windowing, ~150 lines) rather
than do a full reinstall against a live dev server mid-phase. It is deliberately
**library-shaped** (`{ virtualized, startIndex, endIndex, padTop, padBottom }`)
and behind one module, so swapping TanStack in later is a one-file change with
no call-site churn. Windowing is **off below 200 rows** per
`.claude/rules/ui.md`, which also keeps small tables and their existing tests
byte-identical in behaviour.

**Follow-up:** repair the pnpm store (`pnpm config set store-dir` to a durable
path outside `~/snap/`, then one full `pnpm install`) so this stops recurring.

## 3. Slice 5.2 — F&O page

`/styles/fno` (matched before the generic `styles/:style`): analytics strip,
option-selling strategy cards, chain ladder.

**Backend additions were unavoidable**, not scope creep:

- `/fo/chain` returned only strike/OI/volume/LTP — the planned "ladder with IV
  and Greeks" had nothing to render. `fo_analytics.price_chain_greeks` inverts
  every quoted leg to an IV and prices its Greeks via **two batched `tradecore`
  calls per side**, using **Black-76 on the future (carry = 0) — the same
  convention `iv_rank` uses**, so a ladder IV is directly comparable to the
  IV-rank history rather than being a second, subtly different number for the
  same thing. The options math itself stays Rust-only; this is orchestration.
- **Unpriceable legs are absent, never zero-filled.** A `0.0` delta or IV reads
  as a real, tradeable value on screen.
- `fo_analytics.chain_day` — Greeks need a time-to-expiry, and dating them off
  `today` would misprice every chain loaded on a Monday from Friday's close (and
  every holiday). The response now carries `as_of` / `fut_price` / `dte` so the
  UI can state exactly what it priced off; any missing input (no futures close,
  expiry already settled) leaves every Greek `null` rather than guessing a
  forward.
- `/fo/underlyings` + `/fo/expiries` — the chain UI could not render without
  them, and hardcoding a symbol list in the client would bake market knowledge
  into the frontend. Both scope to the latest recorded day (offering what is
  currently tradeable, and staying index-fast instead of `DISTINCT`-scanning
  years of bhavcopy); already-settled expiries are dropped, since a settled
  contract has no tradeable chain.

**Honesty carried from `phase-04-fo-suggestions.md` into the UI** — this is the
part most likely to mislead, so it is explicit:

- **Expectancy is labelled `report-only`.** Risk-neutral expectancy is ≈0 by
  construction and the shipped estimator is deliberately negative-biased, so a
  small negative number is *expected*. Rendered bare in loss-red it would read
  as "this trade loses money".
- **"Forward-tested, not backtested"** on the candidates panel.
- An **empty candidate list is a deliberate no-trade answer**, and the empty
  state lists the gates that produced it.
- The **India-VIX veto renders as a stand-down when the regime is *unknown***,
  not as a blank — the veto fails closed, and a blind safety gate must never
  look OK.
- **No order button.** F&O execution does not exist (live trading is Phase 7).
- The ladder always states its **source and day**, so an EOD chain cannot read
  as live.

The ladder uses the **neutral accent** token for OI bars, not profit/loss: open
interest is not a P&L, and money colours would read as gain/loss. ATM is marked
with a **text badge** as well as a tint, so it survives a colour-blind read.

## 4. Slice 5.3 — style pages v2

- **Committed vs forming, visually separate**, because conflating them is a
  correctness problem: the table is badged **COMMITTED** (complete candles,
  valid from the next one — the tradeable layer the one-click paper trade acts
  on); the **provisional** leaderboard sits below in its own panel. Reused
  `ProvisionalPanel` via a new optional `style` prop that locks it to one style,
  hides the tab strip (a style page must not offer navigation to a style the
  page isn't about) and subscribes to only the style it renders.
- **Per-style stats header** from the real `/analytics/outcomes` data (hit rate,
  entry rate, avg return) plus the live list shape. **Sample size sits next to
  every rate**, and a rate from fewer than 20 tracked outcomes renders greyed
  with "n=… — too small to read" instead of coloured: the 08-03→05 evidence
  (1 of 15 trades reached +1R) is exactly the regime where a rate off a handful
  of outcomes looks like an edge and isn't. **Entry rate is surfaced
  deliberately** — a low one means entries are priced too far away, which the
  daily analysis identifies as the current binding constraint.
- **Factor-breakdown drawer** — the confluence engine is the edge and is
  deliberately not a black box: per-factor weight, score, **weighted
  contribution (weight × score, matching how the scorer aggregates)** and the
  engine's own explanation, **ordered by absolute contribution** so what drove
  the decision is first. Opened from a **button on the symbol, not a clickable
  row**, so it is keyboard-reachable with a visible focus ring.
- Live LTP column (`useLiveQuotes` v2 + the existing `PriceCell` flash, which
  updates the cell rather than re-rendering the row) and the table wired through
  `useVirtualRows`.

## 5. Slice 5.4 — Live Signals feed + alert centre

`/live-signals`: the full-width feed to leave open during a session, where the
topbar bell is only a glanceable summary. Server-side style + watchlist scoping,
client-side lenses, the anti-chase guardrail, one-click paper trade on the
originating signal, and the feed labelled **PROVISIONAL** (at-most-once; tails
new entries only; never creates or gates a signal).

**Desktop notifications** (`useBrowserNotifications`), opt-in only:

- Permission is **never** requested without a user action — browsers penalise
  unsolicited prompts and a denial is effectively permanent. A blocked
  permission renders as a disabled, explained control rather than a dead toggle;
  a browser with no Notification API says so.
- **Bursts coalesce.** The open-auction XADD batch fans out dozens of alerts in
  one flush; above 3 in a batch it becomes **one summary notification**.
- Alerts already seen never re-notify, and the batch present at mount (or when
  the toggle is switched on) is marked seen **without** notifying — enabling must
  not dump the backlog.
- **Notifies regardless of tab visibility, on purpose:** the case that matters is
  the browser sitting behind an IDE or chart window, where `document.hidden` is
  false, so gating on it would suppress exactly the alerts that matter most.

Rows here are **memoised, not virtualised**, and the reason is recorded:
`useAlertStream` caps retention at 100, so windowing would add machinery for a
list that cannot reach the size where it pays off; the real live-update cost is
re-rendering rows every flush, which memoisation fixes.

Two shared-code improvements fell out: `useAlertContext` (the sid→symbol and
signalId→signal joins, extracted from AlertBell so the bell and the feed share
one implementation), and `SimpleSelect` now accepts `aria-label` — its trigger
renders only the selected value, so an unlabelled select was an **unnamed
combobox** to assistive tech.

## 6. Perf — what is proven and what is not

**Proven, deterministically** (`src/test/livePerf.test.ts`, re-runnable in CI):
render count is a function of **frames, not ticks**.

| Measurement | Result |
|---|---|
| 12,000 ticks over 60 frames, 500-symbol subscription | **60 renders** (one per frame) |
| 10 ticks vs 10,000 ticks in a single frame | **1 render either way** |
| A frame with no ticks | **0 renders** (no rAF is scheduled — an idle tape is free) |
| Coalescing correctness | newest price per symbol survives the frame |

**NOT proven — the live-gated exit item.** The budget row "UI live-table commit
under full tick rate ≤ 16 ms (60 fps)" **cannot** be concluded from the above:
jsdom does no layout, paint or compositing. That verdict needs a real browser
profiled against a **replayed full-rate session** (`make replay` tape + the live
worker), and is recorded as unproven in `docs/PERFORMANCE.md` — deliberately the
same treatment the tick→publish p99 got rather than a number nobody measured.

## 7. Exit checklist

- [x] 5.1 live-data infra · 5.2 F&O page · 5.3 style pages v2 · 5.4 Live Signals
- [x] Frontend 332 green · backend 1032 pass (22 `.env`-only, see the banner) ·
      eslint · tsc · ruff · mypy
- [ ] **Full `make check` from a checkout that has `.env`** (adds the cargo gates;
      no `engine/` code changed this phase, so those should be unaffected)
- [ ] **ui-reviewer** on the four new pages/components
- [ ] **In-browser 60 fps under replayed full-rate ticks** → then the
      PERFORMANCE.md budget row can be marked MET or restated
- [ ] Manual smoke in the browser across **daybreak (light)** and **carbon
      (highest contrast)**, not just slate
- [ ] **Verify the sticky table header still sticks inside `VirtualViewport`.**
      `Table` renders its own `overflow-x-auto` wrapper, and per CSS an element
      with one axis `auto` and the other `visible` computes the visible axis to
      `auto` too — so that wrapper is technically a Y scroll container even
      though it never scrolls (no height bound). `position: sticky` on the
      `<thead>` may therefore resolve against the wrapper instead of the
      bounded `VirtualViewport`. Cannot be settled in jsdom (no layout). If it
      does fail, the fix is to let `Table` take the scroll container role rather
      than nesting one inside it.
- [ ] `/phase-gate`

## 8. Follow-ups handed forward

- **Repair the pnpm store** (durable `store-dir` outside `~/snap/`, one full
  install), then optionally swap `useVirtualRows` for `@tanstack/react-virtual`
  behind its existing interface.
- **Phase-2 directional F&O suggestions** (`/suggestions/fno`) are not on the new
  F&O page — it serves the Phase-4 index option-selling engine plus the chain.
  Folding the profile-based directional list in is a small follow-up once
  `StylePage`'s table is extracted into a shared component.
- Kite **SPAN margin** for the strategy cards (v1 uses defined-risk max loss),
  and the **realized-vs-POP forward-validation dashboard** (Phase 6).
- The F&O page reads **EOD by default**; the intraday-snapshot path is wired and
  selectable but only meaningful while the 1-minute chain recorder is running.

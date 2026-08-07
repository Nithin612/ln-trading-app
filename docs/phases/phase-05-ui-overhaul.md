# Phase 5 — UI overhaul

> **Status: slices 5.1–5.4 built 2026-08-06** (branch `worktree-phase5-ui-overhaul`).
> Frontend suite **257 → 332**; backend F&O suite **31 → 49**; eslint · tsc ·
> ruff · mypy clean. The one **live-gated** exit item is the in-browser 60 fps
> verdict under replayed full-rate ticks — see §6.
>
> **Final verification (2026-08-06/07):** backend **1038 passed, 0 failed**
> (16m44s, `tests/` excluding `goldens`+`parity`); frontend **344 passed**;
> `ruff` · `mypy` (159 files) · `eslint` · `tsc --noEmit` · **`tsc -b`** ·
> **`vite build`** all clean — the last two deliberately, since `make check`
> does not cover the production build and this phase added node-side config
> (see the build-gate-gap note in memory).
>
> `tests/goldens` and `tests/parity` are excluded here only because the worktree
> has no root `.env` (those harnesses read it) and symlinking `.env` is
> correctly blocked. **Verified** that this accounts for all of them and nothing
> else: running those two directories alone reproduces exactly the same 9
> failed + 13 errors seen in the full run, every one a `FileNotFoundError` on
> `.env`. They pass in the main checkout. Everything else runs here with an
> inline `JWT_SECRET_KEY=…`.

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

**Proven in a real browser (2026-08-06) — the budget row is MET.** jsdom does no
layout or paint, so the numbers above are necessary but not sufficient. A
browser harness now closes it: `frontend/perf/run-bench.mjs` drives
`perf/live-table-bench.html` (source `src/perf/LiveTableBench.tsx`) in **Chrome
151** over the DevTools Protocol — zero new dependencies, because this box
cannot install packages (Node 22's built-in WebSocket speaks CDP). It mounts the
REAL `useLiveQuotes` + `useVirtualRows` + `PriceCell` + themed table, moves the
price on every tick so `PriceCell` really flashes, and reports React
`<Profiler>` `actualDuration` — literally the quantity the budget names.

| Profile | Rows | Ticks/s | **Commit p99** | Frame p50 | Jank frames (>20 ms) |
|---|---|---|---|---|---|
| Realistic (suggestions cap at 50) | 50 | 500 | **8.8 ms** | 16.7 ms | **0** of 595 |
| Stress | 300 | 2,000 | **7.8 ms** | 16.7 ms | 2 of 598 (mount) |
| Headroom | 1,000 | 5,000 | **7.6 ms** | 16.7 ms | 2 of 598 (mount) |

Budget ≤ 16.7 ms → **MET with ~2× headroom**. Row count and tick rate barely
move the cost (50→1,000 rows shifts p99 by ~1 ms), which is the windowing and
the rAF batching each doing their job. Full method, caveats and reproduction
steps: `docs/PERFORMANCE.md` §2026-08-06.

Caveats stated rather than buried: headless Chrome (compositor path differs from
a windowed browser), and the socket is stubbed — this is the CLIENT's cost to
apply and paint a full-rate tape; the backend tick→publish path is a separate,
already-measured budget.

## 6b. Review round (2026-08-06) — what the agents caught

Both reviews ran read-only (the user's `make check` held the test DB). Every
finding below was verified against source or real data before being fixed, and
each carries a regression test.

**bug-hunter — the one that mattered.** `futures_basis` required a future with
the **same expiry as the option**, but index options are **weekly** and index
futures **monthly**. Checked against the live dev DB: on the latest recorded
NIFTY day only **3 of 12** option expiries have a FUT row, and the *nearest*
expiry — the one the page defaults to, 226 legs — has none. So the F&O page
would have shipped with **every Greek null by default**, and because spot keyed
the same way, `atm_strike` was null too and the ±N strike window silently
degraded to the entire chain. Fixed with `forward_for_expiry` (exact-expiry
future when it exists, else the market's own carry implied from the nearest
future) + `spot_on_day`, and a new `forward_source` field so the UI states which
was used. Also fixed: an **intraday** chain was being priced against the
*previous* day's futures close (EOD bhavcopy lands ~18:45 IST) — it now stands
down instead; `chain_day` derived a trading day from a UTC instant; and two
`useLiveQuotes` pruning holes plus a socket-identity bug where a stale socket's
late close clobbered the live one (the first fix attempt was wrong — a shared
`let` that reconnect reassigns — and the regression test caught it).

**ui-reviewer.** Token usage was clean (all 20 referenced tokens exist in all 5
themes). Real defects: `hit_rate`/`entry_rate` are **fractions** from the API
but were rendered as percents and toned against `>= 50`, so a 60% hit rate read
"0.60%" and was painted loss-red always — and the test hid it by mocking
percent-shaped data; the honest-sample gate used the wrong denominator;
`StylePage` rows weren't memoised, so every rAF flush re-rendered all visible
rows; daybreak's `--color-warning` measured **2.91:1** (below AA) while carrying
the safety copy; the ladder's two-row header gave every label twice with no
call/put distinction; and several missing skeleton/retry/aria-label states.

**Knowingly deferred** (systemic, pre-existing, not introduced here): the
`--color-bull`/`--color-profit-bg` pairing measures 3.32:1 in daybreak on 10px
bold badges — but that pairing is what §19.3 `StatusPill` prescribes app-wide,
so changing it is a design-system decision, not a Phase-5 one. Likewise
`components/ui/drawer.tsx` predates this phase and lacks a Portal and a focus
trap. Both are listed in §8.

## 7. Exit checklist

- [x] 5.1 live-data infra · 5.2 F&O page · 5.3 style pages v2 · 5.4 Live Signals
- [x] Frontend **344** green · backend **1038** pass, 0 fail (goldens/parity
      `.env`-only, see the banner) · eslint · tsc · `tsc -b` · `vite build` ·
      ruff · mypy
- [ ] **Full `make check` from the main checkout** (it has `.env`, and adds the
      cargo gates + goldens/parity). No `engine/` code changed this phase, so
      the Rust legs should be unaffected.
- [x] **bug-hunter** + **ui-reviewer** — run 2026-08-06; all findings in new
      code fixed with regression tests (§6b); two systemic/pre-existing ones
      deferred to §8 with reasons
- [x] **In-browser 60 fps** — MEASURED and **MET** (§6, `PERFORMANCE.md`)
- [ ] Manual smoke in the browser across **daybreak (light)** and **carbon
      (highest contrast)**, not just slate
- [x] **Sticky table header inside `VirtualViewport` — it was BROKEN; fixed and
      re-verified in Chrome.** `Table` wraps itself in `overflow-x-auto`, and CSS
      promotes the other axis to `auto` too, so that wrapper became the
      containing block for `position: sticky`. Being unbounded it never scrolls,
      so the header travelled with the content: scrolling the viewport 800 px
      put the `<thead>` at `top: -761` — straight off screen, losing the column
      headers on exactly the long tables that need them. The static review had
      cleared this; only the browser caught it. `VirtualViewport` now neutralises
      the inner wrapper (`overflow-visible`) and owns both scroll axes; measured
      after the fix, the header holds at the viewport top (`sticks: true`). The
      F&O ladder, which had no bounded container at all, now uses one too.
- [ ] `/phase-gate`

## 8. Follow-ups handed forward

- **Daybreak badge contrast (systemic).** `--color-bull` on `--color-profit-bg`
  is 3.32:1 and `--color-bear` on `--color-loss-bg` 3.95:1 in the light theme,
  on 10–11 px bold badges — below AA. This is the pairing §19.3 `StatusPill`
  prescribes app-wide, so the fix is a token decision (add
  `--color-profit-strong`/`--color-loss-strong`, or darken daybreak's pair to
  the 700 shades), not a Phase-5 edit.
- **`components/ui/drawer.tsx`** (pre-existing, now used by `FactorDrawer`):
  no `createPortal`, `--color-border` instead of `--color-border-strong`,
  `duration-300` over the 200 ms cap, and `aria-modal` without a focus trap.

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

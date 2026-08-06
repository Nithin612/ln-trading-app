# Daily Operations Runbook — Paper-Trading Cycle

**Audience:** you, running a paper-trading day (not a soak). All times **IST**.
**Scope:** exactly which processes to start/stop, when, whether they run 24/7,
and how they depend on each other — updated **2026-08-06** for the ₹ profit
ladder, risk-first fill sizing, trade-from-AlertBell, and the daily
`make analysis` step (earlier: honest-fill gap-through-stop, slippage,
paper-clock reset).

> **The one thing that changed this week.** Yesterday's and today's fixes —
> honest gap-through-stop fills, 2 bps slippage, the trail/profit-lock, MFE
> tracking — all execute inside the **position monitor**, which runs in the
> **Celery worker** (`make worker`) every minute during the session, and it
> reads live prices that the **live-worker** publishes to Redis. So to actually
> exercise the new exit fixes on Mon/Tue, **the Celery worker AND the live-worker
> both have to be running during market hours.** If the worker is off intraday,
> positions are not auto-closed/trailed and the new fills never happen.

---

## 0. Process cheat-sheet

| # | Process | Command | Role | Start | Stop | 24/7? | Needs |
|---|---|---|---|---|---|---|---|
| A | DB + Redis | `make up` | Postgres (5433) + Redis containers | Once | `make down` when you're done for days | **Yes, fine** (data preserved on down) | — |
| B | Migrations | `make migrate` | Apply schema (incl. new `paper_clock_started_at`) | After any `git pull`/new migration | one-shot (not a process) | n/a | A |
| C | Kite login | `cd backend && uv run python scripts/kite_login.py` | Fresh access token (dies ~06:00 daily) | Each morning ~07:50 | one-shot | **No — daily** | A |
| D | Backend API/WS | `make backend` | REST + `/ws/live` (feeds the UI) | ~08:00 | when done for the day (or leave up) | optional | A, B |
| E | Frontend | `make frontend` | Vite dev server (the UI) | ~08:00 | when done for the day | optional | D |
| F | **Celery worker** | `make worker` | **Position monitor (auto-exit/trail/MFE with the new fills)** + EOD ingest + nightly signals | Before open (or just leave running) | only for a soak / machine-quiet | **Yes — leave up** | A, (C for Kite tasks) |
| G | **Live tick worker** | `make live-worker WORKER_ARGS=--gap-fill` | Streams Kite ticks → Redis `ltp:`/candles; fires alerts | **08:15–08:30** | self-exits ~15:30 (or Ctrl-C) | **No — session only** | A, C |
| H | Shadow parity check | `bash backend/scripts/shadow_day.sh <YYYY-MM-DD>` | Rust-vs-Python 1d-close double-check | Evening ~19:30 | one-shot | **No — evening** | A, F (EOD must have run) |
| — | Soak (optional) | `make soak` | Live-worker + **recording**, quiet box | only for a recorded soak | — | No | mutually exclusive with D+F |

**The normal paper-trading day = A + B + C + D + E + F + G running together.**
`make soak` is a *different* mode (see §8) — don't use it for a trading day.

---

## 1. Daily timeline (IST)

### Pre-flight — once, in order (~07:45–08:00)
1. **`make up`** — start Postgres + Redis. Skip if the containers are already up
   (`make ps` / `docker ps` shows `tp_postgres`, `tp_redis`). Leaving them up
   overnight is fine.
2. **`make migrate`** — apply pending migrations. **Do this after any code update.**
   This week it adds `users.paper_clock_started_at`; skip it and the Paper Record
   / reset button will 500. One-shot, seconds.
3. **`cd backend && uv run python scripts/kite_login.py`** — the Kite token died
   at ~06:00, so re-login and paste the redirect URL. Needed by the live-worker
   (G) and the worker's Kite tasks (option-chain snapshots). Verify: the Kite
   Connect page shows **Connected**.

### Pre-open — start the long-running processes (before 09:15)
Each in its own terminal, left running:
4. **`make worker`** (~08:00, or just leave it up from yesterday) — the Celery
   worker + beat. During the session its per-minute `monitor_positions` scans your
   open paper positions and applies **SL/TP auto-close at the honest gap-through
   fill, trail/profit-lock advance, and MFE tracking**. In the evening the same
   process runs EOD ingestion (18:40) and nightly signals (19:15). It is
   session-guarded, so off-hours it idles.
5. **`make backend`** (~08:00) and **`make frontend`** (~08:00) — the API/WS and UI.
6. **`make live-worker WORKER_ARGS=--gap-fill`** (**08:15–08:30**) — subscribes the
   full equity universe (~2,000 instruments) and **gap-fills** each instrument's
   intraday hole from its last stored bar first (≈35 min at full universe — start
   by 08:30 so it finishes before open), then streams live ticks. Verify: the Kite
   Connect page shows the tick consumer **Running**, terminal heartbeats every ~30s.

### 09:00 pre-open / 09:15 open — automatic
Ticks flow with no command. LTP cells flash, provisional leaderboards populate,
committed signals appear at candle close, alerts fire, and the monitor
auto-manages your positions. **Nothing to run.**

### During the session (09:15–15:30) — watch, don't rebuild
- Paper-trade a signal → position appears on **Positions**. Only names with a live
  LTP fill; thin names not in the tick universe return 422 (off-market guard —
  expected).
- Watch the **AlertBell** (entry-zone/cross/near/volume triggers, anti-chase
  guardrail), **Positions** (live P&L + emergency-exit health verdict), and the
  **Paper Record** card.
- **Do NOT run `make check` / pytest / cargo / maturin now** — heavy CPU has
  dropped the Kite WS and frozen the box. (`make worker` is fine — it's light I/O,
  not a build.)

### Evening — EOD, then the parity check
7. **~15:30–15:35:** the live-worker (G) **self-exits cleanly** (exit 0) when the
   session ends. You can also Ctrl-C it. Leave A/D/E/F up.
8. **~18:40 / 19:15 (automatic, needs F up):** the worker ingests the EOD bhavcopy
   and generates tonight's signals. Verify `ohlcv_1d` / `fii_dii` rows for today.
9. **~18:45 — the day's analysis report** (needs A up; the EOD bar has just
   landed so the regime read is fresh):
   ```
   make analysis                      # today (IST)
   make analysis DATE=2026-08-07      # a specific day
   make analysis WEEK_OF=2026-08-07   # + the Mon–Fri roll-up (do this Friday)
   ```
   Writes `docs/analysis/<date>.md`, updates the running `LEDGER.md`. Read-only
   — safe to re-run. What to look at: **Profit sealed right now** vs **Profit
   given back**, the **reached-≥1R** count, and any **chase ⚠** rows. Method +
   definitions: `docs/analysis/README.md`; open fixes: `FIX_PLAN.md`.
10. **~19:30, after the close is committed:** run the parity double-check for the
   day(s):
   ```
   bash backend/scripts/shadow_day.sh 2026-08-03      # Monday
   bash backend/scripts/shadow_day.sh 2026-08-04      # Tuesday
   ```
   Exit 0 with **0 diffs** = the Rust engine agreed with Python on the day's
   decisions. Any diff → investigate before trusting the day. Appends to
   `backend/shadow/shadow_week.log`. This checks **engine correctness**, not trade
   P&L — it is separate from your Mon/Tue-vs-Thu/Fri outcome comparison.

---

## 2. Per-process detail — start, stop, 24/7

### A · `make up` (Postgres + Redis)
- **Start:** once. Everything else needs it.
- **Stop:** `make down` (data is preserved). Only bother when freeing the machine
  for days. **`make clean` DELETES ALL DATA — never during the cycle.**
- **24/7?** Yes, fine to leave up.

### B · `make migrate`
- One-shot, not a process. Run after any `git pull` or new migration. Idempotent
  (no-op if already at head). Safe to run every morning.

### C · `scripts/kite_login.py`
- **Daily**, each morning before the live-worker. The token dies ~06:00 IST.
- If you see the **Kite banner** in the UI, or the live-worker prints
  `NO TOKEN — exit 4`, the token expired → re-run this, and the `make live-worker`
  supervisor picks it up on its next 60s retry.

### D · `make backend`  ·  E · `make frontend`
- **Start** when you want the UI (~08:00). **Stop** when done for the day, or leave
  up. Independent of the workers (they share DB+Redis). Frontend needs backend.

### F · `make worker` — the important one now
- **Start** before the session (or just leave it running across the Mon/Tue cycle —
  this is the simplest correct choice).
- **Two jobs in one process:** (1) intraday — the per-minute position monitor that
  now applies the honest gap-through/slippage exits, the ₹ profit ladder, and MFE;
  (2) evening — EOD ingest + nightly signals (self-heals up to ~21 days of missed
  sessions).
- **⚠ HARD TIMING RULE — do NOT stop the worker at 19:00.** The evening beats are
  **18:30 FII/DII · 18:40 equities EOD · 18:45 F&O EOD · 19:15 nightly signals ·
  19:25 profile suggestions** (IST). Killing it at 19:00 means **tomorrow's
  signals never generate.** Keep it up until **≥ 19:35**, or simply leave it
  running 24/7 (recommended — it's session-guarded and light).
- **⚠ A missed 18:30 costs you that day's FII/DII permanently.** The NSE endpoint
  serves **only the latest trading day** (`services/eod_catchup.catchup_fii_dii`
  docstring), so it is capture-as-you-go: no worker at 18:30 → that session is
  unrecoverable from this source (a historical fetcher is Phase-4 scope), and the
  §2.7 five-day rollup then counts that day as **zero**. Equities/F&O EOD are
  different — those DO self-heal ≤21 days.
- **The monitor is only useful while the live-worker (G) is feeding `ltp:` keys** —
  no live price → the monitor skips the position (never acts on a stale mark).
- **24/7?** Yes — leave it up. It's session-guarded and light (I/O-bound). Its
  only Kite-dependent task (option-chain snapshots) fails harmlessly if the token
  is stale until you re-login.
- **Stop only** for a dedicated soak recording (§8), or to make the box fully quiet.

### G · `make live-worker WORKER_ARGS=--gap-fill` — session only
- **Start 08:15–08:30** so gap-fill completes before open. Runs under a restart
  supervisor: exit 0 → clean session end (stops), exit 4 → no token (re-login,
  retries in 60s), any other → auto-restart in 5s (a restart re-gap-fills the hole).
- **Stop:** it self-exits ~15:30. Ctrl-C to stop early. **Never run it overnight.**
- **24/7?** No.

### H · `shadow_day.sh`
- Evening one-shot, standalone (only needs DB + today's committed close). Not tied
  to backend/frontend/live-worker.

---

## 3. Dependency & ordering (who needs whom)

```
make up (A) ─────────────┬───────────────┬──────────────┬───────────────┐
                         │               │              │               │
                    make migrate (B)  make backend   make worker (F)  make live-worker (G)
                         │             (D) ── make      │ reads ltp:      │ writes ltp:/candles
                         │             frontend (E)     │ from Redis ◄────┘ to Redis
                    kite_login (C) ───────────────────────────────────────┘ (G needs the token)
```
- **Order:** A → B → C, then D/E/F/G in any order (F's monitor only *does* something
  once G is publishing LTP).
- **Bare minimum to see the new exit fixes fire:** A + C + F + G. Add D + E for the UI.

---

## 4. Where the new fixes show up

| Fix (when) | Needs running | Where you see it |
|---|---|---|
| **₹ profit ladder — the live paper exit governor (08-06)** | **F** + G | SL ratchets up in ₹ steps: breakeven once peak profit ≥ **₹2,000**, then seals **peak − ₹1,000** once peak ≥ **₹3,000** (giveback widened to `2.0 × ATR` on volatile names). Only when **Profile → Trading Settings → Profit lock** is ON; OFF = the old fixed R-ladder. Knobs: `PROFIT_LOCK_BREAKEVEN_INR` / `_TRAIL_START_INR` / `_GIVEBACK_INR` / `_ATR_K` in `.env`. Report shows **"Profit sealed right now"**; Positions shows the raised SL |
| **Risk-first sizing from the actual fill (08-06)** | D | Buying above the signal's entry now **shrinks the quantity** (risk stays at your per-trade budget) instead of silently over-risking; a repeat Buy on the same name is capped by the remaining budget and is **rejected** at zero ("already at your per-trade risk"). Report: **Chase / Risk-vs-2%** columns |
| **Buy/Sell from AlertBell (08-06)** | D + E + G | Each entry-zone alert has a Buy/Sell button — tradable even when the stock isn't on the dashboard list |
| Gap-through-stop fill (08-01) | F + G | Trade History: a gapped stop-out books the **gapped market price**, not the stop |
| 2 bps slippage (today) | F + G (exits), D (entries) | Fills sit a hair adverse; realized P&L slightly below the raw stop/target |
| Paper-clock reset (today) | D + E | Paper Record card → **"Reset clock"** button + "counting since …" |
| Signal dedup / near-expiry / regime (chop) filter (yesterday) | D + E | Signals list: one row per setup, "×N" badge, near-expiry hidden, "· chop" muted |
| Anti-chase guardrail (yesterday) | D + E + G | AlertBell: "don't chase > ₹X" / "⚠ chasing +N% past entry" |
| Emergency-exit health verdict (yesterday) | D + E | Positions: CUT / WATCH badge per open position |

Selection + alert fixes are in the API/UI (live with D+E+G). The **exit** fixes
need **F** (the worker) intraday.

---

## 5. The current evaluation window (agreed 2026-08-06)

**Trade 5 sessions — Thu 08-06, Fri 08-07, Mon 08-10, Tue 08-11, Wed 08-12 —
run `make analysis` each evening, then decide the ladder tuning after Wed.**
Do **not** change the `PROFIT_LOCK_*` knobs mid-window; a moving target can't
be measured.

Reading it fairly:
- **Thu 08-06 is a partial day for the exit model** — the worker was restarted
  mid-afternoon 08-06, so **Fri 08-07 is the first session where the ₹ ladder
  governs exits end-to-end**. (Entries got fill-based sizing as soon as the
  auto-reloading backend picked it up.) Keep 08-06 in the log; just annotate it.
- **Exit-side P&L isn't apples-to-apples with July** — gapped stop-outs fill at
  the worse gapped price and every fill carries 2 bps slippage. Treat it as
  "realistic-adjusted," and compare *entry/selection quality* first.
- **The numbers that answer "is the ladder working?"** — from each report:
  **Profit sealed right now** (should be > 0 whenever a trade ran ≥ ₹2k),
  **Profit given back** (should fall vs the 08-03→05 baseline of ~₹21k for the
  week), and **reached ≥1R** (the honest ceiling on what any exit rule can do —
  it was 1/15).
- **If reached-≥1R stays ~1-in-10, the exit rule is not the bottleneck** —
  entry/regime selection is, and that's Phase-6 calibration work, not knob
  tuning. Say so in the review rather than over-tightening the ladder (a tighter
  seal stops you out of the few runners that reach target).
- Keep `make worker` running intraday across all 5 sessions so the comparison
  is same-basis.

---

## 6. When to reset the clock

**Do not reset during the 5-session window above** — those days need to count
under one consistent model. A reset is only worth it after a *material* change
to the fill/exit model (the 08-01 honest-fill change was one; the 08-06 ladder
arguably is too, but the record is young enough that it doesn't matter). When
you do want a clean cycle:
- Click **"Reset clock"** on the Paper Record card (two-step confirm), or
  `POST /api/v1/trading/paper-clock/reset`.
- It stamps `paper_clock_started_at = now`; from then the record counts only
  trades closed on/after that instant (past trades stay in the DB, just stop
  counting). Reversible — you can reset again anytime. The go-live gate stays
  display-only until Phase 7.

---

## 7. Don'ts (hard-won)

- **No `make check` / pytest / cargo / maturin during market hours** while the
  live-worker runs — heavy CPU has dropped the Kite WS and frozen the box.
  (`make worker` is fine.)
- **Don't run `make soak` on a trading day.** Soak expects the backend DOWN and the
  worker STOPPED (a quiet box for a clean recording); it's for capturing a
  replayable session, not for trading. Use `make live-worker WORKER_ARGS=--gap-fill`
  instead.
- **Keep the laptop awake.** Locking the screen is fine; **suspend kills the
  workers.**
- **Don't run two things that both write candles** (the old v1 auto-start consumer
  stays disabled — don't revive it).
- **Never `make clean`** during the cycle (deletes all data). `make down` is the
  safe stop.
- **Push is manual** — `git push` when ready (local `main` is ahead of origin).

---

## 8. Quick recovery

| Symptom | Fix |
|---|---|
| Kite banner in UI / live-worker `exit 4` | Re-run `scripts/kite_login.py`; the supervisor retries in 60s |
| Live-worker crashed | The `make live-worker` loop auto-restarts in 5s and re-gap-fills the hole |
| Positions not auto-closing on SL/TP | Is **`make worker`** running? Is the **live-worker** feeding `ltp:`? Both are required |
| Provisional/alerts empty near open | live-worker not up yet, or gap-fill still running (started too late) |
| Missed a session's EOD bars | Leave `make worker` up an evening — EOD beats self-heal ≤21 days |
| Paper Record / reset 500s | You skipped `make migrate` after the update |

---

*Soak-specific details (recording, replay goldens): `docs/RUNBOOK-soak.md`.
Engine-parity shadow week: `backend/scripts/shadow_day.sh` → `shadow_week.log`.*

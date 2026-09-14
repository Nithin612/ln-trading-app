# CLAUDE.md — project context for Claude Code

Personal intelligent stock-suggestion + algo-trading platform for Indian
markets (NSE/BSE). Solo developer, personal use first, possible future
productization. Read this fully at session start; it points to everything
else.

## Current truth

> **Status lives in ONE place: the top block of `docs/PHASES.md`.** Read it
> first, every session. This section used to duplicate it and drifted badly —
> on 2026-08-08 it still claimed 974 tests (actual: 1120), Phase 3 "in
> progress", and Phase 5 "NOT merged" weeks after it was gated. A status block
> that disagrees with reality is worse than no status block, so what remains
> here is only what is NOT derivable from PHASES.md or the code.

- **v1 phases 0–11 are built and tested.** v1 Phase 12 (live trading) was never
  started — it is now v2 Phase 7. **Live trading genuinely does not exist**:
  `place_order` is paper-only, with no Kite order/GTT path. Every "live"
  recommendation you read anywhere in these docs is a Phase-7 constraint, not a
  description of something running.
- **The v2 upgrade is governed by `docs/UPGRADE_PLAN.md`** (approved
  2026-07-03): Rust compute core, tick-to-tick realtime, four style engines,
  UI overhaul, outcome tracking, then live trading. `docs/PHASES.md` tracks
  status; each finished phase reports to `docs/phases/`.
- **Paper trading runs daily** and feeds the 30-day paper clock (the *Phase-7*
  go-live gate — **not** the Phase-3 exit; this pair is confused often). Exit
  governance is per-user (`users.profit_lock_enabled`): ON = the absolute-₹
  profit ladder (`app/trading/profit_lock.absolute_ladder_stop` — breakeven at
  +₹2k, seal peak−₹1k above ₹3k, ATR room; knobs = `settings.profit_lock_*`),
  OFF = the fixed `trail_sl` ladder. Paper entries size **risk-first from the
  actual fill** (`paper_broker.size_for_fill`), so a chased fill shrinks qty
  instead of over-risking, and repeat entries can't stack past the budget.
- **Daily analysis loop:** `make analysis [DATE=…] [WEEK_OF=…]` (or
  `/daily-analysis`) writes `docs/analysis/<date>.md` + `LEDGER.md`; open fixes
  live in `docs/analysis/FIX_PLAN.md`. **The binding constraint on profit is
  entry/regime selection, not exit logic** — only 1 of 15 trades reached +1R
  over 08-03→05, so the exit machinery was correct but had nothing to protect.
  That is what Phase 6 exists to attack (`docs/phases/phase-06-plan.md`).
  **Phase 6 (6.1+6.2) has since QUANTIFIED that leak** at corpus scale: the
  70–79 confidence band and the transitional ADX regime are net-negative, and a
  **regime gate** (skip ADX 20–25) beats a higher confidence gate — the gate
  experiment nearly doubles captured R. Verdict + numbers live in the PHASES top
  block; `docs/analysis/attribution-*.md` + `gate-experiment-*.md` are the reports.
  **Phase 6 has since run through 6.4:** the §8 walk-forward validated the regime
  gate out-of-sample, and both the regime gate and the `momentum ×1.5` retune are
  now BUILT and running SHADOW-first (measure-only — nothing on the money path
  yet). **The regime gate was flipped active 2026-08-14 and
  ⛔ REVERTED TO SHADOW on 2026-09-02** — its own pre-registered revert condition
  fired: the banner turned ⏳ NOT READY on 08-21 and stayed so for **7 consecutive
  report days**, with the suppressed set net-POSITIVE live (+0.090 expR, `decided`
  54 → **88** = 4.4× the 20-trade bar) and **all three §8 metrics inverted** (win
  30% kept vs 36% suppressed · Sharpe −0.041 vs +0.044 · maxDD 34.5R vs 11.2R;
  total-R −2.0R ungated → −10.0R gated, so the gate SUBTRACTS ~8R). It was
  suppressing 37 of 204 visible signals. `REGIME_GATE_MODE=shadow` + backend/worker
  restart; record `docs/analysis/regime-gate-revert-2026-09-02.md`. **Standing
  lesson: a gate promoted on 44 observations was refuted by 88 — no shadow→active
  flip without its pre-registered count AND a multiple-testing-aware bar.** Gate
  modes are now documented in `.env.example`.
  6.5 pair-trading is BUILT shadow-first; promoting the momentum ×1.5 retune still
  waits on forward evidence. **✅ Phase 6 GATED + CLOSED 2026-08-20** (build-complete;
  three forward-evidence loops — regime keep/revert **DECIDED 2026-09-02: REVERT**, momentum-retune
  promotion, pair df-vs-adf — continue post-close, none blocking; close report in
  `docs/phases/phase-06-plan.md`). **The active build is now Phase 6.8 (Execution Realism
  & Exchange-Safety)** — 6.8.1 depth capture, 6.8.2 spread-aware slippage, and
  6.8.3 circuit-band eligibility overlay, 6.8.4 continuous open-book MTM (rolling
  MFE/MAE for carried holds + weekly per-day open-MTM series), 6.8.5 CA-adjust OPEN
  paper positions (R-preserving split/bonus; admin-verified ratio; ex-date worker,
  idempotent+catch-up; migration `a7b8c9d0e1f2`), and 6.8.6 silent-feed-outage alarm
  (trading-calendar-aware EOD staleness header in the daily report) are DONE (through
  2026-08-18, all reviewed) — **ALL SIX paper-safe slices complete**. **✅ PHASE 6.8
  GATE PASSED + CLOSED 2026-08-20** (`/phase-gate`, worker stopped for a quiescent dev
  DB: backend 1477 · parity 16 · walkforward 9 · replay 19 · frontend 375 · cargo ok;
  §8 drift gate clean = frozen engine untouched; `make analysis` smoke green) — **the
  Phase-6 branch was merged to `main` (fast-forward); push is manual and PENDING the
  user.** Remaining = the gated, non-blocking research track (R1/R2/F1). **paper day-1
  is STILL DEFERRED until the user explicitly says "proceed"** — the merge does not
  start the paper clock. Nothing auto-advances — the NEXT menu lives in the PHASES top
  block (next after push = MCE slice 2, index-OHLC ingestion).
- **Single-factor entries are BLOCKED since the R-track entry-quality overlay**
  (`app/signals/entry_quality.py`, frozen engine untouched, overlay pattern). The
  confluence confidence normalizes by the weight of factors that *scored*, so one 0.8
  factor reads 80% and passes the ≥70% gate — that is exactly how SRTL entered (BUY on
  RSI_DIVERGENCE alone, ₹39 micro-cap × 2666 qty → −₹3.5k). Two moded checks:
  **factor-diversity** (`entry_diversity_gate_mode`, **active** — enforces the "≥2
  factors, never a single indicator" rule) blocks <2 scoring factors or one factor >90%
  of the confluence; **stop-too-tight** (`entry_sl_atr_gate_mode`, **shadow** — tunable)
  flags `|entry−SL| < k·ATR`. A sidecar (`entry_quality_shadow.py` → `make analysis`
  writes `entry-quality-shadow-<date>.md`) accrues flagged-vs-passed outcomes + an sl_atr
  flip-readiness banner. The *context* complement — sector/index relative-strength +
  fundamentals + news as GATES/MODIFIERS (never additive) — is the **MCE**
  (`docs/phases/phase-MCE-market-context-engine.md`), the phase after 6.8.
- **Anti-chase overlay since 2026-08-21** (`app/signals/chase_guard.py`, shadow-first,
  `chase_gate_mode`, the 6th order-path overlay): the entry-*timing* complement — blocks when
  the live LTP (read via `get_live_ltp`) has run > `chase_max_r` (0.33) × 1R past the signal's
  entry (reward:risk gone; risk and reward move OPPOSITE on a chase). Direction-aware, fail-open
  on no-price/zero-risk, stamps `broker_payload["chase_gate"]` (distinct from the broker's
  post-fill `chase`). Sidecar `chase_shadow.py` → `chase-shadow-<date>.md`. Evidence: chase_r ≤
  0.33 → +₹275 avg/62% win (37 trades), the 2 past 0.33R both losers. AlertBell also now surfaces
  SL/TP/R:R + confidence + signal age + validity window per entry alert (frontend-only).
- **MCE is IN PROGRESS — slices 1–4 built 2026-08-20 + slice 5a built 2026-08-21, all mode
  `shadow`/off (no money-path change).** Slice 1 = `sector_rs.py` (RS overlay); slice 2 = index price
  store (`index_ohlcv_1d`, migration `b8c9d0e1f2a3`) + `benchmark.py` + wiring; slice 3 = sector-RS
  shadow sidecar + flip to shadow; slice 4 = the market-regime gate (200-DMA + VIX, `market_regime.py`
  + `market_regime_shadow.py` + `scripts/backfill_indices.py`); **slice 5a = the liquidity junk gate
  (`liquidity_guard.py` + `liquidity.py` + `liquidity_shadow.py`)** — blocks entries too illiquid to
  exit (median daily traded value ₹=close×volume < floor, side-independent; the SRTL archetype), from
  ohlcv_1d (real data now, no backfill). All order-path overlays fail-open in a `begin_nested`
  savepoint; the verdict stamps live in an `_overlay_stamps` helper. **Index source = Option B (real
  index OHLC via the NSE indices CSV `vix_service` already downloads — NO Kite dep.)** quant-verifier
  PASS ×5 + bug-hunter ×3 (findings fixed). ⚠ **5a DEEP-DIVE (2026-08-21) verdict: DON'T flip the
  liquidity gate active.** Illiquid set net-*positive*, liquid net-*negative*, robust across floors +
  median + win-rate; and **SRTL is the sole illiquid+diversity-flagged trade — the ACTIVE diversity
  gate already catches it**, so liquidity is redundant for that archetype AND would cut a net-winning
  set. **DECISION (user): keep 5a shadow; reframe liquidity later as a position-sizing / slippage
  MODIFIER (execution-realism), not an entry P&L gate.** The finding also QUESTIONED 5b — and **F1
  (2026-09-07) then CONFIRMED it: no size signal in the book, so 5b's market-cap floor is DROPPED.**
  **⛔ slice 5b (the market-cap floor + writer) is DROPPED**; **slice 6 (news veto) is DEFERRED**
  (2026-09-07 — none of its 3 preconditions holds). **D3 RESOLVED 2026-09-08: the `market_cap` writer
  needs NO vendor and NO XBRL scraper** — a free NSE-`/api/` `issuedSize × price` path exists (the
  surface the app already uses for FII/DII); build it only when a consumer appears
  (`docs/analysis/market-cap-source-spike-2026-09-08.md`). ⛔ **The index backfill was DESTROYED with
  the dev DB on 2026-09-07 and has NOT been redone — `index_ohlcv_1d` holds 51 rows and
  `india_vix_daily` 17 (measured 2026-09-10). Every market-regime / sector-RS overlay is
  therefore unevaluable until it is re-run.** Shadow→active flips need the R-track (§8-on-≥2y + sign-off). Plan in the phase-MCE doc.
- **The provisional breadth-flood fix is MERGED on the Phase-6 branch (`c1b4752`,
  cherry-picked 2026-08-20 — the source branch had diverged so `--ff-only` was impossible).**
  `live-worker`'s hot set no longer floods with breadth alerts (near-trigger = signal-bound
  only, so watchlist stocks get scored again); cycle health is durable in
  `provisional:health:{day}` (7-day TTL). ⚠ The forward watch has NO scheduler — run `cd
  backend && uv run python scripts/provisional_health.py --days 7` yourself each session
  (protocol: `docs/analysis/provisional-health-watch.md`). The running `make live-worker`
  picks up the fix on its next restart. See the `provisional-hotset-breadth-flood` memory.
- **Circuit-band overlay since 6.8.3** (`app/signals/circuit_guard.py`, shadow-first,
  `circuit_gate_mode`): skips entering a name within `circuit_proximity_pct` (1.5%)
  of its ADVERSE band (long→lower, short→upper) — an un-exitable trade. Bands from a
  market-hours task's batched Kite `quote()` → Redis `circuit:{stock_id}`; the order
  path only READS the cache, fail-open. Frozen engine untouched; `off` = true no-op.
- **The flat DEPOSITORY charge is levied since A29 (2026-09-05)** — `fees.ZERODHA_EQUITY
  .dp_charge_per_sell = ₹15.34`, on the **delivery SELL leg only** (shares leaving the demat
  account), **flat regardless of quantity**, added after the GST line because the published figure
  is GST-inclusive, and itemised as `dp_charge` in the audit breakdown. **Measured when it shipped:
  all 105 closed positions were delivery, so ₹1,610.70 had never been levied — 15.8% of the book's
  entire loss; realised should read −₹11,829 not −₹10,218.** ⚠ **It is the ONE cost that is not
  neutral to position size:** 100 × ₹39 pays **61.6 bps** of round-trip charges vs 22.4 bps for
  400 × ₹2,500 — and small is exactly what the notional cap produces and what live trading (₹1L,
  1–2 positions) will be. ⚠ `min_charge_per_leg` exists but defaults to **0 on purpose** — the
  Zerodha schedule has no per-trade minimum, and inventing one would fabricate a cost rather than
  model one. ⚠ **Forward-only:** closed rows keep their under-costed `realized_pnl`, so that
  ₹1,610.70 is what history *should* have cost, not a restatement. ⚠ Applied to whichever leg is the
  SELL, so a delivery SHORT is charged on ENTRY — an artefact of the paper model, since a
  cash-equity delivery short is not actually possible.
- **Order size is priced against the STOCK, not just the book, since A37 (2026-09-05).**
  `paper_broker.participation_bps` charges **`k × participation²`** bps, participation = order
  value ÷ **median daily traded value** (`load_median_traded_values`, batched, median taken in
  Python with Decimal because `percentile_cont` returns a float). Quadratic, calibrated to
  zipline's `VolumeShareSlippage` (k=0.1): 2.5% ≈ 0.6 bps · 10% ≈ 10 · 20% ≈ 40 · 50% ≈ 250.
  Applied on **both** fill paths (a thin stock often has NO book, so spread-path-only would exempt
  the very names it exists for) and on **every mark surface** (A31 — exiting a fifth of a day's
  volume costs what entering cost). **Real book 2026-09-05: ADROITINFO sits at 16.95% of daily
  volume on ₹33k notional — 28.7 bps, previously the 2 bps floor; only 3 of 29 positions are
  charged >1 bp.** ⚠ **NOT a partial-fill cap** — zipline's 2.5%-of-bar refusal needs partial
  fills (Phase 7), so this PRICES the trade and suppresses no signal. ⚠ It **overlaps** the
  top-of-book term by design (instantaneous depth vs daily capacity; an illiquid name trips both),
  bounded by `paper_slippage_max_bps`. ⚠ Too little history ⇒ **absent, not zero** — unknown fails
  OPEN; zero would mean infinite participation. ⚠ The **sizing refinement pass** now re-prices
  whenever a size exists, not only on the spread model — participation makes the FLAT fill
  size-dependent too. ⚠ **Backtest untouched** (FROZEN engine), same blocker as A38's backtest leg.
- **Marks are priced by the SAME model as fills since A21 (2026-09-05)** — `paper_broker.exit_mark`
  routes every unrealized-P&L surface through `simulate_fill` with the **exit** side, so a long
  marks toward the BID and a short toward the ASK. Before it, fills paid the real half-spread while
  marks used the untouched last trade, making reported open MTM optimistic by ~a half-spread per
  position across ~29 positions. Wired into `update_position_pnl` (API list · summary · monitor,
  each batching ONE `get_live_depths` MGET — never a per-position Redis read) and
  `_open_book_mtm`. **Reporting-only: nothing branches on `unrealized_pnl`** (every exit decision
  is taken on the live tick), so this changed a recorded number and no behaviour.
  ⚠ **`_round_tick` is DIRECTIONAL since 2026-09-05** — a BUY ceils, a SELL floors. `ROUND_HALF_UP`
  to the *nearest* tick could carry an off-grid price back PAST its reference, handing us a fill or
  mark BETTER than the last trade: **4.9% of 20,000 real 1m closes**, and **27.2% of our closes are
  off the ₹0.05 grid**. This is the module's stated "can only make a fill worse" contract, and it
  applies to ENTRY fills too. ⚠ **The one limit that remains:** the HISTORICAL mark cannot be a true
  mark-to-bid (depth is Redis-only, 60 s TTL, never persisted — `_open_book_mtm` always takes the
  flat floor; using *today's* book for a past cutoff would be genuine look-ahead, not just
  imprecision). ⚠ `exit_side_for` accepts **LONG/SHORT only and raises on BUY/SELL** — `compute_pnl`
  treats non-LONG as SHORT, so accepting an order side would mark down *and* value short = a phantom
  gain. ⚠ `conftest` zeroes `paper_slippage_bps` for the suite — a flat-path test that does not set
  it passes vacuously, which has now produced tautological assertions twice.
- **Paper fills are spread-aware since 6.8.2**: when the live `depth:{stock_id}`
  book is fresh, the haircut is the real half-spread + a size-vs-top-of-book
  impact term, floored at `paper_slippage_bps` so a fill is never *cheaper* than
  the old flat model and fails open to it when depth is absent. This was not
  cosmetic — **82% of live NSE books have a half-spread wider than the flat 2 bps**.
  Paper P&L before and after 2026-08-17 is therefore **not comparable**; the
  30-day clock needs a reset. Backtests are untouched (they never read depth).
- **The depth feed asserts its own tick MODE since A25 (2026-09-05)** — `app/broker/tick_mode.py`,
  wired into BOTH live paths (`live_worker._ffi_batch`, `tick_consumer._process_batch`). Kite is
  documented to send **quote-mode ticks on a MODE_FULL subscription**; such a tick has no `depth`
  key, so `depth:{stock_id}` stops refreshing, expires at 60 s, and 6.8.2's spread-aware fills fall
  back to the flat floor — **paper fills quietly CHEAPER than reality**, every step of it our own
  deliberate fail-open. ⚠ **Never observed against us** — this is a detector for a documented
  broker behaviour, not a bugfix. **It detects and counts; it does NOT reopen the socket** (repo 8
  does; we judged a reconnect loop on a misread worse than the degradation). Two counters, cause
  and symptom, kept separate: `degraded` (mode ≠ full) vs `depth_missing` (**tradable** full-mode
  tick with an unusable book — index packets are full mode and bookless BY DESIGN and are excluded).
  ⚠ **A mode-less tick is `unknown`, never an alarm and never a durable write** — recorded/replayed
  ticks carry no `mode`, and alarming would cry wolf every replay run. Surfaces: heartbeat stats
  (`mode_degraded`/`mode_unknown`/`depth_missing`) · a rate-limited warning · a durable
  `tickmode:health:{day}` hash (7-day TTL, HSET-overwrite because counters are cumulative since
  worker start) rendered by `make analysis` beside the 6.8.6 feed alarm. A clean feed costs **zero**
  extra Redis round trips.
- **Every ratio goes through `app/core/ratios.py` since H6 (2026-09-05).** A degenerate ratio has
  THREE honest outcomes and the code conflated them: **UNDEFINED is `None`, NEVER `0.0`** (a
  zero-risk signal returned the same number the code prints for the *worst possible* R:R, so "not
  assessable" and "terrible" were indistinguishable); **OFF-SCALE is clamped AND MARKED** (`>50` —
  printing a truncated 228 as "50.00" reads as a real 50:1 setup, worse than the artifact); NORMAL
  is the number. ⭐ **THE RULE: clamp what you REPORT, never what you DECIDE** — every gate computes
  its verdict from the raw ratio; `MAX_RR` is above every threshold that reads it (`rr_min` 1.0,
  `rr_floor` 1.0) so the two cannot disagree, and the ordering is pinned by test. **`MAX_RR = 50`
  was read off the book, not argued:** all 656 signals with levels give R:R p50 1.97 · p90 3.67 ·
  **p99 28.5** · max 228.06, and **exactly one row (0.15%) exceeds 50** — the tiny-SL artifact with
  a **2.6 bps** stop. ⚠ **Three constants, three DIFFERENT jobs — do not merge them:** `MAX_RR`
  (reporting bound on R:R) · `MAX_R = 9999.999` (**representability** bound from the `Numeric(7,3)`
  excursion columns, where overflow aborts a batch commit) · `WINSOR_R = 10.0` (**statistical**
  winsor bounding one trade's contribution to a mean). They were four literals in four modules, two
  disagreeing by 1000×. ⚠ **The FROZEN sites are untouched and deferred as H6-b** —
  `_compute_sortino` returns **0.0 when there are no losing trades** (an infinite Sortino reported
  as the worst possible score, and a §8 golden), `_compute_sharpe` guards `std == 0` by exact
  equality (a 1e-16 stdev ⇒ Sharpe ~1e15 into `Numeric(6,3)`), `metrics.avg_rr` uncapped into
  `Numeric(5,2)`.
- **Two report sections exist because "the engine produced nothing" was once
  indistinguishable from "the engine is broken":** §7 F&O engine health and §8
  intraday shadow layer. Both attribute a zero to a *reason*. When either shows
  a dark day, read the reason before concluding anything about a strategy.
- **The intraday profiles run in SHADOW** — real schedule, measured to outcome,
  never tradeable (the order path admits `status == 'active'` only). They are
  not activated because walk-forward returned negative risk-adjusted returns for
  all three. See `docs/PHASES.md` and `docs/phases/phase-06-plan.md` §6.4 for
  the promotion path. **Any tradeable statistic must filter `is_shadow IS
  FALSE`** — `signals.status` is a lifecycle field the sweeper overwrites, so it
  cannot carry provenance.
- **ENTRY/ELIGIBILITY AUDIT 2026-09-02 — the leak is ARITHMETIC, not stock picking.** On 99 resolved
  trades since 07-19: **expectancy −0.303R/trade** (37.5% win, avg win +1.14R, avg loss −1.17R;
  break-even needs 1.67R payoff). **Payoff is capped by construction** — `compute_levels` pairs a
  STRUCTURAL stop (swing pivot / EMA20) with an ABSOLUTE-% target (swing +6%, positional +15%), so
  R:R is an accident: **94 of 295 swing signals have R:R < 1**, and there is **no minimum-R:R gate
  anywhere**. **Tight stops are the ₹ sink** — 14 trades with stops <2% of price lost ₹25,951 at 29%
  win (fill cost is a fixed price amount; 6 of 10 fills on 09-01 pinned the 50bps impact cap ⇒ order
  ≈10× top-of-book). **Cohort split: 44 trades with ≥1 mechanical defect = −₹19,649; the 55 clean =
  +₹5,256 at 55% win.** **Displacement, not age, is the discriminator** (at-entry +₹9,830/55%; chased
  0.33–1R −₹12,789/22%) — the signal-age sidecar reports NO stale penalty, so `conviction.ts`'s
  age-decay rationale is not evidence-backed. Also: **overlays gate the ORDER path, not the DISPLAY
  path** (41 of 204 listed signals 409 on click); **portfolio heat 45.3%** of ₹1L over 23 positions
  (a CYCLE-1 sampler artifact; the 6% heat cap + a max-concurrent-position cap of 3 are BUILT in the
  RiskEngine, `off` now, flip at the cycle-2 reset — D4, 2026-09-08); the **entry price is literally yesterday's close**
  (`signal_service.py:236`) and the live entry zone is **symmetric ±0.5%**, so a BUY drifting DOWN
  into entry fires "Entered zone". Fix queue in the PHASES CONTINUE HERE block; **items 1, 2 and 7
  shipped 2026-09-02** (see the next bullet).
- **⭐ SINGLE SOURCE OF TRUTH FOR TRADABILITY = `app/signals/restrictions.py` (A38, 2026-09-05).**
  Every eligibility rule is declared ONCE in an ordered registry; the order path
  (`_load_restriction_context` + `restrictions.check(enforced_by=OVERLAY)`) and the display path
  (`eligibility.preview`, now a thin adapter) both walk it. **This RETIRES the old standing
  warning** that flipping an uncovered gate active meant hand-extending `eligibility.py` in the
  same commit — coverage is now DERIVED from each rule's `requires`, so a new live-state rule
  becomes "uncovered" automatically and an ACTIVE rule that cannot be judged is NAMED in
  `unassessed`, never silently cleared. Three fields carry the semantics: **`requires`** (+
  `requires_any` for "either price will do") · **`enforced_by`** (`OVERLAY` = settings-moded, run
  by the order path; `BROKER` = the paper broker's own unconditional pre-fill rejections, run by
  the preview only — the order path would otherwise double-reject) · **`as_of`**, mandatory, so a
  backtest can finally ask *"was this restricted ON THAT DATE"*. Behaviour was proven unchanged by
  differential fuzz (30,000 order-path cases, 0 block diffs). ⚠ **Adding a gate = adding one
  `Restriction` + its context loader; do not add a second sequence anywhere.** ⚠ Context is
  resolved **eagerly** (the price of a pure composer), so a blocked order pays for later gates'
  I/O. ⚠ **`"off"` is a TRUTHY string** — never `mode_a or mode_b`; use `_effective_mode`. That
  bug silently stopped writing the `entry_quality` stamp. ⚠ **CORRECTION (2026-09-05): that
  stamp has NO current reader** — `entry_quality_shadow.py` **recomputes** `eq.evaluate` from
  `Signal` rows using TODAY's `entry_min_sl_atr_mult`. The bug was real (a non-off gate must
  leave its verdict) but its stated significance was not. **The consequence is worth more than
  the bug: the sl_atr evidence is NOT point-in-time — tuning `entry_min_sl_atr_mult` silently
  re-partitions the whole historical flagged/passed split in every `entry-quality-shadow-<date>.md`.**
  Only `circuit_gate` and `chase_gate` stamps have readers today.
  ⚠ The **backtest still consults NO gate** and `app/backtest/engine.py` is FROZEN, so wiring it
  to the registry needs sign-off + an §8 regression + regenerated Rust fixtures.
- **The DISPLAY path is gated since 2026-09-02 — `app/signals/eligibility.py` is the single source
  of truth for "what would an ACTIVE gate do to this signal".** Before it, `place_order` ran seven
  overlays while `GET /signals/active` and `GET /signals/{id}` ran none, so 41 of 204 listed signals
  showed a Buy button that could only 409 (that is where the toasts in the entry_issue screenshots
  came from). `preview()` is pure (modes + thresholds are arguments), evaluates gates **in the order
  the order path does**, and passes the reason through **verbatim** — a contract test asserts the
  list's `block_reason` equals the order path's 409 detail. Stamped on BOTH endpoints via one shared
  `_apply_eligibility`; the detail endpoint loads a real ATR (AlertBell reads that one). Blocked
  rows are **still listed** — flagged with `⊘ blocked` + a disabled Buy — never hidden, so what the
  gates are doing stays visible. Covered: regime · diversity · sl_atr (with ATR). **NOT covered
  (needs live state): circuit · liquidity · chase · market-regime · sector-RS — all shadow today.
  ⚠ Flipping any of those ACTIVE means extending `eligibility.py` IN THE SAME COMMIT**, or the
  display/order drift returns; an ACTIVE gate the preview can't judge lands in `unassessed`, never
  in "clear". Also fixed the same day: **`size_for_fill` now takes a REQUIRED `side` and a
  DIRECTIONAL risk distance** (a BUY at/below its own stop sizes to 0 and is rejected — `abs()` was
  side-blind and opened positions already through their stop; one such row is still in the dev DB,
  the fix is forward-only), and both gate sidecars **print their real mode** instead of hardcoding
  "SHADOW: nothing is suppressed" (false for the 19 days the regime gate ran active).
  ⚠ **`settings` is an `@lru_cache` module singleton — a `.env` mode change does NOT reach a running
  backend/worker until it is restarted.** Verify a flip in the live process, not just the file.
  Review round (bug-hunter, same day) fixed 9 defects in the above and left **two PRE-EXISTING sizing
  holes open, both needing a decision:** (1) **HIGH — no minimum risk-distance floor and no notional
  cap**: a signal one tick from its stop (₹0.04/share risk) is accepted as **50,000 shares / ₹1.19cr
  notional on ₹1L capital**, which then pollutes the paper book, the R stats and the 30-day clock —
  the wrong-side fix closed the negative-distance half and left the near-zero half, which is worse;
  (2) LOW-MED — `used = abs(existing_entry - stop_loss)` invents risk, so a profitable long whose stop
  trailed above entry is wrongly refused a repeat entry (fix = directional `used` CLAMPED AT 0).
  Also durable: **there are FIVE Buy surfaces** (AlertBell · OpportunitiesTable · DashboardPage ·
  LiveSignalsPage · **StylePage**), all now routed through one shared `tradeBlock()` with the styles
  endpoint stamping the same verdict onto `SuggestionOut`. Grep `placeOrder` before claiming a UI rule
  is enforced. **The preview judges the POST-SLIPPAGE FILL, not the raw LTP** — an LTP comparison
  disagrees with the broker inside a half-spread band and false-BLOCKS tradeable signals. **The broker
  has TWO unconditional pre-fill rejections** — through-stop AND off-market (`allow_offmarket_entry`
  defaults FALSE, so before this every row read `blocked=False` outside market hours while the order
  path 422'd all of them). **`unassessed` reaches the client** and renders enabled-but-marked, because
  log-only made "unknown" indistinguishable from "verified clear". A **non-finite Redis LTP** would
  500 the detail endpoint (`Decimal("nan")` PARSES without raising and `ArithmeticError` misses it) —
  guarded in both `get_live_ltp`/`get_live_ltps`. **UI law learned the hard way
  (ui-reviewer FAIL):** never stack `opacity` on a state carrying safety copy — a row's 0.55 times the
  Button primitive's `disabled:opacity-50` gave 0.275 alpha and put "Blocked" at **1.52–1.99:1**
  against a 4.5 AA floor in all five themes; recede with a TOKEN, not opacity. And a **native
  `disabled` hides its own reason** (drops tab order + `disabled:pointer-events-none` kills the
  tooltip) ⇒ use **`aria-disabled` + a click guard** whenever the reason must be readable. Also:
  daybreak `--color-loss` was 3.95:1 on its own `-bg` (below AA for every existing hit_sl/rejected/
  sell pill) → red-700, measured 5.30:1. **Three agent reviews found 21 defects in this work after it
  passed its own green suite twice — the tests asserted what was INTENDED, not what the code did.** **`make typecheck` now runs `mypy app/ scripts/`**
  — it used to check `app/` only, and that hole hid a missed caller.
- **TWO PAPER CYCLES, NOT ONE (user ruling 2026-09-02).** Cycle 1 = the wide sampler running now
  (~5 entries/day, ~5-day holds ⇒ ~25 concurrent positions) to accrue evidence fast — **its 30-day
  clock is INFORMATIONAL.** Cycle 2 = the rehearsal: after CAS Stage 2 · MCE 5b + 6 · the
  tuning/promotions · the deflated-Sharpe bar · **Phase 7.1–7.4**, reset the clock and run **45–50
  trading days** on a heat-capped ₹1 lakh book — **that** is the binding go-live gate.
  **Phase 7 is now SPLIT by what paper can prove:** 7.1 RiskEngine single-gate (absorbs the circuit
  breaker + 6 overlays + notional cap + R:R floor + heat cap) · 7.2 BrokerAdapter port · 7.3 order
  FSM · 7.4 reconciliation/kill-switch/audit **all run BEFORE cycle 2**, because a 45-day rehearsal
  through the real ExecutionEngine gives the plumbing 45 days of runtime hours — and v1 Phase 7's
  four defects were exactly plumbing (`.claude/rules/testing.md`: "test the SEAMS"). Kite placement ·
  GTT · real partial fills · broker-book reconciliation wait until AFTER (only reality validates
  them); mitigate designing the adapter blind with a READ-ONLY Kite spike in 7.2. Plan:
  `docs/phases/phase-07-live-trading-plan.md`. **The heat cap is BUILT** inside 7.1's RiskEngine
  (6%, fails closed, `off`), **joined by a max-concurrent-position cap (=3) built for D4 2026-09-08**;
  both must not throttle cycle 1 (a 6% cap cuts entries ~74%, a 3-count cuts a ~25-position book far
  more), so both are `off` now and flip `active` at the cycle-2 reset.
- **Exposure now reports against BOTH denominators (2026-09-02).** `paper_sampling_capital_inr`
  (**reporting only** — never touches sizing) declares the notional scale the sampler represents, so
  the same 23 positions read as *45.3% of the ₹1L LIVE capital* and *9.1% of the ₹5L sampling scale*.
  `0`/absent = previous behaviour. **⚠ set `PAPER_SAMPLING_CAPITAL_INR` in `.env` + restart** or only
  the live figure prints. And `app/services/heat_counterfactual.py` (+ a `make analysis` sidecar)
  replays every entry against a 6% cap: **admitted 12 / skipped 35, capped −₹13,303 vs full −₹19,093
  (+₹5,790 total) but per-trade −₹1,478 vs −₹796 ⇒ the cap is a RISK control, NOT a profitability
  fix.** Two traps it taught: default the window to `user.paper_clock_started_at` (never
  `OUTCOME_EPOCH` — that spans the 08-17 sizing/fill-model cut and yields ₹5,663 risks against a
  ₹2,000 budget), and never report a cap verdict on TOTAL P&L alone (chronological admission selects
  by arrival time, not quality).
- **TWO SAFETY RAILS SHIPPED 2026-09-02 (user-approved), neither needing a spec change.**
  (1) **Per-position notional cap** (`paper_max_notional_leverage=1.0`, `_check_notional_cap`):
  risk-first sizing bounds a trade's RISK but **not its SIZE** — `qty = budget/risk_per_share` had no
  ceiling on `qty × price`, so a four-paise stop sized **50,000 shares = ₹1.19cr on ₹1L capital** and
  returned 201. Cap = capital × leverage, existing position counted, **reject never clamp**. ⚠ PER
  POSITION — portfolio-wide is the **heat cap** (now BUILT, `off`) plus the **max-concurrent-position
  cap (=3, D4 2026-09-08, `off`)** — both flip at the cycle-2 reset (45.3% heat was a cycle-1 artifact vs Elder's 6%).
  **This replaced the proposed `paper_min_risk_pct`**: a %-of-price stop floor is the wrong instrument
  (2% is comfortable on HDFC, a knife-edge on a ₹39 micro-cap) and `sl_atr` already measures it in
  ATRs at 17/20. (2) **R:R floor overlay** (`app/signals/rr_guard.py`, `rr_min=1.0`) — rejects a
  target closer than its stop: 11 of 190 listed signals. Shipped **ACTIVE 2026-09-02** on the
  argument that it is the ONE gate needing no forward-evidence bar because it enforces an IDENTITY
  (R:R<1 needs a >50% win rate merely to break even) rather than a claim about the tape.
  **⛔ REVERTED TO SHADOW 2026-09-03 — the premise was false.** The blocked cohort was the book's
  ONLY profitable one: **24 trades, +₹10,585, 63% win, 33% tp_hit** vs the allowed set's 77 trades,
  −₹26,792, 48% win, 16% tp_hit. Two mechanisms: a nearer target is mechanically EASIER to hit, and
  **R:R<1 is a PROXY FOR A WIDE STOP** (7.29% avg, zero tight, vs 4.38% and 11 tight) — wide stops
  are independently the good cohort, so the gate blocked wide stops. Backwards.
  **✅ MODE VERIFIED 2026-09-04** in both live processes (see the mode-verification recipe below);
  the `config.py` default was moved `"active"` → `"shadow"` the same day so a fresh checkout can no
  longer run the refuted state. **Re-promotion needs the deflated-Sharpe bar + a tail check, never
  the identity argument again**; raising the floor above 1.0 is doubly empirical (1.67 is fitted to
  our 37.5% win rate). **R:R and `sl_atr` are STRUCTURALLY DISJOINT — never deduplicate them** (a
  tight stop yields a LARGE ratio; R:R<1 needs a WIDE stop — 11 vs 21 signals, zero overlap, pinned
  by a test). Root cause stays `compute_levels` pairing a structural stop with an absolute-% target
  — but **D5 TESTED + CLOSED 2026-09-08: the geometry is NOT the lever.** A read-only, R-scored
  counterfactual (`scripts/tp_geometry_study.py`, riding the sanctioned `tp_rule` freeze-extension,
  no frozen edit, 1,152 swing+positional signals) showed **no constant-R:R target (1.0–3.0R) beats
  the frozen absolute-% target** (every paired ΔR negative, |t| ≤ 0.65; baseline itself −0.026R),
  and a higher R:R **damages the wide-stop majority** — the exact R:R-reversal mechanism. You can't
  manufacture edge at the exit from edgeless entries ⇒ `compute_levels` stays frozen, the leak is
  upstream in candidate generation — **but the queued generation lever R1 was tested the same day and
  REFUTED (D1 declined; see the R1/RVOL bullet below), so no queued item now attacks profitability.**
  Report: `docs/analysis/tp-geometry-study-2026-09-08.md`. Untested: a *structural* next-S/R target
  (strong prior it won't change the verdict). No §6 spec change.
- **HOW TO VERIFY A GATE'S LIVE MODE (recipe, since `.env` is hook-protected and unreadable).**
  `settings` is an `@lru_cache` singleton, so a `.env` edit reaches a process only when that process
  re-imports `app.core.config`. You cannot read `.env`; you do not need to. Three steps:
  (1) `cd backend && uv run python -c "from app.core.config import get_settings; print(get_settings().<knob>)"`
  — a fresh load reads the same `.env`, and because every gate's code default differs from the
  reverted value, a mismatch with the default proves `.env` is overriding;
  (2) find when each live process last re-imported config — `ps --ppid <uvicorn-pid> -o pid,lstart,cmd`
  gives the `--reload` CHILD's start time (the parent PID does NOT restart on reload, so reading the
  parent is the trap), and `ps -eo lstart,cmd | grep celery` gives the worker's;
  (3) compare those against the flip's own timestamp — `git log -S'<changelog heading>' --format='%h %ad' --date=iso -- CHANGELOG.md`.
  Child-start AFTER flip-time ⇒ the live process holds the current value. Worked example
  2026-09-04: R:R revert committed 09-03 09:34, uvicorn reload child started 09-03 12:28, celery
  worker 09-04 08:37 ⇒ both live on `shadow`.
- **⛔ WATCH MODE / CAS ACCRUAL WAS DESTROYED — restart it (corrected 2026-09-10).** Stage-1 accrual
  did finish healthy on 2026-09-04 (1,664 rows / 8 sessions), but the 2026-09-07 dev-DB loss took it:
  **`cas_daily` holds 43 rows across 1 session** (measured 2026-09-10). The Stage-2 overnight-reversal
  result (ρ −0.272) is therefore **not currently reproducible**, and its "re-run at ≥30 sessions"
  trigger restarts from zero. **CAS accrual is real-time-only and cannot be back-filled**, so every
  day `make worker` is not up across 15:15–15:33 IST is a session lost permanently. The capture remains a
  Celery-beat task, so if accrual resumes, `make worker` must be up across 15:15–15:33 IST and a
  missed window still cannot be back-filled.
- **⭐ THE PROMOTION BAR, IN ONE NUMBER: t ≈ 3.6 on the trade series (H8, validated 2026-09-04).**
  `app/services/deflated_sharpe.py` was rejecting every gate, so `app/services/dsr_control.py` +
  `tests/test_dsr_control.py` (14) test the *instrument*. **It is SOUND** — it rejects noise (1.10%
  of best-of-20 zero-edge selections clear, against a 5% design allowance; 0.00% of random
  partitions) **and** accepts real edges (80% power at a true per-trade Sharpe of 0.52). Restated as
  a plain t-statistic the bar demands **t ≈ 3.6, and the hurdle is FLAT IN n** (3.76 at n=30 → 3.55
  at n=1000) — just above Harvey/Liu/Zhu (2016)'s recommended **t > 3.0** for a new factor. Two
  consequences that change how banners are read: **(1) more data never lowers the bar** (the
  benchmark falls as `1/√n` while the required t stays put — that is why MinTRL returns `None`), so
  "keep accruing" is only ever right when the point estimate is already ahead; **(2) power is ~0
  between t ≈ 2.6 and 3.5**, so *failing* is not proof of no edge — **record the t, not just the
  pass/fail.** ⚠ H8 as specified in the findings doc was insufficient (it asked only "does the bar
  reject noise", which a bar that rejects everything passes trivially); the power arm is the half
  that made the verdict readable. Report: `docs/analysis/dsr-negative-control-2026-09-04.md`.
- **⛔ GATING IS CLOSED AS A PROGRAMME (2026-09-04) — the leak is upstream, now demonstrated.**
  Eight shadow gates over three months, two promotions both refuted (regime, R:R), and the best
  surviving candidate — **`sl_atr`, which passes all three readiness guards** — sits at **t ≈ 0.41
  against a 3.6 hurdle, short by ~9×**. **`sl_atr` is DECIDED: NO; its 20-trade trigger is
  WITHDRAWN** (the count was never the constraint). No partition of these trades will clear the bar
  because the trades carry no edge to partition. **Selection has been optimised; what GENERATES the
  candidates has not.** The only ACTIVE order-path gate remains `entry_diversity`, which enforces a
  stated hard rule rather than a measured edge — that is why it is exempt from this.
- **✅ BUCKETS A AND B ARE COMPLETE (2026-09-06) — the next build is Phase 7.1–7.4**, queued on
  branch **`feature/pre-cycle2-hardening`** (approved, cut from `feature/phase6-overlay-walkforward-retune`
  @ `518b84f`). The ordered queue, its dependency graph and the open decisions live in
  **`docs/phases/pre-cycle2-queue.md`**. All 8 Bucket-A items and all 11 Bucket-B items have code
  **and** tests on disk — verified against the artifacts, not the checkboxes (**W1**), which is how
  the findings doc's own Bucket-B table was caught four items stale. **Bucket C is 7 of ~60**
  (W1–W5 · A11 · A40); the rest builds *under* cycle 2's clock by design.
  **Start with 7.0, a DESIGN PASS** — A33 + A42 + A35 are one problem, not three — then 7.1
  RiskEngine (equivalence-pinned, absorbing the heat cap) → 7.2 BrokerAdapter (+ a READ-ONLY Kite
  spike) → 7.3 order FSM → 7.4 reconciliation. ⚠ **NO decision blocks cycle-2 start.** **D2** (R2
  build-or-drop) is **PARKED to cycle-2 end** (user 2026-09-08 — R2 provisionally dropped; final call
  waits on cycle-2 forward evidence; **Claude flags it at cycle-2 end via the PHASES review calendar**).
  **D6** (reconciliation matching key) is post-cycle-2. ✅ **D3 RESOLVED 2026-09-08** —
  free-source spike: NO vendor needed (free NSE-`/api/` `issuedSize × price` path, the surface the app
  already uses for FII/DII; keystone retired; build deferred until a consumer —
  `docs/analysis/market-cap-source-spike-2026-09-08.md`).
  ✅ **D4 DECIDED 2026-09-08** — minimal rails: notional cap (1.0) + 6% heat kept, and a
  **max-concurrent-position cap (=3) BUILT** in the RiskEngine (`position_count_cap_mode`,
  `max_concurrent_positions`; `off` → flips `active` at the cycle-2 reset; hard design rail, no DSR bar,
  adding-to-existing exempt); concentration is a cycle-1 artifact so a count, not a heat %, binds;
  correlation/sector deferred. ✅ **D5 CLOSED + D1 DECLINED 2026-09-08 — both profitability levers spent.**
  D5: `compute_levels` geometry is NOT the lever (keep the tourniquet). D1: R1-RVOL refuted read-only
  (elevated RVOL mildly inverse; injecting it −0.291R at t=−2.91) and VWAP untestable ⇒ R1 dropped, no
  frozen change. **With selection, exit geometry AND the queued generation lever all spent, no queued
  item attacks profitability — finding a new lever is the open problem.**
  ⚠ **"The rest of Phase 6 / 6.8" has no unbuilt slices** — both are GATE PASSED + CLOSED; what is
  left is the gated research track R2/F1 (**R1 dropped 09-08**) plus three forward-evidence loops
  (regime **decided**, momentum ×1.5 **stalled** at 3 minted / 0 resolved, pair df-vs-adf accruing).
- **⚠ THE WEIGHT-20 `DOW_TREND` FACTOR IS UNREACHABLE ON THE DAILY TIMEFRAME (2026-09-10).** Measured
  by `backend/scripts/engine_selectivity_probe.py` (read-only, rerunnable) over **4,511 daily panels**:
  the spec's heaviest factor — "the macro context", weight 20 — scores on **3 of 4,511 windows (0.07%)**
  and **cannot score by construction**. `run_all_factors` calls `dow_trend_factor(lookback=20,
  swing_n=5)`; in a 20-bar window an n=5 pivot can only sit at index 5…14, any two differ by ≤9 < 11 so
  their windows overlap and both can be the max only on an exact tie — yet the function needs **two**
  highs AND **two** lows. A synthetic HH+HL staircase returns `0.0 — "Not enough swing points"`. ⇒ **the
  tradeable swing engine carries NO trend-structure input**, and the absence is SILENT because the
  confidence denominator counts only scoring factors. Corroborated by **Minervini 0/91** and the closed
  book's **beta +0.92 / alpha +0.0010**. ⚠ **SPEC defect, not an implementation bug** (§2.4 specifies
  both parameters) — `SIGNAL_ENGINE.md` is hook-protected, **nothing was changed**. Act on it with the
  **read-only injection test that refuted RVOL** (no frozen edit, no sign-off needed); prior is guarded
  — an injected graded factor can DILUTE through the normalisation. Full write-up +
  the rest of the probe (a "≥70%" signal is a median of **3 of 15 factors worth 30 of 160 weight
  points**; gate pass rate 4.19%; the swing stop is the last n=5 pivot ANYWHERE in 300 bars, p90 16%
  away and 18% of the time ABOVE the entry, so **52% of gate-passing signals die at the level stage**;
  and **cost in R is a hyperbola in stop width** — 0.05–0.11R at the median 5% stop, **0.40–0.83R at
  the p10 0.65% stop**) in **`docs/SYSTEM_REVIEW_FOR_QUANT.md`**, the standalone document for presenting the
  system to an external quant.
- **⚠ THE `positional` CLASS IS ONE FACTOR'S FOOTPRINT, AND ITS STOP HAS THREE IMPLEMENTATIONS
  (2026-09-10).** `docs/POSITIONAL_REVIEW_FOR_QUANT.md` + `backend/scripts/positional_probe.py`
  (read-only; the frozen scorer AND the frozen `_simulate_trade` are imported and CALLED, never
  reimplemented). A 1d signal is positional **IFF `MULTIBAGGER_EMA` scores** — the `1w` route is
  never run. That factor is appended ONLY when it fires, always scores exactly **+0.9**, and has no
  bearish branch ⇒ **alone it yields confidence exactly 90%** (9/10, the top bucket; live example
  `BUY AFFLE — Multibagger Ema, 90% confidence`). **430/430 gate-passing panels are BUY —
  structurally long-only**; 18.6% rest on that one factor. ⭐ **`compute_levels` assigns
  `max_sl_pct=15.00` for positional then SKIPS the cap check for exactly that class** (dead
  variable), and **`signal_service` passes `ema20_daily` while `profiles/pipeline.py:367` and
  `backtest/engine.py:322` do NOT** ⇒ flat 5%, R:R exactly 3.00 (live: **26 of 40 trades on the
  flat 5%**). ⇒ **the backtest validates a stop rule the primary minter never produces**, and
  `_simulate_trade` walks to the END OF DATA so the 30-day validity is untested. Paired on
  identical panels the rules are **NOT separable** (ΔR −0.120, t −1.47) — a CORRECTNESS defect,
  not a proven P&L one. ⭐ **The class selects AGAINST trend:** `PRICE_VS_EMA` fires on **9.1%** of
  positional panels vs 63.4% generally (`|EMA20−EMA200| ≤ 2%` IS a converged MA stack) and
  `DOW_TREND` scored 0/430 — second confirmation of the dead-factor finding. ⭐ **The notional cap
  is a `risk_pct/leverage` (=2%) MINIMUM-STOP-WIDTH rule in disguise — the capital CANCELS**;
  it rejects 28.4% of positional signals and was never measured as selection, so **measure any
  future stop-width rule AGAINST it, not in addition** (W2). Outcome gross: 30-day horizon
  **n=362, meanR −0.102, win 28.5%**, no bootstrap interval excluding zero, and **enforcing the
  30-day horizon makes both stop rules WORSE**. Stop width is the strongest gradient (before
  costs): <2% **−0.306R at 9.6% win** → >10% +0.543R at 62.5%. Same panels under SWING rules:
  −0.213R/37.4% vs −0.292R/16.1%, paired ΔR −0.079 t −0.53 (**not significant — the relabel is
  supported by no evidence either way**). ⚠ **No realised per-trade positional record exists**
  (39 of 40 last seen `open`; closed trades drop out of the report tape). ⛔ **A FOURTH harness
  defect, NOT positional-specific: `_simulate_trade` books a GAP-THROUGH-STOP fill as ~+1R**
  (3-bar repro: close 100 / stop 99 / next open 95 ⇒ exit 99, `hit_sl=True`, +4.211% = +1.000R).
  Live is immune (`paper_broker:544-554`); it flatters TIGHT stops, and **every study built on
  `_simulate_trade` inherits it** (the 1,975-trade headline included, magnitude unmeasured).
- **⛔ THE `security_analysis` READING STUDY IS CLOSED — FIVE NEGATIVES, NOTHING BUILT (2026-09-10).**
  All 14 PDFs in `docs/reading/security_analysis/` read against the user's entry/alert-timing question;
  synthesis + citations in `docs/reading/security-analysis-folder-takeaways-2026-09-09.md` (§1 rates each
  book — only 5 of 14 bear on it; **Graham & Dodd, which the folder is named after, explicitly argues
  AGAINST confirmation-buying** as speculation rather than investment). **The books agree on a REAL gap:**
  we have SETUP → MANAGE with **no TRIGGER stage** — `signal_service.py:236` sets `entry = last completed
  close`, `compute_levels` derives SL+TP from it, and `live_levels.py:217` alerts on a **symmetric ±0.5%
  band**, so a BUY drifting *DOWN* fires "Entered zone". **Their remedy was MEASURED, not adopted, and it
  LOSES — twice, on independent samples.** (1) Market-wide, 108,506 stock-days: selection is real (+1.018%
  vs −0.915% next-day) but **fully priced into the trigger**; properly differenced with an overlap-corrected
  t, **H-A is SIGNIFICANTLY WORSE at every horizon (t −2.94…−3.51)**, and Weinstein's 2% ceiling changes
  nothing (t −2.55…−3.35). (2) On **1,975 of our own minted signals**: SELECTION +0.133…+0.286R vs FILL COST
  −0.216…−0.292R — ⚠ **the cost is t −7.2…−9.4 while every benefit is t ≤ 0.4**; at 3d/5d the rule is
  significantly worse (t −2.45, −2.87). The cost is **not** target truncation (re-anchoring the TP to the
  fill moves ΔR only −0.262 → −0.268). Also refuted: Weinstein's 150-DMA stage filter · Elder's Market
  Thermometer · Carter's squeeze (3,610 fires, |t| ≤ 1.09 market-neutral) · Weinstein's overhead supply
  (never significant once overlap was corrected, and its reachability gradient collapses +13.8pp → +4.2pp
  inside the low-vol tercile). ⭐ **What the reading yielded: (a) Brooks' trader's equation EXPLAINS the R:R
  reversal STRUCTURALLY** — "whenever one of risk/reward/probability is unusually good it is offset by the
  others" ⇒ the R:R≥1 floor blocked the high-probability cohort *by construction*; this is not bad luck, it
  independently explains D5, and **the floor must never be re-promoted on the identity argument**. (b) Five
  faith-based builds pre-empted *before* the build. (c) **The alert-timing number: of 1,975 signals, 60%
  confirm on day 1, 70% by day 2, 80% by day 5, 20% NEVER within five sessions.** (d) **ONE untested thread
  — 12-month PRICE momentum** (D1 refuted *volume*/RVOL; price momentum surfaced here as the *control that
  killed* the overhead effect, so weaker evidence than it looks, and has never been tested).
  ⚠ **A methods trap it produced:** measuring a forward return **from the trigger price** spans the rest of
  the entry day and rewards a bar that already ran — it manufactured a 1.8pp "effect" (t −17.8/+10.1) that
  vanished measured from the close. Both bases are printed in the report so it cannot be re-discovered.
  ⚠ **Every opening-range idea is UNTESTABLE** — `ohlcv_5m/15m/1h` died 09-07; restoring intraday capture is
  a prerequisite and accrues only in real time, so start it BEFORE cycle 2.
  **Only actionable item: make the entry zone DIRECTIONAL** (`live_levels._signal_levels`; the
  direction-aware PDH/PDL `cross_up`/`cross_down` machinery is already in that file, just unwired) — a
  **correctness fix to an alert, explicitly NOT a P&L claim. NOT BUILT.** Scripts (read-only, SELECT-only,
  frozen engine untouched): `entry_confirmation_study.py` (its walker is asserted trade-for-trade against
  `_simulate_trade` on 400 trades) · `confirmation_base_rate.py` · `squeeze_study.py` ·
  `overhead_supply_study.py`. The source PDFs are **gitignored** (158MB, copyrighted).
- **⚠ THREE MEASUREMENT DEFECTS FOUND IN OUR RESEARCH HARNESS (2026-09-10, quant-verifier) — TWO OF THEM
  AFFECT THE ALREADY-CLOSED D1 AND D5.** These are about the *instruments*, so every future analysis script
  is exposed. (1) **A daily cross-sectional t is NOT enough** for overlapping forward windows: averaging the
  cross-section kills same-day dependence but not the overlap between day t and t+1, which share k−1
  sessions of the same future. Under H0 the naive t has sd **0.98 at k=1, 3.32 at k=10, 4.45 at k=20**, so a
  naive "t = 9" is ≈1.9σ — one gradient looked decisive and **was never significant**. Use
  **`app.services.block_bootstrap.newey_west_t(series, lag=k−1)`** (NEW 2026-09-10, Bartlett kernel, 5 tests
  incl. an H0 canary that first REPRODUCES the inflation) and print the naive t beside it. Sparse cohorts
  are barely affected. (2) **⛔ "the CA-clean window from 2023-07-03" IS A FALSE CLAIM** — `ohlcv_1d` is
  CA-UNADJUSTED throughout and **49 unadjusted corporate actions sit in the top-250-liquid universe, 35 of
  them ≥40% halvings** (SHRIRAMFIN −81.1%, COFORGE −79.7%, ANGELONE −90.1%, DIACABS +3118.6%). Cost measured:
  dropping **4 of 1,979 trades removed ~+49R of FAKE PROFIT**, more than that study's entire original loss
  (mean R −0.020 → −0.045). Filter |close-to-close| > 25% out of any forward window / holding span and print
  the count. ⚠ **`scripts/tp_geometry_study.py` (closed D5) and `scripts/rvol_factor_study.py` (closed D1)
  assert the same false claim and have NOT been re-run — check before either is cited again.** (3)
  **Averaging R without winsorizing lets ~10 trades own the answer** — the entry study's ten largest |R|
  trades ALL had stops of 0.23%–0.86% and contributed **+128.4R against a −89.7R total**. Use
  **`app.core.ratios.WINSOR_R` (10.0) via `clamp_ratio_f` wherever R is AVERAGED** (the convention
  `entry_attribution.py` already follows — W5). Robust alternatives: the **median** R and a **paired** ΔR on
  identical signals. ⭐ **The generalisable rule: an instrument never run against a known null, a
  known-contaminated input and a known tail artifact has not been validated** — `instrument_self_validation`
  applied to the harness, not the metric. All three defects made a *negative* look better than it was.
- **The plan it came from is `docs/quant-agent-findings.md`** — a 30-repo external
  review (2026-09-03/04, 4,358 lines) producing **91 items in five queues** (analysis · UI ·
  architecture · testing · workbench), bucketed by **when they must land**. Governing rule:
  **anything that changes a recorded number must land BEFORE cycle 2's clock starts** (we already
  reset one clock this way on 2026-08-17); ~60 of the 91 touch no recorded number and build *during*
  accrual. **Bucket A** (~7 d, freeze the numbers): A38 point-in-time `Restrictions` · A21
  mark-to-bid · A37 participation cap · A29 DP charge · A23 effective-dated fees · A26 hot-set
  refusal · A25 tick-mode assert. **Bucket B** (~5 d, the instruments): H8 noise control · H1 block
  bootstrap · H12 beta/IR · H2 benchmark · H11 MinTRL headline · T11 · H4 · U4 · H3.
  **Zero external code adopted**; six findings were about *our* code, plus one validation (our PSR
  is correct where QuantStats' is wrong). ⚠ **The plan buys evaluation, not edge** — and BOTH named
  levers are now spent: `compute_levels`/exit geometry (D5) and the queued generation lever R1/RVOL
  (D1) were **both tested and refuted 2026-09-08**. No queued item attacks profitability; the edge
  question is unresolved and finding a new lever is the open problem.
- **The HORIZON / stop-width finding (2026-08-25, `docs/analysis/horizon-recovery-2026-08-25.md`)** —
  from the desk observation that stopped-out names "failed for the day then recovered". **11 of 16
  stop-out losers traded back through their entry, median 1 trading day** — but "just hold" is far
  worse (−₹54,701 on one name), so the bounce is transient. The split is **stop width ÷ average daily
  range**: <1.0× → 8/8 recovered at −1.45R realised; ≥1.0× → 3/8 at −1.17R. Tight stops also
  **overshoot −1R** (−1.70R under 0.25×) because the honest 6.8.2 fill cost is a fixed price amount.
  ⚠ **Measure stop-width counterfactuals in R, never ₹** — risk-first sizing means a wider stop buys a
  smaller position, so a constant-qty replay tests bet size, not stop placement (that error inverted
  the first pass). Risk-normalised over all 82 closed trades: planned SL −0.05R → 1.5×range +0.11R,
  gain entirely inside the tight-stop group. **This independently reproduces the `sl_atr` shadow gate
  at its exact 1.0× threshold — it still STAYS shadow (12/20 readiness).** Second half: **we grade
  multi-day trades on a one-day clock** — ≥1R on the entry day is 12% for both classes, but within
  their own horizon **swing 36% / positional 54%**, +1R typically on **d+3**. ⇒ two safe reporting
  changes (horizon-aware ≥1R line; surface the already-stamped `sl_atr_mult` at entry). **REJECTED:
  widening stops on the money path** (retrospective, daily-bar; and *reject, don't clamp* means don't
  take the trade) **and holding through stops.**
- **`docs/STATUS.html` is the readable mirror of the PHASES top block** — rebuilt 2026-08-25, current
  through 6.8 + MCE 5a + CAS + the horizon finding. Self-contained (no CDN, no charting library; four
  pre-rendered SVG charts), with a Full/Overview detail toggle for presenting and a light/dark/auto
  theme toggle. Keep it in sync when status moves; it is NOT canonical — PHASES.md is.
- **Machine quirk that has bitten three times:** a snap refresh prunes anything
  living under `~/snap/`. It has already destroyed the uv venvs and the pnpm
  store (`pnpm add` still fails with `ERR_PNPM_UNEXPECTED_STORE` — repoint
  `store-dir` outside `~/snap/` and run one full `pnpm install` before adding
  any package). Check where `claude` itself resolves to as well.
- `make check` green is the baseline state — keep it that way. Tests use an
  isolated Redis logical DB (15), flushed per test — never point them at dev
  db 0. Options math + F&O suggestions run behind the `tradecore` wheel: run
  `make engine-build` after pulling engine changes.
- **⛔ NEVER pass `DATABASE_URL` to `pytest`, `make test` or `make check`. On 2026-09-07
  doing exactly that DESTROYED the dev database** — `conftest.py` used
  `os.environ.setdefault`, so the supplied URL was taken as-is and the autouse
  `clean_tables` fixture `TRUNCATE`d every table before each test. **Cost: 138 paper
  positions (the whole cycle-1 book), all signals + outcomes, 1,664 `cas_daily` rows across
  8 sessions (unrecoverable by design — the window cannot be back-filled), orders,
  watchlists, journal, saved screens, holdings.** No PITR, no backup existed. Recovered:
  `stocks` via `seed_stocks.py` (public CSVs, no auth) and 1.63M `ohlcv_1d` bars from the
  bhavcopy archive. **A worktree isolates FILES, not the database.** If a worktree needs
  env vars because it has no `.env`, pass **only `JWT_SECRET_KEY`** — analysis scripts get a
  DB URL, the test suite never does. Two guards now exist: `conftest.py` refuses at import
  time any database not named `*_test`, and **backups run `0 11 * * 1-5`** to
  `/home/nithin/code/back_ups/trading_platform/{dev,test}/` (3 retained, all 52 tables,
  pruning only after a verified dump). `make backup` · `make backup-verify` (a REAL restore
  — TimescaleDB hypertables need `timescaledb_pre_restore()`/`post_restore()`) — details in
  `RUNBOOK.md` §9. **Ask before anything that writes to, truncates or migrates live data.**

- **✅✅ THE UNIVERSE OUTAGE IS REPAIRED (D2′b, 2026-09-14).** User approved +1,121 / −152.
  **Active stocks 1,322 → 2,291; Nifty 50 constituents active 5 → 50.** ⭐ The 152 deactivated
  were **139 `BE`-series** (the 2026-07-17 T2T ruling already excluded them from live scanning)
  **+ 13 junk** — incl. `KNOWNCO`, a **test fixture in the production stock master**, and two
  **indices carried as stock rows**. ⭐⭐ **`is_active` now has ONE writer and a DATABASE TRIGGER
  refuses every other** (`app.universe_writer`, `SET LOCAL` so a pooled connection cannot inherit
  it); `deactivate_dead_stocks.py` is **retired** and **its reversal SQL REMOVED rather than
  preserved** (it joins on raw `stock_id`, all of which were reassigned 09-07 — §20/2).
  ⛔ **A collapse rail was added that §43 did not ask for:** the beat applies nightly from an
  internet CSV, so it refuses a snapshot below 50% of the active set — **exactly what my own
  `EQ=0` header bug would have done.** ⚠ **Membership flags deferred to U9** (they self-heal on
  reseed, which is why `is_active` alone got STUCK; their real defect is point-in-time).

- **✅ THE D3 → U17 → D0 → D1′ → D2′a QUEUE IS DONE (overnight 2026-09-14).** ⭐⭐ **D2′a evaluated the universe as a versioned rule and the first run says: WOULD
  ACTIVATE 1,121 · WOULD DEACTIVATE 152 · resulting universe 2,291** — the 152 all
  `not_eq_listed`, **exactly** round 2's independently-derived "active but not in the EQ list"
  count. ⚠ **SHADOW ONLY — nothing writes `is_active`**; the flip is D2′b and the question is
  now *"do we accept these 1,273 changes"*, not *"is the rule right"*. Check it with
  `uv run python scripts/universe_snapshot.py --diff`.
  ⭐ **D3's real justification was never storage:** `eod_catchup:102` calls the default ingest
  path, so on 09-11 the old code would write **1,166 of 2,637** traded names and drop **1,471
  EVERY DAY** — the same count U3 repaired. **U3's fix was not durable.**
  ⭐ **U17:** subscription = universe **∪ held names** — a held name leaving the active set lost
  its ticks and the monitor skipped it **permanently**, SL/TP unwatched. The trace also talked me
  OUT of unioning the alert hot set (capacity-bounded; a stale row "silently eats a slot").
  ⭐ **D1′:** `symbol_history` + **`COALESCE(stocks.isin, EXCLUDED.isin)`** — an identity anchor is
  filled once, never silently rewritten. ⛔ **`uq_stocks_symbol_exchange` NOT dropped**: 14 queries
  assume one row per symbol, and the reuse hazard's rate is **unmeasurable retrospectively**
  because the merge overwrites its own evidence (4th estimand-trap instance, caught before it was
  banked). ⭐ **D0:** identity pin + a negative-control test planting the 09-07 id swap.
  ⚠ **U16 pressure is LOWER than reported** — 2,291 = 76% of Kite's 3,000 cap, not 2,655/88%.
  ⛔ **Two bugs I wrote and caught by RUNNING, both silent-partials:** the `sync_instruments`
  missing commit, and a CSV parser that returned EMPTY because `EQUITY_L`'s header carries a
  LEADING SPACE on every column after the first (`seed_stocks._csv_rows` already strips keys and
  says so — a documented trap, reintroduced). Both now raise instead of succeeding quietly.

- **⛔⛔ THE LIVE THREAD IS `docs/UNIVERSE_REBUILD_PLAN.md` — the stock master has been WRONG
  since the 2026-09-07 DB loss, and PART VII settles what that means.** ⭐⭐ **Every one of the
  3,392 `stocks` rows has `created_at` = 2026-09-07**, so there was never anything to "restore":
  the whole master was improvised in one night by the emergency recovery. The choice is keep that,
  or replace it with one that was chosen ⇒ **REBUILD-D: derive, don't repair** (§26) — collapse the
  `is_active` repair into the versioned universe rule, so the repair becomes the rule's FIRST
  EVALUATION (no repair script, no forensic table, and no reversal SQL — §20/2 proved the documented
  reversal now reactivates the WRONG companies, every id having been reassigned that night).
  ✅ **DONE 2026-09-13, committed, NOTHING PUSHED: U3** (breadth hole closed, **+7,351 bars**, stale
  names 1,481 → 4; ⭐ `is_active` **1,322 before and after**, so `U1 → U2 → U3` was never a real
  chain and the `load_frames` clock is STOPPED) · **U1** (`kite_instruments` **0 → 57,595**; the dump
  is **PUBLIC**, which is the only reason a beat task can own it — a Kite token dies ~06:00 IST daily;
  plus an `EXIT_NO_UNIVERSE` startup guard) · **D4a** (CA detector ungated from `is_active`) ·
  **U15** (the backfill can repair a THIN session, not just a missing one).
  ⛔ **TWO "SUCCESS LOG OVER WORK THAT DID NOT HAPPEN" BUGS in one day:** `sync_instruments` had
  **never committed** (its one caller was an endpoint whose `get_db` auto-commits, so a Celery caller
  would have discarded 57,595 rows nightly while logging success), and a 200-OK login interstitial
  parsed to zero records and reported success. **Both found by RUNNING, not reading.** bug-hunter
  then found **five more defects in the new code** (§30), incl. a supervisor that restart-looped on
  the new exit code and a baseline that let a **staged collapse walk under the ratio guard**.
  **⇒ NEXT: U16** (chunk the WS subscription — `live_worker` subscribes in ONE call and Kite caps a
  connection at **3,000**; today 1,178 = 39 %, **post-repair 2,655 = 88 %** ⇒ **before D2′**) → **D0 /
  D1′ / D2′**. ⛔ **BLOCKED ON THE USER: D3** (does the T2T ruling govern TRADING or STORAGE — §22/1).
  ⛔ **D4b is not half a day** — a backward CA pass flags **1,768 of 3,395 stocks, 386 of them
  ACTIVE**; rescoped in §32 as a review queue (= the front half of A3).
  ⚠ **The universe rule drops `≥ 300 bars`:** bar count is a fact about OUR OWN data completeness,
  and a rule that reads its own completeness shrinks when ingestion breaks — 09-07 rebuilt inside
  the fix. It becomes a SCORING-TIME check.

- **✅ THE B-QUEUE IS COMPLETE 7/7 (2026-09-12), AND E2 RETURNED A NULL.**
  ⭐ **`docs/BUILD_QUEUE.md` is the operational doc.** B2 cash rail · B3 dated tick schedule ·
  B1 filters deleted · B4 span gap guard · B5 E1 · B6+B7 E2 + excursion surface · B8 ledger.
  ⭐⭐⭐ **E2 ANSWERED (§12.35) against a pre-registration committed BEFORE the code** (`fe5d508`).
  **3a unconditional IC h=5d = −0.0070, 90% [−0.0259, +0.0119] ⇒ NULL** (upper bound below the
  MEASURED break-even 0.0310). **The scorer carries no cross-sectional information; `confidence_pct`
  is flatter still.** ⚠ **3b INCONCLUSIVE, not rounded to null** (−0.3150%, upper bound +0.388% >
  +0.255%) ⇒ ⭐ **THE RANKER IS DEAD, THE GATE IS UNPROVEN BOTH WAYS.**
  ⭐ **Retired: `sd(IC_t)` 0.10 → 0.1126 · `E[z|selected]` 2.268 → 1.8506** ⇒ break-even IC figures
  rise ~23%. ⭐⭐ **B7: MFE/|MAE| 0.83/1.12 (no geometry repair) and the hazard curve is FLAT** ⇒
  **the hold-period breadth lever is RESOLVED AGAINST IT.** T=0 contrast t = −4.16 but it is the
  tight-stop cohort the order path refuses.
  ✅ **LEDGER MIGRATION `e1f2a3b4c5d6` IS APPLIED TO DEV** — measured 2026-09-12 (`alembic_version` = `e1f2a3b4c5d6`, `ledger_entries` present); the earlier "not applied" warning was stale (RUNBOOK §8b).
  ⚠ **QUEUED:** `swing_dependence_probe.py` has **no through-stop exclusion** while the positional
  probe and the live path do — the two corpora never measured the same population.
  ⛔ **NOTHING PUSHED.**

- **⭐⭐ THE B-QUEUE IS 5 OF 7 BUILT (2026-09-11/12), AND E1 IS ANSWERED.**
  ⭐ **`docs/BUILD_QUEUE.md` is the operational doc.** Shipped: **B2** `Σ notional ≤ cash` rail ·
  **B3** tick grid → a DATED schedule (sub-₹250 moved to ₹0.01 in **June 2024**, measured;
  boundary **₹225**, not 250, because ₹225–300 is a MIXED zone — the tick is a property of the
  INSTRUMENT) · **B1** both undeclared display filters DELETED (choppy: **p = 0.999** while hiding
  **67%**) · **B4** gap guard tests SPAN · **B5** E1 run.
  ⭐⭐ **E1 ANSWERED (§12.34): POSITIONAL CLOSES LIKE SWING.** Contrast decays **R −0.4879
  (t −1.89) → raw % −0.7870 (t −1.18) → excess vs matched basket −0.1909 (t −0.29)**.
  ⇒ **§4.4, §12.1, §12.2, the cap sweep and the σ_R objective ALL CLOSE.**
  ⛔ **§12.27's "opposite signs" is WITHDRAWN against itself** — `E[1/w]` jumps **110×** at the
  first bucket (~0.026% stops), net ₹ **−25,808/trade**: a LEVERAGE POINT on a cohort the order
  path refuses. ⭐ `drift × T` confirmed again: mean `T` **6.4 → 32.9** sessions.
  ⚠ **B4 shipped a blind spot its own verification caught** — the observed-session calendar is
  blind to MARKET-WIDE holes (nobody has bars in the gap, so a straddling window reads
  contiguous). Now tests sessions AND calendar days. **`probe-147` → `probe-145`; `clean × BUY`
  is n = 60** (§16.1d). ⛔ **NEXT: B6+B7** — write the estimands, h=5d and the decision tree down
  BEFORE any code.

- **⭐⭐⭐ ROUND 10 (2026-09-11) — A PREDICTION HIT TO FOUR DECIMALS, AND DIED THE SAME SESSION.**
  ⭐⭐ **THE OPERATIONAL DOCUMENT IS NOW `docs/BUILD_QUEUE.md`** — B1–B8 with `WHY · SCOPE · FILES ·
  ACCEPTANCE · ARTIFACT · DO NOT` per item, the parked register, and five probe conventions. **The
  adjudication (5,900+ lines) is the forensic record you CITE, not the file you READ to decide.**
  New §12.33 (measurements) · §13.12 (process) · §18.6 (ledger) · `docs/analysis/round10-cells-2026-09-11.md`.
  ⭐⭐ **PREDICTED −0.74%, SE 0.31, t −2.4 from our published rows alone. MEASURED −0.7413%, SE 0.2914,
  t −2.54, p 0.011** (clustered −2.06), **surviving the gap filter** (clean −0.8556, t −2.59). The BUY
  book's matched basket returns **−0.166%** over its own holding windows; the SELL book's **+0.575%**.
  ⇒ ⭐ **88% OF THE BUY BOOK'S GROSS LOSS IS TAPE, NOT ALPHA** (raw −0.1877% = tape −0.1659% + alpha
  −0.0218%); **SELL rides a +0.58% tape and gives back −1.01% in alpha.**
  ⭐⭐ **THE INSTRUMENT WAS TESTED AGAINST ITS OWN PREFERRED CONCLUSION AND PASSED:** on the full book
  **`mean(bench) = drift × mean(T)` to ratio 1.00** (Wald — `T` is a stopping time) **and the deviation
  is ENTIRELY directional, which an exit artifact cannot produce** ⇒ ✅ §12.31c's α confirmed.
  ⛔⛔ **THEN IT DIED — NO OBSERVABLE ANTECEDENT.** BUY vs SELL **trailing** basket at entry:
  **t = +0.50 / −0.88 / +0.29** at 5/10/20 sessions. The −0.74% exists **only FORWARD**; the one
  bridging mechanism (basket mean reversion, t −2.14) explains **3%** of it. ⇒ ⭐ **RECORDED, NOT ACTED
  ON** at t −2.06 clustered vs our t ≈ 3.6 bar — the RVOL verdict, same reason.
  ⭐ **PARKED ITEM RETIRED FREE: the market-regime overlay was NEVER gated on `index_ohlcv_1d`** — the
  equal-weight basket is the better proxy and conditioning BUY alpha on pre-entry tape **does not
  separate** (best cell t = +1.66). ⚠ "No evidence for", not "evidence against" (n=82 split two ways).
  ⭐ **PROCESS — 3 adopted, 1 FORBIDDEN.** ✅ `BUILD_QUEUE.md` · ✅ **entry rule: converged across sources
  OR settled by our own measurement — NEVER consensus alone** (unanimity has been wrong repeatedly; the
  best items each came from ONE source) · ✅ **B2 FIRST** (only item where money is at stake), **B7
  retires a parked row**, **B8 timeboxed to ONE table in ONE day**. ⛔ **REJECTED: "deactivate the dead
  factors" is a SPEC CHANGE to a FROZEN, hook-protected engine.**
  ⭐ **Zero new scoring walks — everything came off round 9's `--dump-trades` artifact.**

- **⭐⭐⭐ ROUND 9 (2026-09-11) — E3 WAS RUN, THE PAIRED NULL REFUTED OUR OWN α, AND THE PANEL IS CLOSED.**
  Five responses to §17b's invitation (*run E1/E2/E3 or refute a §16.1 row*). ⭐ **The first round that
  shipped code with itself:** `swing_dependence_probe.py` gained the holding period `T`, a **paired**
  matched-window basket return, entry-day Kaufman ER and a confidence-normalizer decomposition, plus
  `--dump-trades`; `scripts/round9_cells.py` reads the artifact. **`probe-185` reproduced to 4 dp.**
  New §12.24–§12.31 · §13.9 (plan) · §13i (ledger) · **§16.1c (card, supersedes §16.1b)** · §17c.
  ⛔⛔ **THE BIGGEST CORRECTION IS OURS: §12.20a's "the correct null roughly DOUBLES the deficit"
  (α = −0.137…−0.172R) IS WITHDRAWN.** It multiplied a drift from **789 post-gap sessions** by an
  **assumed** 5-session horizon and subtracted it from trades in *different* sessions whose measured
  **mean hold is 3.59** (median 5; **14.6% same-session exits**). **Paired over each trade's own window
  the basket is NEGATIVE on the tradeable book** (−0.166% BUY, −0.338% E3). ⇒ ⭐⭐ **GROSS ALPHA ON THE
  TRADEABLE BOOK IS ZERO: paired excess −0.0218%, t = −0.07 (n=82)** — the ALL book's basket is +0.247%
  and BUY's is −0.166%, so **SELL signals fire into rising tape and BUY signals into falling tape; the
  gross loss is WHEN it trades plus cost, not what it picks.** ⚠ t = −0.07 is absence of evidence for
  any α, not evidence of zero (MDE ≈ ±0.93%/trade).
  ⭐⭐ **E3 RUN — `clean × BUY × w≥2%`, n=49:** gross **−0.1212R (t −1.26)** · **NET −0.1772R (t −1.84)**
  explicit · **−0.2432R (t −2.52)** @15bps/leg · −0.3092R (t −3.19) @30bps. **Date-clustering moves every
  t by ≤0.06** (RVOL collapsed under clustering because it is a per-DATE regressor; a per-trade mean is
  not). ⛔ **§16.1b's `t = −2.19` is WITHDRAWN as the WRONG COHORT's number** (it includes sub-2% stops
  the order path refuses) — the verdict re-derives at −1.84. ⚠ **Both published predictions were too
  optimistic because both held σ at 1.0050; the reachable cell's σ is 0.6712**, and `E[cost in R]` there
  is **+0.0561R** (confirming 0.0573R to 2%).
  ⭐⭐ **THE STOP-WIDTH FAMILY, CLOSED A THIRD TIME BY A MECHANISM §12.18f MISSED:** `R = (α + drift·T)/w`
  with **`d(T)/dw = +0.384, t = +6.69`**. The contrast decays and **flips sign** — **R −0.386 (t −1.55)
  → raw % −0.262 (t −0.78) → excess vs matched basket +0.069 (t +0.17)**. ⛔ **"Independence is MEASURED"
  is WITHDRAWN — t = +1.07 is a NON-REJECTION**, ~25% of it drift×T. **Raw % was never enough; only
  pairing is.**
  ⭐⭐ **THE HEADLINE, needing no t-statistic: per rupee-day deployed the tradeable book underperforms
  simply HOLDING the universe it selects from by 19–56 pp/yr (30–63 on the reachable cell) net of
  explicit charges**, 39–90 at 15 bps/leg. ⚠ **Range = the aggregation choice (mean-of-ratios vs
  ratio-of-means), NOT uncertainty; the sign is invariant.**
  ⛔ **TWO HYPOTHESES REFUTED, both making closure CLEANER:** (a) **the confidence normalizer** —
  `confluence.py:160` divides by the weight of *scoring* factors so sparse conviction outranks broad
  agreement (**confirmed in code**), **but all four rival ranking keys are ρ ≈ 0, every p > 0.46** ⇒ the
  negative covers the **factor set**, not one summary; (b) **the undeclared `choppy` filter** hides
  **67%** of the offered set and separates **nothing** (−0.0001, **p = 0.999**) ⇒ **delete it and
  `_near_expiry` with it.**
  ⭐ **CONVERGENCE: three sources, three routes, one defect in E2** — the specified full-cross-sectional
  IC is not the deployed question and the gate-conditional version is a **collider** on the score's own
  output ⇒ **E2 = THREE estimands** (3a unconditional · 3b matched-tail · the collider, reported never
  decided on), `sd(IC_t)` and `E[z|selected]` as **OUTPUTS**, coverage-weighted (cross-section runs
  46→250 and 1/√46 = 0.147 exceeds the whole break-even band).
  ⭐ **NEW MECHANICAL RULE — the sample-tag rule in TIME: ⛔ a benchmark measured over one set of
  sessions may not be subtracted from a return measured over a different set. Pair it, or do not
  subtract it.** Eighth instance of the family, first in time rather than population.
  ⭐⭐ **THE FACTOR INVENTORY, READ FROM THE FROZEN SCORER (§12.32): 26 registry entries, not 15** (the
  pattern detectors are separate; only one is selected per panel). **325 declared weight; the mean that
  SCORES per panel is 30.6 = 9.4%.** ⛔ **THREE factors never score on 487 panels — `DOW_TREND`
  (weight 20, the HEAVIEST), `MARUBOZU`, `FII_DII_FLOW`** (dead: `fii_dii_daily` = 4 rows). ⭐ **That
  last one REMOVES A BLOCKER two reviewers built packages around — the only non-price term is already
  inert, so E2 can test the SHIPPED scorer, not a "price-only variant."** Four factors carry nearly
  every scoring event (**PRICE_VS_EMA 70% · ADX 46% · MACD_HISTOGRAM 43% · RSI_LEVEL 36%**), two of the
  top three EMA-derived ⇒ **effective dimensionality ~2–3.**
  ⭐ **THE DOC NOW CARRIES: §13.10 the build queue WITH ACCEPTANCE CRITERIA · §13.11 what is parked
  and WHY (each row BLOCKED / UNCONVERGED / SEQUENCED) · PART VI §18.1–§18.5 every panel question
  answered per source.**
  ⛔ **PANEL CLOSED AT ROUND 9 (§17c).** What remains is **B1–B8** (§13.10): delete the two undeclared
  filters · `Σ notional ≤ cash` rail · the tick SCHEDULE table · span-based gap guard · E1 positional in
  four units · E2's three estimands + MFE/MAE · the ledger. **User ruling: build the AGREED half first,
  discuss the rest after.**

- **⭐⭐ ROUND 8 (2026-09-11) — AN EXTERNAL AUDIT RECOMPUTED ROUND 7 AND WITHDREW FIVE OF MY CLAIMS.**
  Three responses; one (`~/Downloads/round8-external-audit-2026-09-11.md`) is the **first review in
  eight rounds to arrive as a reproducible RECOMPUTATION** — **11 of 13 claims reproduce exactly.**
  New §12.18–§12.23 · §13.8 (the plan) · §13h (ledger) · §16.1b (card corrections) · §17b.
  ⛔⛔ **BOTH ROUND-7 "INVERSIONS" WERE DECOMPOSITIONS, NOT FINDINGS** — I read the *level* in each half
  and never computed the **contrast**: BUY-vs-SELL `+0.0893, SE 0.1325, t = +0.67, p = 0.50`;
  clean-vs-straddling `+0.0718, SE 0.1420, t = +0.51`. **Neither separates**, and **0.33 of the 0.52
  t-drop is POWER, only 0.20 the mean.** ⭐ What survives is **structural, not statistical**: cash
  delivery cannot hold an overnight short ⇒ 55.7% untradeable by construction — **the reason for
  preferring the BUY cell was never statistical.** ⭐ **Family name for the error: a quantity computed
  on a subgroup is not evidence about the subgroup until it is compared with its complement.**
  ⛔ Also withdrawn: **the σ_R ladder is NOISE** (0.62 SE; t 0.82 two-sample) · **"the evidence base is
  EMPTY, not negative"** ⇒ **P(positive net edge) = 0.4–5.7%** across priors 0.03R→0.20R = **economic
  closure without statistical closure** · **every "MDE" was 1.40× too small** (`2·SE` = 50% power; the
  honest cell is **+0.417R**) · ⛔⛔ **RVOL's t = +3.67 was an IID-SE ARTIFACT — HC3 +0.61,
  date-clustered +0.98** (SE inflates 6×; 185 trades on 92 dates, RVOL is market-wide daily).
  **"Most robust coefficient in the document" withdrawn: the unit was never the only problem, the SE was.**
  ⭐⭐ **THE ONE PLACE IT GOT SHARPER: costed PER TRADE, the tradeable book is SIGNIFICANTLY NEGATIVE.**
  `cost_in_R = bps/(100·w)` ⇒ Jensen. Measured **E[cost] 0.1522R vs the 0.0549R scalar = 2.77×
  understatement** on the corpus (scalar is **right** for the reachable w≥2% book, 0.0573R).
  **BUY-only net −0.2435R at t = −2.19** (explicit only), **−0.4134R at t = −3.31** with slippage.
  ⇒ **the GROSS question is underpowered; the NET question is ANSWERED.**
  ⛔⛔ **THE STOP-WIDTH/DENOMINATOR FAMILY IS CLOSED ON SWING:** the pure `1/w` term with return
  **independent** of `w` reproduces **116%** of the measured spread (−0.4470 vs −0.3864); independence
  is measured (`ret ~ w` t +1.07); the contrast was never significant (t −1.55). ⇒ **§4.4, §12.1 and
  §12.2 are ONE artifact of dividing by a small number.** Positional untested = plan item **E1**.
  ⭐ **THREE FINDINGS IN NO REVIEW, all from verifying it.** (a) ⭐⭐ **the equity-beta NULL is
  computable from `ohlcv_1d` alone** and I had just declared it blocked on `index_ohlcv_1d`:
  equal-weight eligible basket = **789 sessions, +0.0816%/day, t +2.06, +22.8%/yr** ⇒ 5-session null
  **+0.088R** ⇒ **α = −0.137…−0.172R, roughly DOUBLE the raw deficit.** (b) ⭐⭐ **MONEY-PATH BUG:
  `paper_tick_size` is ONE constant (₹0.05) and the market has TWO grids** — NSE moved sub-₹250 to
  ₹0.01; on-₹0.05 for those names **0.98 (2019) → 0.49 (2024) → 0.22 (2025)**, nothing above ₹250
  changed. `_round_tick` rounds adversely to ₹0.05 regardless ⇒ **a ₹39 name overcharged ~10 bps round
  trip = 0.064R at a 2% stop**, on exactly the cohort the remaining results rest on. **Changes a
  recorded number ⇒ BEFORE cycle 2; published exchange schedule ⇒ no DSR bar; read it from a TABLE
  (the phase-in is staged), not a constant.** (c) **my gap guard tests two hardcoded endpoints, not the
  SPAN** — a **second, per-NAME hole** exists (790 post-gap sessions; median 620 bars/name, **p10 67**;
  2,048/3,129 names <95% coverage) and the guard **misses 1.2% of panels**, worst **516 sessions in a
  300-row window**. Fix = span vs the market's session calendar (**W5: the calendar owns it**).
  ⭐⭐ **AND THE ANSWER TO THE ORIGINAL QUESTION, from the code.** `signals.py:267-289`: dedup on
  confidence → **two UNDECLARED filters** (`_near_expiry`; `_choppy` at ER<0.30) **both defaulting ON,
  neither in `restrictions.py`, neither on the order path** → **sort DESCENDING by `confidence_pct`** →
  human picks the top. ⇒ **the deployed picker's ranking key is `confidence_pct`, measured at Spearman
  ρ = −0.018 (perm p 0.807) on a test powered to 0.147.** *"Sometimes I cannot select the right
  stock"* — **the quantity the UI sorts by carries no measured information.** ⚠ Second display/order
  divergence, opposite direction to the 2026-09-02 one (that was too permissive; this is too
  restrictive) ⇒ **`restrictions.py` is NOT currently the single source of truth its docstring claims.**
  ⭐ **Two structural reads:** **ρ̄ is FLAT in m** (one-factor identity — refutes my Q7-2) and **HOLD
  PERIOD is the bigger breadth lever** — 9 slots × 3-day holds = **298** effective obs/yr vs **109**
  ⇒ **the 2021–23 back-fill is DROPPED, the lever is TURNOVER**; and **§4.5 used `IR ≈ IC√BR` (a
  portfolio law) for a gated TAIL selector** — correctly transferred, **IC 0.02 ≈ break-even/trade,
  IC 0.04 comfortably positive** ⇒ §4.5's "not investable" is a **turnover** diagnosis. ⚠ At the honest
  σ, **decade-scale validation is BACK** (1,198 trades ≈ **9.6 yr**).
  **⇒ THE PLAN IS THREE MEASUREMENTS + ONE BUILD (§13.8): E2** the panel-level score IC at **h=5d**
  (⭐ the only fully-powered test of the only question that changes direction; **pre-register 5d** — 20d
  can only say INCONCLUSIVE; **report `sd(IC_t)` as an OUTPUT**, it is `[ASSUMED]` at 0.10 and every
  power figure is linear in it) · **E1** positional family in raw %/ATR/net ₹ with the gap flag ·
  **E3** the one cell the programme turns on in ONE pass (`clean × BUY × w≥2% × net-per-trade` + the
  mean hold) · **BUILD: the append-only ledger** (not for this strategy — for any successor).
  ⛔ **DROPPED: the back-fill · the level-stage lever · the cap sweep · the index-backfill gate ·
  ROUND 9** (4 of 37 round-7 and 3 of 29 round-8 points changed a decision; **a round only happens if
  a probe runs with it**).
- **⭐⭐ ROUND 7 OF THE QUANT PANEL (2026-09-11) — THE HEADLINE INVERTS, AND `ohlcv_1d` HAS A
  922-DAY HOLE.** Four reviews adjudicated point by point in
  `docs/analysis/quant-panel-adjudication-2026-09-10.md` (§12.12–§12.17 · §13.7 · §13f · §14b ·
  §15.7 · rebuilt §16.1 · **§17 = four questions back to the panel**); probe extended read-only in
  `backend/scripts/swing_dependence_probe.py`. **37 points: 21 taken · 8 refined · 8 rejected on
  evidence.** Nothing built on the money path.
  ⭐⭐ **Round 6's "significantly negative gross edge, t = −2.31" is carried by the UNTRADEABLE half:
  BUY-only n=82, −0.0992R, t = −0.94** (SELL n=103, −0.1885R, t = −2.36; a cash-delivery account
  cannot hold an overnight short). ⇒ **the tradeable book is NOT distinguishable from zero, negative
  in expectation.** All four reviewers led with this and it had been an unrun plan item since round 1.
  ⛔⛔ **`ohlcv_1d` HAS A 922-DAY HOLE, 2020-12-23 → 2023-07-03 — 1,097 sessions, not the ~1,730 a
  2019-10 → 2026-09 span implies, and 33.2% of round 6's 16,428 panels were scored on a 300-bar
  window straddling it** (EMA200/ATR/ADX/pivots across a 2.5-year discontinuity). It explains
  `_CLEAN_SINCE = 2023-07-03` — **not a CA-clean choice, just the first date of the contiguous modern
  block** — and it **KILLS the un-truncation plan item**: real yield n ≈ 2,662 (bar-50 walk) or
  **exactly 0** (300-bar walk), not 4,300. The blocker was never the CA source but **615 missing
  sessions** (bhavcopy back-fill). On gap-clean windows the headline falls to t = −1.79. ⭐ **Standing
  rule: a span is not a span until the session count is QUERIED** — three docs and six rounds asserted
  "~7 years" from `min(time)`/`max(time)`, two numbers that say nothing about what lies between them.
  ⭐ **Three round-6 conclusions corrected:** (1) **ρ̄ ≈ 0 was a DIRECTIONAL-CANCELLATION artifact** —
  long-only inflation is **1.19–1.23×** (ρ̄ ≈ **+0.19**), so ₹3L buys ×1.63 effective observations, not
  ×3.26 and not +20%; **Kimi's stress case was the real case.** (2) **§12.10a's "detects an edge below
  friction, with room to spare" is WITHDRAWN** — long-only MDE **+0.0714R > 0.051R** explicit charges;
  a Sharpe-1.0 edge is still detectable at ×2.87 but the margin is **1.3×, not 4×**. (3) **Δ_select as
  a continuous rank statistic: ρ = −0.018, perm p 0.807, powered to detect 0.147** — same answer, now
  properly powered (the decile contrast had MDE +0.31R).
  ⭐⭐ **Two structural repairs.** **KILL LINE 3 → 3a (strategy closure) / 3b (feature-family closure)**:
  ChatGPT, Claude and Kimi converged from three directions that **a line keyed to total strategy R
  cannot kill the SCORER** when the classifier, the level stage (−60.8%), geometry, horizon and fill
  model sit between. And ⛔ **`Σ notional ≤ available cash` DOES NOT EXIST IN THE CODE** — three slots
  at the median 5% stop need **120% of capital**, unchecked (the per-position cap binds only below a
  2% stop). **First new RAIL in 25 reviews, identity-enforcing so no DSR bar, and a PRECONDITION for
  cycle 2.**
  ⭐ **The best new finding, and the only breadth lever left: the level stage discards 289 of 475
  gate-passing swing panels and has NEVER been evaluated as a selector.** Re-simulated with fallback
  stops on identical panels, **the discarded cohort beats the kept cohort by +0.16R** (paired by entry
  date, t **+1.43** flat-5% / **+1.54** 2×ATR20, rejects carrying wider stops). ⚠ **Not significant —
  MDE +0.22R**, but **+288 trades available today with no data blocker** and it is 3b's first test.
  ⭐ **Gemini's one control variable outperformed every other point:** its ATR-proxy hypothesis was
  **refuted** (ATR% t −0.43), **one of OUR findings was partially refuted** (the stop-width gradient is
  t +2.30 in R, **+1.07 in raw %**, +1.06 long-only ⇒ **the 2026-08-25 stop-width result is
  substantially a DENOMINATOR EFFECT**), and it surfaced **`RVOL-20` at t = +3.67, the only coefficient
  in seven rounds to clear the t ≈ 3.6 bar.** ⛔ **Then round 6's own rule disqualified it — in raw
  return % it is t = −0.28, and D1 refuted RVOL as a generator at t = −2.91. RECORDED, NOT PROMOTED.**
  ⭐ §12.10b ("keep R for sizing, test in bps and ATR") has now disqualified **two of our three best
  results**, which makes it the most productive finding of the whole exercise.
  ⭐⭐ **AND THE HONEST CELL (R7-K), WHICH CORRECTED THREE OF THE ABOVE.** Gap guard × direction split
  = **clean windows × long only: `n = 61, −0.0843R, t = −0.66, σ_R 1.0050, MDE +0.29R` —
  UNINFORMATIVE.** ⇒ the evidence base for the book we can actually trade is **EMPTY, not negative**,
  and KILL LINE 3 cannot fire on this sample either way. ⭐ **σ_R rises MONOTONICALLY as the
  population is restricted: 0.878 → 0.911 → 0.957 → 1.005** (halfway back to the corpus's 1.489);
  inflation with it, 1.00× → **1.24–1.43×** (ρ̄ ≈ +0.26).
  ⛔ **(1) CLAUDE'S FINDING D DOES NOT SURVIVE** — paired contrast **+0.16R (t 1.43) → +0.095R
  (t 0.69)**, and it **REVERSES on the clean tradeable book** (rejects BUY −0.118R vs accepts
  −0.084R): gap contamination + a shorts effect. ⭐ **Structural credit stands — the largest filter in
  the pipeline is measured and "not anti-selective" CLOSES a suspect** — but it is not a lever
  (downgraded to a +223-trade sample-enlarger). ⛔ **(2) The Kelly INTERVAL claim is WITHDRAWN** —
  clean BUY CI **[−0.844, +0.016] includes zero**; ✅ `f* = 0.0000` exactly survives everywhere and
  **Claude's prediction was right.** ⛔ **(3) The stop-width gradient COLLAPSES AND FLIPS** — t +2.30
  → **+1.06** clean → **NEGATIVE on clean × BUY** ⇒ **the 2026-08-25 stop-width finding survives
  NEITHER the unit change NOR the gap filter**, and `sl_atr`'s "reproduction at exactly 1.0×"
  inherits the defect (already DECIDED: NO at t 0.41, so nothing downstream moves).
  ⭐ **STRONGER: `RVOL-20` is robust to the gap filter** (t +3.65 clean, +3.13 clean × BUY) **and
  still t −0.36 in raw %** ⇒ **only the UNIT kills it.**
  ⛔⛔ **PROCESS LESSON: I published four measurements before running the `--clean-only` variant of
  the guard I had just built in the same round, and it corrected three of them.** ⭐ **STANDING RULE:
  a guard is not adopted until every number in the same document has been re-run through it.**
  ⚠ **GOVERNANCE: §16.1 carries a `sample` and a `verified` column per row, with one mechanical rule —
  NO FORMULA MAY COMBINE TWO QUANTITIES WHOSE SAMPLE TAGS DIFFER.** Five instances so far; Claude found
  the fifth (σ from `probe-185` × n from `corpus-1975`) and **Kimi committed it in the same round while
  diagnosing a different one** (its "t ≈ −3.3" is the published −1.94 with a foreign σ). ⛔ **And I
  drafted one regression table from expectation before its run finished — deleted before it entered the
  doc, recorded permanently in §13f.**
  ⛔ **Shipped since 2026-09-10: four commits, all docs. ONE of nine cut items has shipped as code.
  50 days to the 2026-10-31 sunset.** ⇒ **ship, do not review** — §13f measures the marginal value of
  review breadth as negative (4 of 37 points changed a decision; 5 were refuted by a query the reviewer
  could have asked for).
- **⭐ EXTERNAL QUANT PANEL ADJUDICATED 2026-09-10 —
  `docs/analysis/quant-panel-adjudication-2026-09-10.md`.** Ten external reviews (5 each on
  `SYSTEM_REVIEW_FOR_QUANT.md` and `POSITIONAL_REVIEW_FOR_QUANT.md`) checked claim-by-claim
  against the code and the DB. Sixteen mechanism claims **CONFIRMED** (denominator, volume
  sign-forcing, three-way level divergence, no positional stop cap, zero-cost/no-horizon
  backtest, notional cap = 2% min-stop-width, symmetric entry zone, `_has_active_signal`
  latch). Six **REFUTED** — most importantly the panel's most unanimous claim, *"you have
  never computed factor-level IC"*: `scripts/factor_sweep.py` ran it 2026-09-07 on 212,129
  observations / 156 non-overlapping dates with day-block bootstrap **and trial-count
  deflation**, and nothing survived — including the exact SMA/52w feature family a
  cross-sectional ranker would use, which is a strong measured prior **against** the panel's
  other unanimous recommendation. The real gap is narrower: the sweep never pointed at our
  own 15 factors or the composite score. **FIVE genuinely new findings, three of which change
  the plan:** (1) ⭐ **cycle 2 cannot test expectancy** — σ_R = 1.489, so at n ≈ 25 trades the
  DSR bar demands **+1.12R/trade** and even a plain t=2 demands +0.60R, against **+0.094R**
  from a Sharpe-1.0 system ⇒ **re-scope cycle 2 as an operational-correctness rehearsal, not
  an edge gate**; (2) ⭐ **the null was never written down** — E[R]=0 for ANY barrier config
  under a martingale, so −0.065R is *worse than a coin flip*, and the correct null for a
  100%-long beta-0.92 book in a rising market is strongly POSITIVE ⇒ we have **negative
  alpha**, not zero alpha; (3) ⭐ **57% of generator output is untradeable** (108 SELL / 81 BUY
  on a cash-delivery book that cannot hold an overnight short — the backtest simulates both
  sides, so the 1,975-trade headline blends a tradeable long book with an untradeable short
  one); (4) the **8% swing stop cap is anti-correlated with P&L** on three independent lines
  and kills 51.9% of gate-passing signals — worth ~0.13R of the 0.215R gap, on no tier of our
  plan; (5) **breadth** (`IR ≈ IC × √breadth`) is the dimension the architecture never
  considered — at ~60 trades/yr a *perfect* version of this system is not investable.
  ⭐ **The tension nobody named, and the real strategic problem: at ₹1 lakh, cost economics
  pushes toward CONCENTRATION (flat ₹15.34 DP ⇒ bps falls with size) while statistical
  validation pushes toward BREADTH — you cannot have both, so single-name delivery swing
  trading at this capital is not a validatable strategy class regardless of whether it has
  edge.** ✅ **The panel's sharpest attack on our own numbers was TESTED AND REFUTED** — the
  positional stop-width gradient is NOT a winsorizer artifact (only **3 of 119** trades
  clipped; raw mean −0.222 vs winsorized −0.251; sign, ordering and conclusion all stand).
  Two unexpected results from that same re-run: the **accidental flat-5% stop BEATS the live
  EMA20 stop** on 387 paired panels (+0.091R vs −0.016R, ΔR −0.116, t −1.41), and applying the
  8% cap to positional panels would reject **54.4%**. Two zero-cost governance edits proposed:
  split `FROZEN-BEHAVIOUR` from `FROZEN-CONTRACT` (we are paying promotion-bar prices for bug
  fixes), and make the burden of proof asymmetric (**the t≈3.6 bar applies to ADDING
  behaviour; REMOVING unjustified behaviour needs only the absence of evidence for keeping
  it**). ⛔ **What all ten reviewers missed: the evidence base they reason from no longer
  exists** — `positions` = 0 rows, so every live-tape number in both review documents is
  currently unreproducible and the forward-evidence loops still listed as open in PHASES are
  dead. Highest-priority engineering item is on nobody's tier list: an **append-only trade
  ledger with off-box nightly export**.

## Tech stack (locked in — ask before substituting)

| Layer | Choice |
|---|---|
| Backend | Python 3.12 · FastAPI (async) · SQLAlchemy 2 async + asyncpg · Celery + Redis |
| Compute core (v2, from Phase 1) | Rust workspace `engine/` — engine-core + PyO3 wheel `tradecore` + engine-cli |
| Database | PostgreSQL 16 + TimescaleDB (port **5433** locally) · Redis 7 (volatile-lru) |
| Frontend | React 19 · TypeScript 6 · Vite 8 · Tailwind 4 tokens · Zustand + TanStack Query |
| Charts | TradingView Lightweight Charts (candles) · Recharts (dashboards) |
| Auth | JWT — access 45 min in memory · refresh 7 d httpOnly · rotation |
| Broker | Zerodha Kite Connect (token expires ~6 AM IST daily) |
| Testing | pytest (real Postgres+Redis, no mocks) · Vitest + RTL · cargo test (Phase 1+) |
| Tooling | uv · ruff · mypy (strict) · eslint · maturin (Phase 1+) |

## Hard constraints (non-negotiable — full detail in `.claude/rules/trading-domain.md`)

1. `docs/SIGNAL_ENGINE.md` is the user's edge — **protected by hook**; spec
   changes only by explicit user instruction + backtest regression (§8).
2. Signals come from the weighted confluence engine only — never a single
   indicator. ≥70% gate.
3. No look-ahead: compute on candle N, valid from N+1; committed signals
   only from `is_complete` candles; the tick-level layer is labelled
   provisional and never enters backtests.
4. Position sizing on every signal; risk_pct is a WHOLE percent (2.0 = 2%).
   Reject (never clamp) signals whose natural SL exceeds the class cap.
5. Money = Decimal / Numeric(12,4) / i64·1e-4. Storage UTC, market logic
   IST. Trading-day arithmetic needs the NSE calendar.
6. Paper trading default; live requires opt-in + 30 profitable paper days.
   **⚠ TWO CYCLES (user ruling 2026-09-02 — `docs/phases/phase-07-live-trading-plan.md`):
   cycle 1 is the WIDE SAMPLER running now and its clock is INFORMATIONAL** (a ~25-position
   book at 45.3% of the live capital figure is not the book that will be traded; live =
   ₹1 lakh, 1–2 positions, and the two can give OPPOSITE signs from the same signals).
   **The BINDING 30-day gate is cycle 2** — reset the clock after CAS Stage 2, MCE 5b + 6,
   the tuning/promotions, the deflated-Sharpe bar and Phase 7.1–7.4, then run 45–50 trading
   days on a heat-capped ₹1 lakh book. Live is realistically 4–6 months out. The daily-loss
   circuit breaker is never disableable.
7. Every feature ships with tests (`.claude/rules/testing.md`); every
   feature follows the vertical slice (`/vertical-slice` skill).
8. **NEVER flip a gate/knob on an argument — check the accruing data first.**
   User rule 2026-09-03, after two reversals in two days: the **regime gate** was
   promoted on 44 observations and refuted by 88 (−8R), and the **R:R≥1 gate** was
   promoted on an "identity, no evidence needed" argument and refuted within a week
   (it blocked the book's only profitable cohort: +₹10,585/63% win). In both cases the
   arithmetic was fine and the *premise* was an unchecked assertion.
   - Before any shadow→active flip: read the sidecar, check the bar's COUNT, check the
     sign survives **trimming the tail**, and check the partition isn't a proxy for
     something else (market-regime turned out to be a proxy for *side*).
   - **An identity about arithmetic still rests on an empirical premise. Test the
     premise.**
   - **Claude owns the calendar.** It is Claude's responsibility to remember each
     item's review trigger and to RAISE it unprompted when the day/count arrives —
     see the REVIEW CALENDAR in the `docs/PHASES.md` CONTINUE HERE block. Do not wait
     to be asked.

## Working rules (W1–W5 — each earned by an incident here, not borrowed)

1. **Doc/code precedence: the executable content wins, and you fix the doc in the same
   change.** This is a precedence *rule*, not the value "conflicts are bad" — it tells you
   what to DO on finding one. A doc that disagrees with the code has already cost real
   time twice: a stale status block claimed 974 tests and "Phase 3 in progress" weeks after
   the truth moved, and `market_regime.py` called our VIX history "too shallow (~weeks)"
   when it held **784 sessions**, which is exactly why its threshold went unexamined for
   months. Finding a conflict is not a discovery to report, it is a doc edit to make now.
2. **Do not add a parallel implementation.** Extend the one that exists, or migrate every
   caller in the same change. The rule with the most evidence behind it here: a review
   round found **five separate Buy surfaces** (AlertBell · OpportunitiesTable ·
   DashboardPage · LiveSignalsPage · StylePage), one of them unwired, and eligibility
   gating had to be retrofitted across all five. Same shape as the gate vocabulary declared
   **nine times** and tied together nowhere (T7). Grep for the existing one first; if you
   are about to write a second, that is the signal to unify instead.
3. **A new config item updates `.env.example` and its docs in the same commit.** The narrow,
   checkable instance of the doc-sync ritual. Config drift is what bit us when a `.env`
   gate flip did not reach a running process — `settings` is an `@lru_cache` singleton, so
   verify a flip in the live process, not just the file.
4. **The git boundary: commit freely on the working branch, never push.** Push, merge and
   force-push are the user's. Branch creation needs explicit approval, including worktree
   branches. Stated rather than inferred, because "reserve push only" is a deliberate
   choice and a future session should not have to reconstruct it.
   **⛔ HARD RULE (user, 2026-09-07): NEVER work in a git worktree — check the branch out in
   the MAIN checkout (`/home/nithin/code/agent/Claude/trading-platform`) and work there.**
   Worktrees have caused an error every time: they have no `.env` (so scripts need a DB URL
   passed inline, which is exactly how the dev DB was destroyed 2026-09-07), and they can't
   merge into a branch already checked out in main. If a branch is held by a worktree, commit
   any WIP first, `git worktree remove` it, then `git checkout` in main.
5. **No hardcoded copy of a value that has an owner** — model names, secrets, paths, ports,
   and *gate modes*. The non-obvious clause is the last one: `STATUS.html` hardcodes gate
   modes in prose, two tables, an ASCII diagram and the KPI tiles, with no data source, so
   a mode flip silently falsifies it. It has bitten twice. If a value has an authority,
   read it from there or accept that every copy must be updated by hand on every change —
   and say so where the copy lives.

## The Claude Code workbench (use it)

- **Hooks** (`.claude/settings.json` + `.claude/hooks/`): auto-format on
  edit; destructive-command guard; protected files (SIGNAL_ENGINE.md,
  applied migrations, .env). If a hook blocks you, it's working — don't
  fight it, tell the user.
- **Agents** (`.claude/agents/`): `quant-verifier` (any analysis/signal/
  backtest/engine change), `bug-hunter` (pipeline/async/broker changes),
  `ui-reviewer` (frontend), `perf-auditor` (hot paths), `test-guardian`
  (coverage honesty). Run the relevant ones before calling work done.
- **Rules** (`.claude/rules/`): trading-domain · python · typescript ·
  rust · testing · ui. Load the ones matching the files you touch.
- **Skills**: `/vertical-slice` (feature workflow) · `/phase-gate` (phase
  exit ritual) · `/signal-audit` (verify a signal/profile against spec) ·
  `/perf-bench` (benchmarks + PERFORMANCE.md protocol).

## Where things live

```
backend/app/      analysis/ (confluence engine, frozen at Phase 1 parity)
                  signals/ · backtest/ · broker/ (kite, tick consumer,
                  paper broker) · trading/ (circuit breaker, trail SL)
                  services/ (incl. F&O recorders) · tasks/ (Celery)
                  api/v1/ · models/ · schemas/ · core/ · db/
backend/tests/    pytest — factories in helpers.py, fixtures in conftest.py
frontend/src/     features/<area>/ pages · components/{ui,layout,charts}
                  lib/api/ (typed client) · lib/format.ts (ALL numbers)
                  store/ (zustand) · styles/tokens.css (5 themes)
engine/           Rust workspace (arrives Phase 1)
docs/             UPGRADE_PLAN (the why) · PHASES (status) · phases/
                  (per-phase reports) · SIGNAL_ENGINE (protected spec) ·
                  UI_GUIDELINES · ARCHITECTURE · PERFORMANCE · DATABASE_SCHEMA
```

## Commands

```
make up / down          postgres+redis (pg on 5433)
make backend            uvicorn dev server      make frontend   vite dev
make worker             celery worker+beat — REQUIRED for EOD ingestion +
                        nightly signals; EOD tasks self-heal ≤21d of missed
                        sessions (stop it during soaks)
make migrate            alembic upgrade head    make create-admin
make test / lint / typecheck / check            (check = the full gate)
cd backend && uv run pytest tests/<file> -q     (targeted)
```

## Communication style

Direct and concrete; no filler. Surface trade-offs on non-trivial decisions
and ask before committing to them. When you find bugs in existing code, fix
them and say what you found. Honest yes/no answers with one-line reasoning.

## Doc-sync ritual (run at the END of every task — not just phase gates)

A doc that disagrees with reality is worse than no doc: on 2026-08-08 a stale
status block cost real time (it claimed 974 tests and Phase 3 "in progress"
weeks after the truth had moved). So the moment a task, sub-slice, or phase
closes — or status/behaviour changes — sync the record BEFORE calling it done:

1. **`docs/PHASES.md` top block (STATE AT A GLANCE)** — the single source of
   truth. Update its content AND its `(updated <date>)` stamp.
2. **`docs/PHASES.md` "CONTINUE HERE"** — the next-session pointer; stale here
   sends the next session down a dead path.
3. **The active phase plan** (`docs/phases/phase-0X-*.md`) — status line + a
   DONE marker on the slice you closed.
4. **`CHANGELOG.md`** under Unreleased.
5. **CLAUDE.md** — the "Current truth" bullets and any "next build" pointer, if
   they moved.
6. **Memory** — the relevant fact file under the memory dir AND its one-line
   entry in `MEMORY.md`.
7. **Any other `.md` the change touched** (analysis report, README, per-phase doc).

If you changed what is true, you are not done until every place that states it
agrees. When a checkbox disagrees with the artifact or the code, trust the
artifact and fix the checkbox — that is working rule **W1**, and it applies on
DISCOVERY, not only when you were the one who changed things.

## Definition of done

`make check` green · tests shipped with the change · reversible migration ·
manual smoke · CHANGELOG under Unreleased · relevant agent review clean ·
phase report updated when a phase item closes · **the doc-sync ritual above run**
(every task, not just at a gate). The `/phase-gate` skill runs this list.

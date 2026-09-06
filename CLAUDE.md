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
  MODIFIER (execution-realism), not an entry P&L gate.** The finding also QUESTIONS 5b (a market-cap
  *size* floor may be no better — cross-tab a cheap proxy before paying the XBRL-scraper cost).
  **NEXT = run the deep backfill**
  (`scripts/backfill_indices.py 2023-07-01 <today>`) so the 200-DMA + sector-RS get history; then
  **slice 5b = the XBRL market_cap writer** (greenfield scraper) + a market-cap floor on the junk gate;
  slice 6 = news veto. Shadow→active flips need the R-track (§8-on-≥2y + sign-off). Plan in the phase-MCE doc.
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
  with no heat cap in code (Elder 6% / Tharp 6–10%); the **entry price is literally yesterday's close**
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
  `docs/phases/phase-07-live-trading-plan.md`. **The heat cap is DESIGNED, NOT BUILT** — it belongs
  inside 7.1's RiskEngine, and it must not throttle cycle 1 (a 6% cap cuts entries ~74%).
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
  POSITION — portfolio-wide is the **unbuilt heat cap** (45.3% across 23 positions vs Elder's 6%).
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
  — a §6 spec change, not done.
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
- **✅ WATCH MODE COMPLETE (ran to Fri 2026-09-04).** CAS Stage-1 accrual finished **HEALTHY:
  `cas_daily` = 1,664 rows across 8 sessions, last 2026-09-04, no missed window** (verified by query
  2026-09-04). Stage 2 (the overnight-reversal study) is now unblocked. The daily "check the row
  count each morning" obligation is **discharged — do not carry it forward.** The capture remains a
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
  spike) → 7.3 order FSM → 7.4 reconciliation. ⚠ **Five decisions block the rest and only the user
  can make them:** **D1** frozen-engine sign-off for R1 (VWAP/RVOL) · **D2** R2 build-or-drop
  (*recommend drop* — gating is closed as a programme and a ninth gate adds a trial) · **D3** the MCE
  market-cap **vendor** · **D4** concentration/sizing · **D5** `compute_levels` payoff geometry.
  ⚠ **"The rest of Phase 6 / 6.8" has no unbuilt slices** — both are GATE PASSED + CLOSED; what is
  left is the gated research track R1/R2/F1 plus three forward-evidence loops (regime **decided**,
  momentum ×1.5 **stalled** at 3 minted / 0 resolved, pair df-vs-adf accruing).
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
  is correct where QuantStats' is wrong). ⚠ **The plan buys evaluation, not edge** — the known lever
  is still `compute_levels`, above.
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

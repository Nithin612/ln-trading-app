# Phase 6 — outcome tracking + entry-selection · LIVE TRACKER

**Status: UNDERWAY (updated 2026-08-14).** Started as a plan-for-review on
2026-08-08; the three sign-off questions were answered 2026-08-12 and the build
has since run through 6.1, 6.2, the gate experiment, the §8 walk-forward, the
regime-gate overlay, and the 6.4 weight-retune experiment + shadow-promote — all
SHADOW-first (nothing on the money path yet). The proposal history is preserved
below the "Decisions (settled 2026-08-12)" line; the **DONE markers on each slice
are the current truth**. What remains is user-gated: flip the regime gate to
active, promote the retune on forward evidence, then 6.5. Phase 6 still touches
expectancy calibration and the FROZEN engine — those stay the user's calls.

---

## The one-paragraph case

Your own evidence says the binding constraint is **entry/regime selection, not
exits**: over 08-03→05, 15 trades, only **1 reached +1R**. The profit-lock work
proved the exit machinery is correct when it arms — it just had almost nothing
to protect. So Phase 6 is not "tune the ladder further"; it is "find out which
setups actually have an edge, and stop taking the ones that don't." Everything
below serves that question.

## What Phase 6 must NOT become

- **Not a re-litigation of the frozen engine.** `app/analysis/`,
  `app/backtest/engine.py` and the swing/window canon are frozen bugfix-only
  (trading-domain rules). Phase 6 measures and selects; it does not re-derive
  factor math. Any fix there regenerates the Rust oracle fixtures in the same
  commit.
- **Not tuning on the live book.** The paper record gates Phase 7. Calibrating
  against the same trades you are counting toward go-live contaminates both.
- **Not a dashboard project.** A prettier hit-rate page does not answer the
  entry question. Measurement that changes a decision, or it does not ship.

## Proposed slices

### 6.1 — Signal-level MFE/MAE (prerequisite, low risk)

Today `signal_outcomes` records first-touch ordering (`tp_first` / `sl_first`),
which answers "did it win" but not "how much was on the table" or "how close did
it come to stopping first". Without excursion data you cannot tell a bad *setup*
from a bad *stop placement*, and those need opposite fixes.

- Extend the outcome recorder to track max favourable / adverse excursion per
  signal, from the same tick stream that already drives the touch levels.
- Backfill from the 1m tape for the existing cohort (the daily report already
  loads those tapes — `tape_excursion` exists).
- Deliverable: every signal carries MFE/MAE in R multiples.
- **Known open item this closes:** "signal-level MFE/MAE missing (Phase 6)".

### 6.2 — Entry-quality attribution

The actual question. For each closed signal, decompose the outcome into:
regime at entry (ADX/VIX bucket), setup type, confidence bucket, entry-vs-fill
slippage, and time-of-day. Report which cells have positive expectancy and
which are systematically negative.

- Read-only over existing data. No engine change.
- Deliverable: a per-cell expectancy table with sample sizes, and — critically —
  **an explicit refusal to report cells below a sample threshold** (the
  StyleStatsHeader precedent: never dress up n<20).
- This is what turns "1/15 reached +1R" into "these three cells are the leak".

### 6.3 — Strategy Lab v2 on the Rust engine

Currently `POST /strategy/runs` executes the frozen **Python** `BacktestEngine`
inside the HTTP request via `to_thread`. The Rust core is ~6,180× faster and
already parity-pinned. Moving the lab onto it turns a coffee-break backtest into
an interactive one, which is what makes 6.4 practical at all.

- Keep the Python engine as the parity oracle; do not delete it.
- Add job-queue offload so a long sweep does not hold a request open.

### 6.4 — Weight tuning + promotion workflow

Only after 6.1–6.3. Rayon-parallel parameter sweeps, walk-forward validated,
with a **promotion gate**: a profile moves `shadow → active` only on forward
evidence, never on in-sample fit. The shadow layer built on 2026-08-08 is
already the mechanism — see `intraday-shadow-layer` in memory.

- This is where the flagged profiles (dc1, dc2, multibagger, and the intraday
  trio) get a real verdict instead of a stale one.

## Sequencing note

6.1 and 6.2 are read-only and independently useful — they can ship without
touching the engine or the lab. 6.3 is infrastructure. 6.4 is the payoff and
should not start until the first three are done, because tuning against
un-attributed outcomes is how you overfit.

## Decisions (settled 2026-08-12 — build started)

The three sign-offs are resolved:
1. **Framing confirmed** — Phase 6 = entry/regime selection (measure → attribute →
   select), not further exit tuning. Exit/sizing fixes already shipped (FIX_PLAN
   P0–P3).
2. **Sample-size floor = n=20** — 6.2 computes every cell but refuses to *rank* any
   cell below n=20, stated on the page (the StyleStatsHeader precedent).
3. **6.3 brought forward** — the Rust lab is sequenced right after 6.1, not last:
   6.2's statistical power lives in the 2y backtest corpus (the paper book is
   sample-starved), and only the fast lab makes corpus-scale attribution practical.

**Resulting sequence:** 6.1 (excursion data) → 6.3 (Rust-lab speed) → 6.2
(attribution at corpus scale, n≥20 floor; marginal + a few 2-D slices rather than a
fragmenting full 4-D cross-tab) → 6.4 (shadow→active promotion on forward evidence).
The external-study candidates (pair-trading / momentum / scan-catalog) enter as
**6.5** — new shadow profiles / a universe sieve measured by 6.1–6.2 and judged by
6.4, never a rewrite of this spine (see `docs/VARSITY_REVIEW_2026-08-12.md`).

**6.1 — signal-level MFE/MAE: DONE 2026-08-12.** Shared `app/services/excursion.py`
(extracted from daily_report) + `app/services/signal_excursions.compute_outcome_excursions`
+ migration `c5d6e7f8a9b0` (7 nullable columns on `signal_outcomes`) + the 5-min
expiry-sweep hook + `scripts/backfill_signal_excursions.py`. Tape-derived (1m),
direction-aware, no-look-ahead, window capped at validity, idempotent, R winsorized,
per-row commit, effective-end ordering. Pure observability; frozen engine untouched.
11 tests (all canaries mutation-verified); quant-verifier PASS, bug-hunter findings
fixed, test-guardian run by hand (spend-limited). See CHANGELOG 2026-08-12.

**6.2a — entry-quality attribution: DONE 2026-08-12.** `app/services/entry_attribution.py`
(+ `render_attribution_markdown`) + CLI `scripts/entry_attribution.py` →
`docs/analysis/attribution-<date>.md`. Per-cell expectancy by confidence · regime
(ADX) · direction · setup · time-of-day (marginals + confidence×regime 2-D),
tradeable/shadow split, n<20 no-rank floor, R winsorized ±10R, expectancy derived
from status+RR (`outcome_pnl_pct` is empty live). **First read (171 tradeable):
expectancy monotonic in regime — trending +0.20R / transitional −0.01R / choppy
−0.15R; leakiest ranked cell 70–79 × transitional −0.30R (n=63).** 7 tests,
canaries mutation-verified. See CHANGELOG 2026-08-12.

**6.3 (interactive Strategy-Lab v2) — DE-PRIORITISED.** Investigating on 2026-08-12
found the Rust backtest already exists and is parity-pinned (`run_backtest_single`,
`tests/parity/test_backtest_ext_parity.py`); only `POST /strategy/runs` still calls
the slow Python engine. So 6.3 was never the blocker for 6.2 we assumed — it's a
UI/product enhancement (switch the lab API to Rust + job-queue), not a Phase-6
critical-path item. Do it when the interactive lab matters.

**6.2b — attribution at corpus scale: DONE 2026-08-13.** `app/services/corpus_attribution.py`
+ CLI → `docs/analysis/attribution-corpus-<date>.md`. `run_universe` over the Nifty50
daily corpus (816 trades, ~0.6s) → per trade reconstruct regime (ADX level at the
decision bar) + MFE/MAE (shared `tape_excursion`) → the shared `attribute_rows`. The
frozen engine is untouched (the Rust backtest already exists + is parity-pinned).
**The leak, with power: confidence 80–89 +0.20R (n=307) vs 70–79 −0.07R (n=434); regime
transitional −0.10R vs trending +0.24R; 70–79 × transitional −0.14R (n=223).** 7 tests;
quant-verifier PASS, bug-hunter CLEAN. See CHANGELOG 2026-08-13.

**The Phase-6 verdict (6.2): the entry-selection leak is the 70–79 confidence band**
(the bulk of signals) and the **transitional ADX regime** — both net-negative
expectancy at corpus scale, while 80–89 confidence and trending are the edge. This
is the evidence for **raising the confidence gate toward 80 and/or a regime gate**
(the Market-Context-Engine idea). Any such change is behaviour-changing → §8 backtest
+ user sign-off; the engine stays frozen until then.

**Gate experiment — DONE 2026-08-13** (`scripts/gate_experiment.py` →
`docs/analysis/gate-experiment-<date>.md`). Read-only corpus comparison of the levers:
**gate-70 + skip-transitional wins on both axes — total-R +73.8 (vs +41.2 baseline,
~+79%) and mean expectancy +0.158R (vs +0.052), keeping 477 trades (vs 270 at
gate-80).** Raising the gate to 80 alone *lowers* total-R below baseline; both together
over-filter. **The regime gate is the high-value lever, not a confidence-gate bump.**

**Regime-gate §8 walk-forward — DONE 2026-08-13** (`app/services/gate_walkforward.py`
+ `scripts/gate_walkforward.py` → `docs/analysis/gate-walkforward-<date>.md`; 14 unit
tests, quant-verifier PASS). Promotes the gate experiment to §8 grade — it adds the
three metrics §8 gates a merge on (the experiment omitted them) and answers the
circularity of scoring a corpus-mined rule on that same corpus. **The finding HOLDS
out-of-sample:**
- **§8 metrics all improve** (all moves > ±5% → sign-off): win rate 40→43%, per-trade
  Sharpe +0.034→+0.097, max drawdown 36.5R→20.4R, total-R +41.2→+73.8.
- **Consistency:** skip-transitional wins expectancy in **5/5** sequential time folds
  (2023-09→2026-08); its biggest lift is in the *worst* fold (2025-06→12: −28.3R/−0.170
  → −2.0R/−0.018).
- **Anchored walk-forward (OOS):** learn the negative-expectancy regime from each
  expanding *past* window (every window re-learns "transitional"), apply forward →
  OOS expectancy **+0.067→+0.142** (Sharpe +0.044→+0.091, maxDD 36.5R→20.4R).

DRY: a shared `realized_r(row)` helper now backs the attribution cells, the gate
experiment, and this (byte-identical output confirmed). Read-only; frozen engine
untouched.

**Regime-eligibility overlay — BUILT shadow-first 2026-08-13** (`app/signals/regime_guard.py`
+ `regime.py`; `settings.regime_gate_mode`, default `shadow`; quant-verifier PASS +
bug-hunter CLEAN). The §8-validated gate, as a DOWNSTREAM overlay that never touches the
frozen engine (the `risk_guards.py` precedent): it reads a committed signal's own ADX
regime and, in `active` mode only, rejects a paper order in transitional (20–25). Default
shadow = measures, never suppresses. `app/services/regime_gate_shadow.py` +
`scripts/regime_gate_shadow.py` → `regime-gate-shadow-<date>.md` = "measure before gating"
on the LIVE cohort (first read: suppressed −0.061R, gating lifts live expectancy
−0.034→−0.016, consistent with the backtest). Design decision (recorded): NOT an engine
change / no Rust-fixture regen — the frozen engine already emits the ADX level in the
factor payload, so the gate is a filter on top and the §8 evidence carries over unchanged.

**First-class ADX level — DONE 2026-08-14** (migration `e3f4a5b6c7d8`; quant-verifier
PASS-WITH-NOTES + bug-hunter CLEAN). The second active-flip precondition. `Signal.regime`
is persisted at commit and `regime_guard.signal_regime` reads it (legacy NULL falls back to
on-the-fly recovery). Recovered from the frozen ADX factor's DECISION BRANCH — the phrase it
emits reflects the comparison it made at full precision before the `f"ADX={x:.1f}"` display
rounds — so the money-path gate no longer hangs off prose parsing and the raw-choppy
[19.95, 20) / [24.95, 25) band edges are no longer misbucketed. Set at all 3 commit sites;
frozen engine untouched. Branch-recovery agrees with the backtest's raw-number bucketing
except at raw ADX == 25.0 exactly (measure-zero; the conservative direction). +9 tests (two
band-edge canaries mutation-verified). **Shadow-alignment follow-up — ✅ DONE 2026-08-14 (same session):** the live regime-gate
shadow (`regime_gate_shadow.measure`) now buckets by the persisted `signals.regime` (via
`Row.regime`, identical to `regime_guard.signal_regime`), so forward evidence and enforcement
use the identical partition; §8/corpus/attribution numbers unchanged. quant-verifier PASS. +3 tests.

**NEXT — recommended lead first; each starts on user command (nothing auto-advances):**

1. **Flip the regime gate shadow→active — ✅ DONE 2026-08-14 (user decision, reversible).**
   Set via `REGIME_GATE_MODE=active` in `.env` + backend/worker restart (`place_order` reads it
   live); the paper order path now rejects transitional (20–25) entries. Revert = `shadow` +
   restart. **Precondition — first-class ADX level: ✅ DONE 2026-08-14** (migration
   `e3f4a5b6c7d8`): `Signal.regime` is persisted at commit, recovered from the frozen ADX
   factor's DECISION BRANCH (not its 0.1-rounded prose, so the raw-choppy [19.95,20) edge
   is no longer misbucketed), and the gate reads the durable field (`signal_regime` prefers
   it; legacy NULL falls back). quant-verifier PASS-WITH-NOTES + bug-hunter CLEAN; frozen
   engine untouched. **Governance precondition — MET 2026-08-14:** the user gave the §8 sign-off
   (win / Sharpe / drawdown all > ±5%) by choosing to flip, accepting the accumulated cohort's
   evidence (44 suppressed trades, all 3 §8 metrics improve live). Now monitoring live via the
   daily shadow banner (`regime-gate-shadow-<date>.md`) — if it diverges (⏳ NOT READY), revert. **Follow-up — ✅ DONE
   2026-08-14:** the live shadow measurement now buckets by the persisted `signals.regime`
   (identical partition to the gate). **Forward evidence is now surfaced every `make analysis`**
   (`regime-gate-shadow-<date>.md` + a **Flip readiness** banner; `forward_evidence_ready`, bar =
   ≥20 resolved suppressed trades + suppressed net-negative + gating lifts expectancy). **First
   read: ALREADY ✅ READY** — accumulated live cohort since 2026-07-19 has 44 suppressed trades,
   all three §8 metrics improve on live (expR +0.027→+0.089, total-R +2.8→+5.5, maxDD 8.8→4.7R,
   suppressed −0.061R). OPEN: accept the accumulated cohort (met now, out-of-sample vs the backtest
   corpus) vs require strictly-forward-only evidence (~6-10wk) — user's call. Checkpoint 2026-09-15.
   The flip still needs explicit §8 sign-off. Highest value — where the edge becomes P&L.
2. **6.4 — weight retune + promotion. Experiment DONE 2026-08-13** (`app/services/weight_retune.py`
   + `scripts/weight_retune.py` → `weight-retune-<date>.md`; quant-verifier FAIL→resolved).
   The 6.2 leak is per-FACTOR but the only weight lever is per-GROUP, and groups mix
   helping+hurting factors, so a naive "downweight the hurting factors" isn't expressible —
   the experiment therefore SWEEPS group multipliers (each ×0.5/×1.5) on the corpus, §8
   metrics + per-fold consistency. **Lead candidate = `momentum ×1.5`** (cross-engine-
   consistent): expR +0.052→+0.070, total-R +41.2→+50.4, Sharpe +0.034→+0.045, maxDD
   36.5→32.4R, 4/5 folds (up-weighting momentum *tightens* the confluence). Runners-up
   `structure ×0.5` / `pattern ×0.5`. **Shadow-promoted DONE 2026-08-14** (migration
   `d2e3f4a5b6c7`): `retune_momentum_x15` + a `retune_base` control now run as 1d/eod SHADOW
   profiles over Nifty50 (no setup gate = base engine + multipliers, rr-2 exit both arms so
   the A/B isolates the entry effect), minting `is_shadow` signals on the nightly path,
   measured by 6.1/6.2 attribution (bucketed by `profile_key`). Verified end-to-end. **To
   promote:** once the shadow A/B (`retune_momentum_x15` vs `retune_base` in the daily
   attribution Setup×shadow table) beats base forward → create an active retune profile on
   sign-off (best-of-12 = in-sample until the shadow confirms; ~1–2 signals/arm/day, so weeks
   of accrual). **No DOW_TREND grouping bug** (investigated + WITHDRAWN 2026-08-14): a
   *scoring* DOW_TREND is tagged `["structure"]` (analysis/structure/dow.py) and Python
   `_factor_group` checks tags before names → it groups `structure`, matching the Rust engine;
   the `_GROUP_NAMES` "trend" entry is dead code for it (only a score-0/tagless DOW_TREND hits
   it — immaterial). An earlier "engine-specific" flag came from testing that tagless case; an
   attempted fix (→trend) INVERTED parity and was reverted (quant-verifier FAIL). All six
   weight groups are cross-engine consistent. Do NOT change DOW_TREND's group — see
   `dow-trend-grouping-gotcha` in memory.
3. **6.5 — pair-trading, market-neutral candidate.** Regime-agnostic — sidesteps the
   choppy/transitional tape our directional profiles leak in. A new shadow profile
   judged by this same 6.1–6.2 attribution.

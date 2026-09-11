# BUILD QUEUE — the only operational document

**Updated 2026-09-11 (round 10).** ⭐ **This file is what a working session reads. It is not the
research record.**

- **The research record** is `docs/analysis/quant-panel-adjudication-2026-09-10.md` (5,700+ lines,
  ten rounds, never pruned). ⛔ **Do not read it to decide what to do next** — read this.
- **The status record** is the `docs/PHASES.md` top block.
- **The invariants** are `CLAUDE.md` + `.claude/rules/`.

⚠ **Adopted from ChatGPT's round-10 process note, and its diagnosis was correct:** the adjudication
is an excellent forensic archive and a dangerous engineering specification. Splitting them is the
fix. ⭐ **Its `CURRENT_SYSTEM_CONTRACT.md` is deliberately NOT created — `CLAUDE.md` plus
`.claude/rules/` already serve that role, and W2 says extend the thing that exists rather than adding
a parallel one.**

---

## THE RULE THAT DECIDES WHAT LANDS HERE

> ⭐⭐ **An item enters this queue when it is converged across sources **OR** settled by our own
> measurement — never on consensus alone.**

⚠ **This is not pedantry; it is the single most expensive lesson of ten rounds.** Unanimous panel
agreement has been wrong repeatedly: all five sources demanded a factor-level IC study that had
already been run; all five recommended a cross-sectional ranker against a measured prior; both
round-7 "inversions" were unanimous and both were withdrawn. ⭐ **Meanwhile the best items each came
from a single source** — the cash rail, the normalizer decomposition, the tick grid, the level-stage
question. ⇒ **Consensus is a good filter for PRIORITY and a bad one for TRUTH.**

## STATE MACHINE

```
PARKED  ──(evidence it is worth capacity)──>  BUILD  ──(acceptance test)──>  MEASURED  ──>  ACCEPTED
```

⚠ **"Parked" never means "wrong".** It means *not sufficiently justified to consume capacity now*.
The parked register with per-item reasons is §13.11 of the adjudication.

---

## THE QUEUE

⭐ **Ordered by money-at-risk first, then by cost.** ⚠ **B2 is first because it is the only item on
this list where real money is at stake** (Claude, round 10 — accepted: three slots at the median 5%
stop currently require **120% of capital** with nothing checking).

### B2 — `Σ notional ≤ available cash` rail · ½ day · ⭐ PRECONDITION FOR CYCLE 2

- **WHY** `[code]` The constraint **does not exist anywhere**: not in `paper_broker`, not in
  `risk_engine`, not in the backtest. Three slots at the median 5% stop need **120% of capital**.
  Identity-enforcing ⇒ **no DSR bar** under §5.4's asymmetric burden.
- **SCOPE** One `Restriction` + one context loader in the existing registry. **Do not add a second
  sequence** (W2).
- **FILES** `app/signals/restrictions.py` · `app/services/risk_engine.py` · `app/core/config.py` ·
  `.env.example`
- **ACCEPTANCE** a test proves 3 slots at the median 5% stop are refused · `off` by default, flips
  `active` at the cycle-2 reset beside the heat cap and the position-count cap · `.env.example` and
  the docs updated **in the same commit** (W3)
- **ARTIFACT** a passing test named for the defect · a CHANGELOG entry
- ⛔ **DO NOT** clamp — *reject, don't clamp*. ⛔ **DO NOT** flip it `active` now; it would throttle
  cycle 1.

### B3 — `paper_tick_size` → a dated price-band SCHEDULE · ½ day · ⭐ BEFORE CYCLE 2

- **WHY** ₹0.05 is the wrong grid for sub-₹250 names since ~2024 (on-grid share fell
  **0.98 → 0.49 → 0.22** across 2019/2024/2025). Published exchange schedule ⇒ **no forward-evidence
  bar**. Changes a recorded number ⇒ before cycle 2.
- **SCOPE** a table with `valid_from · price_lo · price_hi · tick · source`; `_round_tick` reads it.
- **FILES** `app/core/config.py` (retire the scalar) · `app/broker/paper_broker.py` · a new schedule
  module or data file
- **ACCEPTANCE** a ₹39 name rounds on ₹0.01 and a ₹2,500 name on ₹0.05 · the **adverse**-rounding
  contract is preserved (a BUY ceils, a SELL floors) · the source is cited **in the table** (W5)
- ⛔ **DO NOT** write `tick = 0.01 if price < 250 else 0.05`. The phase-in is **staged**, so the
  schedule is date-dependent as well as price-dependent. **Gemini proposed exactly that constant and
  it is the thing §12.19b warns against.**
- ⚠ **Blast radius is the paper broker ONLY** (3 call sites) and the artifact is **0.051R** at a 2%
  stop, not 0.064R. It contaminates **no research number** (§12.30a).

### B1 — delete `_near_expiry` and `_choppy` from the display path · 2 hours

- **WHY** `[measured]` They hide **67%** of the offered set and separate **nothing**: contrast
  −0.0001, **p = 0.999** on 185 trades (§12.31e). Neither is in `restrictions.py`; neither is applied
  by the order path ⇒ **`restrictions.py` is not the single source of truth its docstring claims.**
- **SCOPE** `app/api/v1/signals.py:267-289`. Delete, or declare with `enforced_by = DISPLAY`.
- **ACCEPTANCE** a test asserts the default listing and the order path admit the **same set** ·
  offered-set counts re-run and recorded
- ⭐ **Side benefit:** removes two axes from §12.8's corpus-vs-deployed estimand gap at zero cost.

### B4 — the gap guard tests SPAN, not endpoints · ½ day

- **WHY** `GAP_LO`/`GAP_HI` are hardcoded constants describing **one known incident** — exactly what
  **W5** forbids. The session calendar is the owner. The current guard misses **1.2% of panels**
  (worst case: 516 sessions inside a 300-row window).
- **SCOPE** `sessions_between(w[0], w[-1]) ≤ WINDOW × (1 + tol)` against the market calendar.
- **FILES** `backend/scripts/swing_dependence_probe.py` · `positional_probe.py` · ⚠ **and
  `run_single_stock`'s bar-50 walk, which has no guard at all**
- **ACCEPTANCE** catches the 5,462 straddling panels **and** the 204 internally non-contiguous ones ·
  `GAP_LO`/`GAP_HI` **deleted**

### B5 — E1 re-specified: positional in FOUR units · ½ day

- **WHY** The swing stop-width family is now **closed** (§12.31d: the contrast decays and flips sign
  as `1/w` and then `drift×T` are removed). ⚠ **Positional is NOT the same mechanism** — its buckets
  carry **opposite signs** and its *reachable* cohort is the **better** one, where swing's is worse.
  ⚠ **And its contrast has never been computed: t = −1.47, p = 0.14, MDE 0.74R** (§12.27).
- **SCOPE** `positional_probe.py` gains `T`, `bench`, `excess` — **from the same `basket_series`
  owner in `swing_dependence_probe.py`. Do not write a second one** (W2).
- **ACCEPTANCE** buckets in R · raw % · ÷ATR20 · **excess vs the matched basket** · **contrasts with
  SEs, never levels** · mean/median `T` and `E[1/w]` per bucket · split by the gap flag
- ⭐ **ADDED IN ROUND 10:** also emit the **trailing** 5/10/20-session basket return at entry, so the
  positional book gets the same entry-timing decomposition the swing book got (§12.33).

### B6 — E2 as THREE estimands · 1 day · ⭐⭐ THE LAST QUESTION THAT CAN CHANGE DIRECTION

- **WHY** The specified test (full cross-sectional IC) is **not** the deployed question, and the
  gate-conditional version is a **collider** on the score's own output. Three sources converged on
  this independently (§12.28).
- **SCOPE**
  - **3a** unconditional IC of the composite across the eligible universe, **h = 5d pre-registered**
  - **3b** the matched-tail contrast — gate-passers vs date-and-characteristic-matched non-passers
  - **3c** the gate-conditional IC, **reported and labelled a collider, never decided on**
- **ACCEPTANCE** ⚠ **`sd(IC_t)` and `E[z|selected]` emitted as OUTPUTS, not assumed** (`factor_sweep`
  does **not** store per-date ICs, so 0.10 cannot be retired any other way) · power
  **coverage-weighted** (the cross-section runs **46 → 250** and `1/√46` = 0.147 exceeds the whole
  0.018–0.071 break-even band) · **the four-branch decision tree written down BEFORE the run**
- ⛔ **DO NOT** start coding before the three estimands, the horizon and the decision tree are
  written. **Under-specifying the decisive test is how KILL LINE 3 went wrong twice.**
- ⭐ `[git]` **`confluence.py` has been untouched since the 2026-07-04 freeze and corpus analysis
  began five weeks later** ⇒ this is a **test**, not a fit.
- ⭐ **And the shipped scorer IS testable**: the only non-price factor (`FII_DII_FLOW`) scores on
  **0 of 487** panels, so there is no "price-only variant" problem (§12.32).

### B7 — MFE/MAE + the hazard curve · ½ day, folded into B6's pass

- **WHY** ⭐ **It retires a PARKED row for free** (Claude, round 10 — accepted): §13.11 lists
  hold-period-as-breadth-lever as UNCONVERGED, and the hazard curve decides it. **And** it separates
  *"no signal"* from *"signal destroyed by the barrier geometry"*, which B6 alone cannot.
- **SCOPE** per-trade MFE/MAE in raw % / ATR / R · `P(+1R before −1R | day d)` for d = 1..20 ·
  time-to-MFE and time-to-MAE by stop-width bucket and direction
- ⭐ **And separate the `T = 0` cohort**: 27 of 185 trades (14.6%) exit on the bar they opened, at
  **mean R −0.7034 and a 14.8% win rate** (§12.31f). **1 trade in 7 dies on its entry bar and this
  has never been isolated anywhere.**

### B8 — the append-only ledger · ⭐ TIMEBOXED TO ONE DAY

- **WHY** ⭐ **Not for this strategy — for any successor.** `positions` = `orders` = 0, which is why
  ten rounds of live-tape argument were unfalsifiable and why the human-picker question is
  permanently unanswerable for history.
- **SCOPE** ⚠ **ONE append-only table with the five node types as a discriminated column** —
  `DecisionSnapshot · OrderIntent · Execution · PositionLifecycle · PerformanceRecord` — **not five
  tables.** Every row carries `code_commit · spec_version · experiment_id · data_version ·
  created_at`. Nightly **off-box** export.
- **ACCEPTANCE** a reversible migration · the export runs and lands off-box · one round-trip test
- ⛔ **DO NOT** build the full nine-schema design (`ExperimentManifest` / `DataSnapshot` /
  `UniverseSnapshot` as separate tables). ⭐ **Claude's round-10 argument is accepted and the base
  rate is the evidence: ONE item shipped as code in the previous fifty days. The five-table version
  is the version that does not ship.** The extra schemas become **columns** on the manifest row.

---

## WHAT IS PARKED

Full register with a reason per row: **§13.11** of the adjudication. One-line summary:

| item | why it is parked |
|---|---|
| does the **human picker** add value? | ⛔ **BLOCKED** — `positions` = `orders` = 0 and the offered→selected mapping was never logged. **B8 unblocks it forward only** |
| point the apparatus at **allocation** | ⚠ **UNCONVERGED** — sharpest strategic read on the table, and a **new strategy class** 50 days from the decision date |
| **3-day holds** as the breadth lever | ⚠ **UNCONVERGED** ⇒ **B7 decides it** |
| unified `ExecutionKernel` · tax layer · PIT `UniverseSnapshot` · factor correlation matrix · turnover/IC frontier · data-gap reconstruction · F&O | ⏸ **SEQUENCED** — each has its specific blocker stated in §13.11 |
| **another review round** | ⛔ **CLOSED** (§17c) |

⛔ **AND ONE THING THAT IS FORBIDDEN, NOT PARKED.** Gemini's round-10 brief proposed *"deactivate
dead factors (`DOW_TREND`, `MARUBOZU`, `FII_DII_FLOW`)"*. ⚠ **`app/analysis/` is FROZEN and
`docs/SIGNAL_ENGINE.md` is hook-protected.** Removing a factor is a **spec change** requiring
explicit user instruction, a §8 backtest regression **and** regenerated Rust oracle fixtures in the
same commit. ⭐ **The measurement (§12.32) is a finding to record, not a licence to edit the engine.**

---

## PROBE CONVENTIONS — adopted round 10

1. ⭐ **A probe emits a `--dump-trades` artifact.** One expensive pass writes the per-trade table
   **before** the report sections; every contrast downstream is a cheap read. (Deepseek's round-10
   point — it produced five of round 9's adjudications from a single run.)
2. ⭐ **A round only happens if a probe runs with it.** Round 9's two recomputing sources produced
   five of seven decision changes; the source that only read produced zero, twice running.
3. ⭐ **Report the CONTRAST with its SE, never two levels.** Eight instances of this error so far.
4. ⭐ **Pair a benchmark to each observation's own window.** Never subtract a scalar measured over a
   different set of sessions (§16.1c's time-dimension rule).
5. ⭐ **Publish a numeric prediction before running the test.** Kimi did it for E3 and Claude did it
   for the BUY/SELL contrast; both made their runs tests rather than searches.

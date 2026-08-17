# Phase 6.8 (PROPOSED) — Execution Realism & Exchange-Safety · adjudication + build tracker

**Status: APPROVED 2026-08-17 (user) — scope LOCKED, nothing built yet.** Decisions taken:
**(1)** a distinct **Phase 6.8** between Phase 6 and MCE; **(2) full scope** — all six
paper-safe slices + the research track (R1/R2) + the F1 `market_cap` spike, with the
research/spike items individually go/no-go-gated and R1 (the only frozen-engine change)
sequenced last and **non-blocking**; **(3)** F1 pulled forward as a **bounded** spike
(`market_cap_cr` only). This document adjudicates
`REAL_WORLD_NSE_BSE_TRADING_ANALYSIS.md` (the three-model external review —
Gemini 3.6 Flash / 3.1 Pro / GPT + your own notes, dated 2026-08-16) point by
point against the **actual code** (verified 2026-08-17, evidence cited inline),
then bundles the genuinely-actionable, **paper-safe** subset into a new phase
that slots **after Phase 6 closes and before the Market Context Engine (MCE)**.

Everything here follows the house discipline that carried Phase 6: **shadow-first,
the frozen confluence engine untouched, `§8` backtest before any behaviour change,
quant-verifier / bug-hunter / ui-reviewer before "done."** Positioning is **settled
(§10): a distinct Phase 6.8**, inserted between Phase 6 and MCE.

---

## 0. How to read this — the four verdicts

Every item in the review lands in exactly one bucket. I use these labels
throughout so you can cross-walk to the review's own section numbers:

| Verdict | Meaning |
|---|---|
| **✅ ALREADY HAVE** | Built and shipped. The reviewers are working from a stale snapshot; do **not** rebuild. Evidence cited. |
| **🟢 TAKE (this phase)** | Genuinely new, paper-safe, buildable now without a live-order path. This is what Phase 6.8 *is*. |
| **🟡 DEFER → MCE** | Real, but it *is* the Market Context Engine (already the named phase after 6) — building it here would just be starting MCE early. |
| **🟠 DEFER → Phase 7** | Only bites once a **live order** exists (GTT, SPAN, freeze-slicing, physical settlement, multi-broker). Cannot be validated in paper; belongs with live hardening. |
| **🔴 REJECT** | Wrong tier for a solo retail platform on Kite, or contradicts a hard constraint, or already tested-and-rejected. Reasoned, not dismissed. |
| **⚫ FACT-CHECK** | The claim describes code that does not exist. Flagged so it isn't actioned. |

**The one distinction that governs everything below:** an *overlay / report /
paper-fill* change leaves the frozen engine alone (the `risk_guards.py` /
regime-gate pattern) and is cheap and safe. A *new confluence factor* (anchored
VWAP, RVOL, order-book imbalance) **touches the frozen engine** → it needs Rust
oracle-fixture regeneration + a `§8` regression + your sign-off, so it lives on a
slower **research track**, never in the fast lane. Live-order mechanics are Phase 7
by definition. Keeping these three lanes separate is what makes this plan
"clinically" safe.

---

## 1. Executive verdict — the whole review on one screen

| Review § | Item | Verdict | Lands |
|---|---|---|---|
| 1.1–1.5 | Rust core, no-look-ahead, honest accounting, risk rails, replay | ✅ accurate self-assessment | — |
| 2.1 | No live execution; in-memory trailing-SL tail risk | 🟠 Phase 7 | GTT/SL-M slice |
| 2.2 | Silent EOD outages; single-broker dependency | 🟢 **TAKE** (outage alarm) + 🟠 (multi-broker → P7) | 6.8.6 / P7 |
| 2.3 | Edge degrades in chop (ADX 20–25); negative profiles shadowed | ✅ already attacked (regime gate ACTIVE + pairs) | — |
| 2.4 | No market depth (L2); flat 2bps slippage underestimates illiquids | 🟢 **TAKE** | 6.8.1 + 6.8.2 |
| 2.5 | No SPAN margin; no physical-settlement handling | 🟠 Phase 7 (and index-only today → not a current exposure) | P7 |
| 3.1.1 | Exchange-resident GTT / SL-M stops | 🟠 Phase 7 (backlog P0.1) | P7 |
| 3.1.2 | Upper/lower **circuit-limit filter** | 🟢 **TAKE** (best new item) | 6.8.3 |
| 3.1.3 | Freeze-qty limits + order slicing (iceberg) | 🟠 freeze-awareness → P7; 🔴 iceberg (already rejected) | P7 / — |
| 3.2.4 | SEBI algo-approval / broker-approved routing | 🟠 Phase 7 constraint (documented) | P7 |
| 3.2.5 | Multi-broker failover adapter | 🟠 Phase 7 (backlog; Nautilus BrokerAdapter) | P7 |
| 3.2.6 | Real-time SPAN / exposure margin | 🟠 Phase 7 | P7 |
| 3.3.7 | Market-depth analytics + VWAP impact cost | 🟢 **TAKE** | 6.8.1 + 6.8.2 |
| 3.3.8 | Market Context Engine + earnings blackout + 200-DMA/VIX gate | 🟡 **this IS the MCE** | MCE |
| 3.3.9 | Corporate-action adjustment of **open** positions | 🟢 **TAKE** (paper) + 🟠 (live → P7) | 6.8.5 / P7 |
| 3.3.10 | Physical-settlement expiry auto-squareoff | 🟠 Phase 7 (index-only today → no exposure) | P7 |
| 6.1 | UI token discipline, rAF batching, tabular-nums, glyph+colour | ✅ accurate; 60fps **measured & met** | — |
| 6.2/6.3 | React-DOM GC, WebGL/WASM grids, SharedWorker/Tauri multi-monitor | 🔴 over-engineered (budget already met, evidence) | — |
| 6.3.2 | **Continuous open-book MTM** report | ✅ mostly built → 🟢 **TAKE** (small gap only) | 6.8.4 |
| 6.3.4 / 8 | ORB gate / Anchored VWAP / RVOL / decoupled IntradayEngine | 🔴 separate-engine + gate-lower; 🟢 factors on **research track** | R1 / — |
| 7.1 | Kelly + volatility-parity sizing | 🔴 Kelly (rejected); ✅ partial vol-scaling already exists | — |
| 7.2 | TWAP/VWAP/POV smart-order-router | 🔴 rejected (irrelevant at retail size) | — |
| 7.3 | Monte-Carlo VaR + portfolio-Greek auto-hedge | 🔴 VaR rejected; simple exposure-heat → P7 | P7 |
| 7.4 | Event-sourcing / CQRS / Kafka | 🔴 over-engineered; P7 reconciliation solves the real risk cheaper | — |
| 7.5 | kdb+ / ClickHouse / ArcticDB tick DB | 🔴 rejected (Timescale fine at our scale, soak-proven) | — |
| 9.1 | F&O dark = IV-rank gate working + bhavcopy lag | ✅ accurate diagnosis (matches §7 health) | — |
| 9.2/9.3 | Long/short-vol dual regime; live Greeks off tick | 🟡 dual-regime → MCE/F&O-ext; 🟠 live Greeks → P7 | MCE / P7 |
| 9.4 / 11.1 | **Spread-width liquidity gate** to unlock weeklies | 🟢 **TAKE** (research track; resolves an OPEN ruling) | R2 |
| 10 | "yfinance backtester wiped the account in an Aug-14 stress test" | ⚫ **FABRICATED** — no such file/test exists | §2 |
| 11.2 | `calculate_vmi` / `calculate_momentum_oscillation` indicators | ⚫ **FABRICATED** — do not exist | §2 |
| 11.3 | Cross-exchange / calendar / skew arbitrage | 🔴 rejected (HFT/co-lo tier; stocks aren't on MCX) | — |
| 12.1 | Separate SwingEngine + 60% gate + soft ADX scaling | 🔴 violates ≥70% confluence-only hard constraint | — |
| 12.1.4 | Early-arm profit-lock (0.5 R) | ✅ already planned (FIX_PLAN P2) → evidence-first tune | — |
| 12.1.5 | Fill-based sizing | ✅ **already shipped** (`paper_broker.size_for_fill`) | — |
| 13.2 | Mean-reversion pairs | ✅ **already built** (Phase 6.5) | — |
| 13.4 | Trend-following gated by ADX | ✅ already have (regime gate + ADX confluence) | — |
| 14 | Fundamental data sources (TradingView-screener / yfinance / Screener.in) | 🟡 MCE keystone; 🟢 optional **spike** here to de-risk MCE | F1 / MCE |

**Bottom line:** of ~40 distinct suggestions, **~5 are genuinely new + buildable now**
(depth capture, spread-aware slippage, circuit filter, open-book gap, CA-adjust,
outage alarm), **~8 are already built**, **~10 are the MCE or Phase 7 we already
planned**, **~12 are over-engineering we should decline with reasons**, and **~2 are
fabricated code claims.** That distribution is the point of this document.

---

## 2. Fact-check first — what the reviewers invented (credibility screen)

Before spending effort, weigh the source. Several "flaws" describe code that
**does not exist**. Actioning them would send you hunting phantom bugs.

| Claim (review) | Reality (code evidence, verified 2026-08-17) |
|---|---|
| §10: backtester lives in `backend/app/backtester.py`, uses **yfinance** | No such file. Engine is `backend/app/backtest/engine.py` (`BacktestEngine`) + Rust `run_universe` (`engine-core/src/backtest.rs:312`). **Zero** yfinance/Yahoo usage anywhere in the repo (only match is prose in the review itself). |
| §10.2.1: "**All-in** 100%-of-capital sizing wiped the account on Aug-14" | Sizing is risk-first: `analysis/risk.py:33` `compute_quantity = floor(capital·risk%/100 / |entry−SL|)`, called by the backtest at `engine.py:345`, then **reduced 25% in high-ATR regime** (`volatility_adjusted_qty`, `engine.py:350`). No all-in path exists. The "Aug-14 stress test" did not happen. |
| §10.2.4: "trades executed at **56%**, below a **60%** gate" | Gate is **70**, not 60 (`core/config.py:106 min_signal_confidence=70`); effective 65/70/75 via ADX (`confluence.py:170–174`); profiles floored `ge=70` (`schemas/profile.py:204`). **No 60% gate exists.** |
| §10.3: "`TestBacktester` is a placeholder that asserts `True`" | No such class. Real tests: `TestBacktestEngine` (`tests/analysis/test_backtest.py:24`), `TestBacktestParity` (`tests/parity/test_engine_parity.py:118`), walk-forward goldens, intraday-parity. |
| §11.2: `calculate_momentum_oscillation` / `calculate_vmi` in `indicators.py` | `backend/app/indicators.py` does not exist. Neither function exists anywhere. Indicator math is `analysis/indicators/{adx,ema,rsi,macd,bbands,volume}.py` mirrored in Rust `engine-core/src/indicators/`. |

**Read for the plan:** the *architectural* commentary (§1–§3, §6.1, §9.1) is largely
sound and matches our own docs — those reviewers clearly read the design. But the
*code-level* deep-dives (§10, §11.2, and the swing/intraday "the engine does X"
specifics) are **hallucinated against a plausible-but-fictional codebase.** Trust
the former; verify the latter. Nothing in §10 is actionable.

---

## 3. What the review flags that we already shipped (do NOT rebuild)

The reviewers scored us as if these were gaps. They are done — cited so we don't
spend a rupee twice.

- **Honest fills** — gap-through-stop (paper SL books the gapped open, not the stop)
  + adverse slippage (`paper_slippage_bps` default 2). Shipped 2026-08-01 (CHANGELOG;
  memory `architecture-review-2026-08`). *Answers §1.3, and is the base 6.8.2 builds on.*
- **Fill-based (not entry-based) sizing** — `paper_broker.py:118 size_for_fill`
  ("Risk-first quantity sized from the ACTUAL fill price"). *Directly answers §12.1.5,
  which claims we size from entry and oversize; we do not.* The chase→oversize guard
  (FIX_PLAN P1) sits on top.
- **Volatility-aware sizing** — `volatility_adjusted_qty` cuts qty 25% in a high-ATR
  regime (`engine.py:350`). *Partial answer to §7.1's volatility-parity; the full
  ATR-inverse target-vol is a possible Phase-6 sizing experiment, not a new build.*
- **Signal-level MFE/MAE** — `signal_outcomes.{mfe_price,mfe_r,mae_price,mae_r}`
  (`models/signal.py:235–241`); position-level MFE `positions.{peak_price,peak_pnl}`.
  Phase 6.1. *Answers §6.3.2's excursion ask (mostly — see 6.8.4 for the one gap).*
- **Open-book EoD mark-to-market + open heat, carried across days** —
  `daily_report.py` renders "Open book mark-to-market (gross, EoD)" and "Open
  portfolio heat (Σ risk-at-fill on open positions)" over every position open at
  day-end regardless of open date (`:375,:410,:518,:532`). *§6.3.2 claims `make
  analysis` is "blind to open MTM"; it is not — see 6.8.4 for the narrow real gap.*
- **Market-neutral mean-reversion pairs** — Phase 6.5, fully built shadow-first.
  *§13.2 lists this as a "new idea"; it shipped 2026-08-15.*
- **Trend-following gated by ADX** — the regime gate (ACTIVE) + ADX in the confluence
  scorer. *§13.4 / §7.4-"trend strength" — already the system's spine.*
- **Regime/chop defence** — §2.3's core complaint is exactly what Phase 6 attacked and
  quantified; the regime gate is live and pairs cover choppy tape.

---

## 4. Phase 6.8 — thesis, scope, and why it slots here

**Thesis.** Everything real-world about NSE/BSE execution that we can **build and
measure in paper/shadow without a live-order path** belongs here — so that (a) our
paper P&L stops flattering itself on illiquid names and un-fillable stops, and
(b) Phase 7 becomes almost pure broker-wiring because every guard is already built
and validated. This is the same "shadow-first, de-risk the scary phase before it
starts" posture that made Phase 6 safe.

**The keystone that makes it cheap.** The tick consumer already subscribes
`KiteTicker.MODE_FULL` (`tick_consumer.py:141`), so **5-level order-book depth is
already arriving on every tick** — and we extract only `last_price`
(`tick_consumer.py:234`), discarding the book. The review's four best real ideas
(spread-aware slippage §2.4/§3.7, circuit proximity §3.1.2, liquidity/spread gate
§9.4/§11.1, order-book imbalance §11.2) all reduce to "stop throwing the book away."
One small extract unlocks the whole cluster.

**Scope boundary (hard).** Phase 6.8 touches **overlays, reports, and paper-fill
realism** only. It does **not** touch the frozen confluence engine (factor
candidates are a separately-gated research track, §5 R1) and does **not** place a
live order (that is Phase 7). If a slice would need a live order to prove itself, it
is not in this phase.

**Positioning.** Phase 6 closes → **Phase 6.8** → MCE → Phase 7. See §10 for the
numbering decision.

---

## 5. The slices

Each slice is a vertical slice (model → migration → service → API → UI → tests) with
the project DoD. Effort is relative (S ≈ a session, M ≈ 2–3, L ≈ a week). Reviews
listed are the mandatory ones for the files touched.

### 6.8.1 — Order-book depth capture (the foundation) — ✅ DONE 2026-08-17
*Answers review §2.4, §3.3.7, §11.2(OBI). Frozen engine: untouched. See the Build log.*

- **The case.** We pay for `MODE_FULL` and discard the book. Capture top-of-book so
  every downstream slice has spread + liquidity to work with. This is pure data
  plumbing, not a strategy change.
- **Why take.** Near-zero risk, unlocks 6.8.2 + 6.8.3 + R2 + the OBI idea. No
  subscription change (already MODE_FULL). Cheap.
- **Why NOT / risks.** Depth is **live/provisional** data — it must be labelled as
  such end-to-end and **never enter a backtest or candle** (trading-domain rule 3;
  the no-look-ahead invariant). It is a Redis-cache concern, not a Postgres time-series
  one. Do not over-store: 5-level × 2000 stocks × every tick would bloat — cache
  top-of-book with a TTL, keep full 5-level only for an opt-in research capture.
- **Design.** In `tick_consumer.py`, alongside the LTP extract, read
  `tick["depth"]["buy"][0]` / `["sell"][0]` → best bid/ask/qty. Publish/SET a new
  Redis key `depth:{stock_id}` (JSON: `bid,ask,bid_qty,ask_qty,spread_bps,ts`), TTL
  ~30–60 s, mirroring the `ltp:{stock_id}` contract (import a `DEPTH_KEY`, never
  retype — same rule as `LTP_KEY`). Bounded-queue / drop-oldest overflow policy
  (depth is LTP-class droppable data, not a candle-close event).
- **Touches.** `broker/tick_consumer.py`, a `DEPTH_KEY` constant, a small
  `broker/depth.py` reader (parse-back, like the LTP reader), Redis contract docs.
- **Reviews.** bug-hunter (tick pipeline / async / overflow). perf-auditor (per-tick
  allocation — no heap churn in the hot path; borrow, don't clone).
- **Tests.** consumer SETs `depth:{id}` → reader parses it back (seam test, both
  sides); malformed/empty depth → `None` not crash; TTL present; overflow drops
  oldest depth but never a candle event.
- **§8 backtest?** No — provisional data, never enters scoring/backtests.
- **Effort.** S. **Dependency.** none. **Build first.**

### 6.8.2 — Spread-aware slippage & impact model (paper-fill honesty)
*Answers review §2.4, §3.3.7, §7.2(the legitimate core). Frozen engine: untouched.*

- **The case.** Flat 2 bps is fine for a Nifty large-cap and a lie for a small-cap
  where the spread is 50–100 bps. Every paper fill on an illiquid name currently
  overstates our edge. Replace the constant with a fill model that reads the actual
  book from 6.8.1.
- **Why take.** Makes the 30-day paper clock (the Phase-7 go-live gate) *honest* —
  the single most valuable thing before risking real money. Directly extends the
  shipped honest-fill program.
- **Why NOT / risks.** (1) It **changes paper economics**, so like the 2026-08-01
  slippage-on change it makes pre-/post-change paper P&L non-comparable — it should
  reset (or annotate) the paper clock, your call. (2) Must **fail open**: when depth
  is absent (pre-open, thin name, cache miss) fall back to the flat bps — never block
  a fill on missing microstructure. (3) Keep it a *model*, not a book-walking
  simulator (that is the §7.2 SOR we reject); a spread + size-vs-ADV impact term is
  enough.
- **Design.** In `paper_broker.py`, when `depth:{id}` is present: fill BUY at ask (or
  ask + impact for size beyond top-of-book qty), SELL at bid − impact; impact ≈
  `k · (order_qty / top_qty)` capped, plus half-spread. Config knobs
  `paper_impact_*`, default conservative. Absent depth → current `paper_slippage_bps`
  path unchanged. **Backtests are unaffected** (they run on candle data, never depth),
  so no engine regression — only *live paper fills* change.
- **Touches.** `broker/paper_broker.py`, `core/config.py` (knobs), paper-clock
  annotation, `daily_report.py` (surface realised slippage vs modelled).
- **Reviews.** bug-hunter (fill path, Decimal money — construct from `str`, never
  `float(price)`). quant-verifier (fill-price math, worse-of semantics).
- **Tests.** wide-spread name fills worse than flat-bps; large qty walks past
  top-of-book; **absent depth ⇒ byte-identical to today** (fail-open canary); money
  stays Decimal.
- **§8 backtest?** No (paper-fill only; document the paper-clock reset).
- **Effort.** M. **Dependency.** 6.8.1.

### 6.8.3 — Circuit-band eligibility overlay (the best new idea)
*Answers review §3.1.2. Frozen engine: untouched (a downstream overlay).*

- **The case.** If a long position's stock hits **lower circuit**, there are zero
  buyers — your stop **cannot fill** at any price, software or exchange. Entering a
  name already pinned near its band is a structurally un-exitable trade. NSE/BSE bands
  are 2/5/10/20%. We have **no** awareness of them today (verified: no
  `circuit`/`price_band` logic exists; the only "circuit" is the daily-loss breaker).
- **Why take.** This is the highest-value genuinely-new item in the whole review. It
  is the exact shadow→active shape we just executed for the regime gate, so the
  pattern is proven. It protects paper *and* pre-builds a Phase-7 must-have.
- **Why NOT / risks.** (1) **Data source**: bands aren't in `MODE_FULL` ticks — pull
  `lower_circuit_limit` / `upper_circuit_limit` from Kite `quote()` (throttled REST,
  cache with TTL like LTP; the shared `ThrottledKite` — never raw calls). (2) Some
  bands are wide (20%) and legitimately tradeable — gate on **proximity** (within, say,
  1.5% of a band per the review), not band existence. (3) Must **fail open** — a
  missing quote never blocks an otherwise-valid signal.
- **Design.** New `signals/circuit_guard.py` (mirrors `regime_guard.py`): given a
  signal's entry + direction + the cached band, return `block_reason` when the entry
  sits within `circuit_proximity_pct` of the *adverse* band (long → lower, short →
  upper). Wire into `place_order` next to the regime gate
  (`api/v1/trading.py:142`). `settings.circuit_gate_mode` default **shadow**
  (measure-only), promote to `active` on evidence — identical to the regime-gate
  lifecycle. A daily `circuit-gate-shadow-<date>.md` (like the regime-gate readiness
  banner) shows what it *would* suppress.
- **Touches.** `signals/circuit_guard.py`, a band fetcher on `ThrottledKite`,
  `api/v1/trading.py`, `core/config.py`, `daily_report.py` (readiness banner).
- **Reviews.** quant-verifier (eligibility logic, direction correctness).
  bug-hunter (throttled fetch, cache/TTL, fail-open).
- **Tests.** long near lower band ⇒ shadow-flag; short near upper ⇒ flag; wide band
  far from price ⇒ pass; **absent band ⇒ pass (fail-open canary)**; `active` mode
  rejects, `shadow` mode is a no-op on the order path.
- **§8 backtest?** Behaviour-changing when flipped `active` → yes, a §8-style
  before/after on the suppressed cohort (same bar the regime gate cleared), plus your
  sign-off. Shadow accrual first.
- **Effort.** M. **Dependency.** none (parallel to 6.8.1).

### 6.8.4 — Continuous open-book MTM — close the carried-position gap
*Answers review §6.3.2. Frozen engine: untouched (reporting only).*

- **The case.** `make analysis` already marks open positions and reports open heat
  across days (§3 above). The **one real gap**: the rich per-trade excursion narrative
  (MFE/MAE, chase, timing) is centred on positions *opened that day*; a swing position
  carried for a week gets an EoD mark + heat line but **not** the rolling MFE/MAE
  write-up — so a position quietly bleeding toward its stop over three days isn't
  narrated until the day it closes.
- **Why take.** Small, pure-reporting, high signal-to-noise. It is the honest version
  of §6.3.2 (the reviewers over-claimed the gap; this is the actual sliver).
- **Why NOT / risks.** Low risk. Only caution: keep it read-only and temporally
  bounded (marks from the stored 1m tape under the day's cutoff — the existing
  `daily_report` discipline), no look-ahead into future bars.
- **Design.** Extend `daily_report.build_daily_report` so `still_open` carried
  positions get a rolling MFE/MAE/updated-R block (reuse `signal_outcomes` excursion
  data where the position links to a signal; else derive from the tape). Make the
  weekly `open_mtm_latest` a small day-by-day series rather than latest-only
  (`:830,:905`).
- **Touches.** `services/daily_report.py` only; snapshot-test the new section.
- **Reviews.** quant-verifier (mark math, no look-ahead). test-guardian.
- **Tests.** a 3-day carried position shows rolling MFE/MAE at each day's cutoff;
  weekly series has one entry per trading day; no future-bar leakage.
- **§8 backtest?** No. **Effort.** S. **Dependency.** none.

### 6.8.5 — Corporate-action adjustment of OPEN paper positions
*Answers review §3.3.9 (paper half). Frozen engine: untouched.*

- **The case.** CA detection today is **quarantine-only** — it removes a flagged stock
  from the *selection universe* (`ca_detector.py`, `universe_service.py:35`) but does
  **nothing** to a position you already hold through an ex-date. After a 5:1 split, a
  held position's `avg_entry_price`, `qty`, `current_sl`, `current_tp` are all off by
  5×, so its displayed P&L and its risk (R) are silently wrong.
- **Why take.** A correctness bug for any multi-day hold spanning an ex-date; buildable
  now against paper positions; a clean prerequisite for the Phase-7 live version.
- **Why NOT / risks.** (1) Adjustment ratios must come from the **detected CA event**,
  not guessed from the price gap. (2) Preserve **R exactly** (entry/SL/TP scale by the
  ratio; qty inverse-scales) — this is the whole point. (3) Idempotent (apply once per
  ex-date per position; a re-run must not double-adjust). (4) Reversible migration if a
  new column is needed to record "adjusted for CA event X."
- **Design.** An ex-date worker: for each open position whose stock has a CA event with
  `ex_date == today`, apply the split/bonus ratio to price levels + qty, stamp the
  adjustment. Extend `position_monitor` or a dedicated task.
- **Touches.** `services/` CA-adjust worker, `models/trading.py` (adjustment stamp),
  a Celery beat entry, migration.
- **Reviews.** quant-verifier (R-preservation math). bug-hunter (idempotency, ex-date
  boundary in IST, transaction visibility).
- **Tests.** 5:1 split ⇒ entry/SL/TP ÷5, qty ×5, **R identical to the paisa** before
  and after; re-run is a no-op (idempotency canary); bonus ratio path.
- **§8 backtest?** No (position accounting, not signal generation). **Effort.** M.
  **Dependency.** none.

### 6.8.6 — Silent-feed-outage alarm
*Answers review §2.2 (the reliability half). Frozen engine: untouched.*

- **The case.** The month-long v2-era EOD outage (ingestion frozen 07-02→07-17,
  discovered by accident) is the cautionary tale. We since made EOD tasks self-healing
  (≤21-day catch-up) and adopted a "dead consumer is loud" culture, but there is still
  **no explicit alarm** when `ohlcv_1d` / `fo_bhavcopy` / `fii_dii_daily` go stale — we
  find out by reading §7/§8 of the daily report.
- **Why take.** Cheap insurance against the exact failure that already cost real time
  twice. Turns a silent degradation into a loud one.
- **Why NOT / risks.** Keep it a *staleness* check (max age of the latest row per feed
  vs the NSE trading calendar), not a heavyweight monitor — don't reinvent Prometheus
  (the review's §12.3 metrics stack is over-engineering for a solo platform).
- **Design.** A small check (a beat task or a header in `daily_report`) that computes
  "feed X is N trading days behind" and raises a loud, un-missable line (and/or the
  opt-in notification channel we already have) when N ≥ 1. Trading-calendar aware
  (a weekend is not an outage).
- **Touches.** `services/` staleness check, `daily_report.py` header, optional
  notification.
- **Reviews.** bug-hunter (calendar arithmetic — trading days, IST). test-guardian.
- **Tests.** feed 3 trading days stale ⇒ alarm; weekend gap ⇒ no alarm; all-current ⇒
  quiet.
- **§8 backtest?** No. **Effort.** S. **Dependency.** none.

---

### Research track (higher ceremony — NOT the fast lane)

These touch the frozen engine or an open ruling, so they carry the full ceremony
(oracle regen and/or §8 + sign-off) and should not gate the six paper-safe slices.

**Approved into Phase 6.8 (2026-08-17), each individually gated:** R1 and R2 get an
explicit go/no-go *before* their heavy work starts, informed by what the six paper-safe
slices reveal; **R1 (the only frozen-engine change) is sequenced LAST and must not block
phase close.** This is what keeps "full scope" from meaning "commit to R1's expensive,
uncertain machinery unconditionally."

#### R1 — Anchored VWAP + RVOL as **candidate confluence factors**
*Salvages the legitimate core of review §8 and §11.2.*

- **What we take.** The *ideas* — anchored VWAP (anchored to the 09:15 open tick) and
  RVOL (today only a volume-surge ratio, `indicators/volume.py:28`, not a first-class
  factor) are real momentum signals. They join the **confluence framework as new
  factors**, gated ≥70%, §8-backtested — exactly the PKScreener/MoneyControl
  factor-harvest path already in the backlog.
- **What we REJECT (and why, firmly).** The review's §8/§12 *architecture* — "build a
  separate `IntradayEngine`/`SwingEngine`, lower the gate to 60%, normalise per class,
  scale confidence by ADX ×0.6/×1.2." This **violates hard constraint #2** (confluence
  only, single-indicator signals never, ≥70% gate) and #3 (no look-ahead), and it
  guts the very mechanism (the binary ADX regime gate) we just validated
  out-of-sample in 5/5 walk-forward folds. Lowering the gate to make more signals fire
  is curve-fitting toward volume, not edge — the shadow layer exists precisely so we
  *don't* do that. The intraday trio is `shadow` because walk-forward found it
  **negative**; the fix is better factors inside the gate, not a lower gate.
- **Ceremony.** New factor ⇒ frozen-engine change ⇒ regenerate the Rust oracle
  fixtures in the same commit (rust rules), `§8` regression on the 2y×Nifty50 corpus,
  quant-verifier, **your sign-off**. Shadow-first as a candidate.
- **Effort.** L. **Priority.** after the six paper-safe slices; optional.

#### R2 — Weekly-options spread-width liquidity gate
*Answers review §9.4 / §11.1; resolves an OPEN F&O ruling.*

- **The case.** Weeklies are excluded today via `require_exact_expiry_future` + a flat
  `min_oi` (the open ruling in memory `fo-open-calibration-rulings`). The review's
  better filter — gate on live **bid-ask spread width** `(ask−bid)/ask < 2%` rather
  than OI — is exactly right, and 6.8.1's depth capture makes it possible.
- **Why NOT yet.** It needs option-chain depth (not just equity depth), and the open
  ruling notes a NIFTY weekly's whole chain carries ~1% of the monthly's liquidity, so
  the fill model must not overstate credit. Do it *after* depth capture proves out on
  equities, and re-open the weeklies ruling with the spread gate as the evidence.
- **Effort.** M. **Priority.** research track; ties depth-capture → F&O.

---

### Foundational spike F1 — IN SCOPE (approved 2026-08-17)

#### F1 — `market_cap` data-source decision + writer
*Answers review §14; unblocks the MCE keystone.*

- **The case.** MCE's fundamentals layer is blocked on one thing: `market_cap_cr` has
  **no writer** (verified: column exists `models/stock.py:38`, populated only in
  tests; catalog says "returns no results until populated"). Every fundamental scan
  thresholds on it. §14 finally proposes concrete sources.
- **The verdict on §14's three options** (respecting the prior ruling in
  `COMPETITOR_TOOLS_REVIEW` §4 that Screener.in scraping is "fragile + ToS risk"):
  - **TradingView-screener package** — one request for all NSE fundamentals, but
    unofficial API + ToS grey area + a scraping dependency we'd own. Not for a
    money-path input.
  - **Screener.in CSV export** — highest accuracy for India, but manual/ToS-bound;
    fine as a *one-off seed*, not an automated feed.
  - **yfinance `Ticker.info` weekend cron** — for **`market_cap` specifically** this is
    the pragmatic MVP: low-stakes, slow-decaying, weekly `time.sleep`-paced. It is the
    least-bad of the three *for this one field.*
  - **The real path (already on record):** BSE/NSE **XBRL** quarterly results via
    extending `filings_consumer` (free, authoritative, no ToS risk) for the full
    fundamentals + statements; or a paid API.
- **Decision (2026-08-17): IN SCOPE for 6.8 as a bounded spike.** Deliverable = (a) a
  source decision (yfinance-MVP vs XBRL vs paid) + (b) a working `market_cap_cr` writer
  that populates the field weekly (MVP: yfinance weekend cron, `time.sleep`-paced).
  **Hard boundary — `market_cap_cr` ONLY:** it does **not** build `stock_fundamentals`,
  ratios, or quality scores (those stay MCE, gated on the source decision this spike
  produces). If it grows into the fundamentals table, it has left scope.
- **Why pulled forward (recommended).** It fixes a *current* bug — the screener's
  `market_cap_cr` filter is live and silently returns nothing (no writer, `catalog.py:99`)
  — and de-risks MCE's single biggest unknown (data sourcing) cheaply, while this analysis
  is fresh, so MCE opens unblocked instead of stalling on a data call.
- **Effort.** M (spike). **Priority.** in-scope; the bridge into MCE; independent of
  6.8.1, so it can sequence flexibly.

---

## 6. Deferred to the Market Context Engine (with reasons)

These are real and already the *named phase after Phase 6*. Building them in 6.8
would just be starting MCE early.

- **Earnings blackout (§3.3.8)** — suppress signals N trading days before results.
  Needs a *forward* earnings-calendar source; today's `event_guard` is reactive
  (post-filing) only. Backlog review P1.4.
- **Top-down 200-DMA / India-VIX gate (§3.3.8)** — downweight/suppress longs when
  NIFTY < 200-DMA or VIX high, + sector-RS. Behaviour-changing ⇒ §8. Backlog P2.1.
  *Explicitly NOT a multi-state regime engine.*
- **Fundamental layer + quality scores (§14)** — `stock_fundamentals` table + Altman-Z
  / DuPont / Graham / Ohlson, gated on F1's `market_cap` decision. Authoritative math:
  `VARSITY_REVIEW` §1.1 (the review's `FV = BookValue×10` heuristic stays **rejected**).
- **Per-stock seasonality flag** — the one MCE piece needing no new data; cheap,
  already unblocked.
- **Long/short-vol F&O regime toggle (§9.2)** — debit spreads/backspreads when
  IV-rank < 30. A genuine idea but a whole new F&O strategy family; MCE/F&O-extension,
  §8-gated, paper-first. The current short-vol-only engine is *defensive by design*,
  not a bug.

---

## 7. Deferred to Phase 7 — live-trading hardening (with reasons)

Cannot be *validated* in paper (they only bite on a live order), so they belong with
the live path. Most are already in the PHASES backlog.

- **Exchange-resident GTT / SL-M stops (§2.1, §3.1.1)** — the primary live exit; the
  position monitor becomes a supervisor/reconciler; each trail ratchet becomes a
  MODIFY of the exchange order. Backlog P0.1. *This is the correct fix for §2.1's
  in-memory-SL tail risk — and it is inherently live.*
- **RiskEngine single-gate (§3.2.4)** — consolidate the scattered guards
  (circuit-breaker, regime gate, circuit-band, sizing, SL-cap) behind one pre-order
  gate. **Phase 7 opens with exactly this slice** (test-first, equivalence-pinned) —
  the review's §3.2.4 independently re-derives our own plan.
- **SPAN / exposure margin (§2.5, §3.2.6)** — `kite.order_margins()` pre-trade check.
  Read-only-ish but a live concern; Phase 4 follow-up folded into P7.
- **Freeze-quantity awareness (§3.1.3)** — reject/flag index-option orders over the
  NIFTY 1800 / BANKNIFTY 900 freeze cap. Only meaningful once a live order exists; and
  the **iceberg/slicing engine is REJECTED** outright (backlog: "irrelevant at this
  size" — retail lots rarely approach a freeze cap).
- **Physical-settlement auto-squareoff (§2.5, §3.3.10)** — **note the nuance**: our
  F&O engine is **cash-settled INDEX only** (`fo_suggestions.py:11` "no
  physical-settlement/assignment"), so there is **no current physical-delivery
  exposure**. This becomes relevant *only if* we add **stock** options — a Phase-7
  decision. Documented, not urgent.
- **CA-adjustment of LIVE positions (§3.3.9)** — the live sibling of 6.8.5, gated on
  broker reconciliation. Backlog P1.5.
- **Multi-broker failover (§3.2.5)** — abstract behind an execution-adapter port
  (Angel One / Dhan / Fyers). Real, but the mitigation for the *daily-token* single
  point of failure is the Phase-7 broker-adapter port + reconciliation, per the
  Nautilus study — not a second live broker on day one.
- **Optimistic-update order UX (§6.3)** — a live-order UI concern; no live order to be
  optimistic about yet.

---

## 8. Rejected — with the reason, not a dismissal

Declined because they are the wrong tier for a solo retail platform on Kite, or
contradict a hard constraint, or were already tested-and-rejected. Each is a
considered "no."

| Item (review) | Why not |
|---|---|
| Separate `SwingEngine`/`IntradayEngine` + **60% gate** + per-class normalisation + soft ADX ×0.6/×1.2 (§8, §12.1) | Violates hard constraint #2 (confluence-only, ≥70%). Guts the binary ADX regime gate we validated OOS (5/5 folds). Lowering the gate to fire more signals is curve-fitting, not edge — the salvage is R1 (factors *inside* the gate). |
| Kelly-criterion sizing (§7.1) | Rejected in backlog (Varsity M9): estimation-error-fragile at our sample sizes; simple risk-first + expectancy-informed sizing (Phase 6) chosen. Vol-parity's usable core already exists (`volatility_adjusted_qty`). |
| Monte-Carlo VaR / Expected-Shortfall + portfolio-Greek **auto-hedge** (§7.3) | VaR/ES explicitly rejected in backlog; a **simple total-open-risk + sector caps** number (P7 RiskEngine) is the chosen, honest substitute. Auto-hedging is a prop-desk feature, not retail. |
| TWAP/VWAP/POV smart-order-router, iceberg slicing (§7.2, §3.1.3, §11) | Rejected in backlog: "irrelevant at this size." Execution algos matter at institutional notionals; at retail lots on Kite they add latency and complexity for no benefit. |
| Event-sourcing / CQRS / Kafka/Redpanda (§7.4, §12.3) | Over-engineering. The real risk it targets — crash-recovery/reconciliation — is solved far more cheaply by the Phase-7 broker **reconciliation** slice against Kite's order book. An append-only event bus is a large architectural bet unjustified for a single-user system. |
| kdb+ / ClickHouse / ArcticDB tick DB (§7.5) | TimescaleDB is proven sufficient at our scale — the soaks ran **9.35–9.54M ticks/day, 848k candles, 0 skipped, p99 in budget** (PERFORMANCE.md). A columnar HFT store solves a scale problem we do not have. |
| WebGL/Canvas grids, WASM/Protobuf WS, SharedArrayBuffer "144fps" (§6.2, §6.3, §8.4) | The 60fps budget is **measured and met** — React commit p99 **7.6–8.8ms** vs the 16.7ms frame (PERFORMANCE.md). The premise (GC pauses under thousands of ticks/sec) does not match a ~2000-instrument retail feed. This is a rewrite chasing a problem we measured and don't have. |
| Tauri/Electron desktop wrapper + SharedWorker multi-monitor (§6.3.1) | The stated driver ("6 tabs = 6 WS = broker rate limits") is **wrong**: our WS is to our *own* backend, not Kite, so no broker limit is hit. Real but low-value for a solo user; a desktop shell is a distribution decision, not a trading-edge one. |
| Cross-exchange / calendar / skew **arbitrage** (§11.3) | Requires co-location + sub-ms multi-venue execution — the exact HFT/FIX tier our Nautilus study said *do not copy* for retail Kite. The specific "NSE spot vs MCX futures" example is also wrong (equities don't trade on MCX). |
| Tick-driven swing/intraday **now** (§8.3, §12.1.6) | Premature: the intraday trio is `shadow`/negative and swing doesn't need sub-15m granularity (the review itself concedes 10-min is fine). Move to tick *only if* a profile earns activation — optimising latency for signals we don't trade is effort in the wrong place. |

---

## 9. Sequencing & critical path

```
FOUNDATION            PAPER-HONESTY              EXCHANGE-SAFETY
6.8.1 depth capture ─┬─► 6.8.2 spread slippage    6.8.3 circuit overlay (parallel)
                     └─► R2 weekly spread gate     6.8.5 CA-adjust open pos (parallel)
INDEPENDENT (any order): 6.8.4 open-book gap · 6.8.6 outage alarm
RESEARCH (after the six): R1 VWAP/RVOL factors
OPTIONAL BRIDGE TO MCE: F1 market_cap spike
```

- **Do first:** 6.8.1 (unlocks 6.8.2, R2, the OBI idea) — one small, safe slice.
- **Then the two honesty wins:** 6.8.2 (paper-fill realism) and 6.8.3 (circuit
  safety) — the two that most change what "30 profitable paper days" *means*.
- **Fill in anytime:** 6.8.4, 6.8.5, 6.8.6 — independent, small, low-risk.
- **Research/optional last:** R1, R2, F1 — higher ceremony, don't block the phase.

A tight, high-value MVP of this phase is **6.8.1 + 6.8.2 + 6.8.3** — order-book
honesty + circuit safety — which is what actually de-risks the money.

---

## 10. Decisions — settled 2026-08-17 (+ two left for build-time)

**Settled by the user 2026-08-17 (items 1, 2, 5). Items 3–4 are build-time details that
resolve at their slice:**

1. **Positioning & numbering — SETTLED: a distinct "Phase 6.8"** between Phase 6 close and
   MCE (MCE + Phase 7 numbers unchanged). The slices cohere around one thesis (execution
   honesty) and don't dilute MCE.
2. **`market_cap` (F1) — SETTLED: pulled forward into 6.8 as a bounded spike** (see F1).
   De-risks MCE's data-sourcing unknown *and* fixes the live screener filter that returns
   nothing today. Boundary is hard: `market_cap_cr` ONLY — it does not build
   `stock_fundamentals` (that stays MCE).
5. **Scope — SETTLED: full six paper-safe slices + the research track.** The six are
   unconditional; R1/R2/F1 are in-scope but individually go/no-go-gated, and R1 (the one
   frozen-engine change) is sequenced last and must not block phase close. The MVP order
   still holds — **6.8.1–6.8.3 ship first** as the honesty core.
3. **(build-time) Circuit-band data (6.8.3).** Confirm we pull bands from Kite `quote()` via
   the shared throttled client (my assumption), and the proximity threshold (review says
   1.5%). Resolve when 6.8.3 starts.
4. **(build-time) Paper-clock treatment (6.8.2).** When spread-aware fills land they change
   paper economics — reset the 30-day paper clock (cleanest, comparable) or annotate the
   discontinuity? **Your call when 6.8.2 lands.**

---

## 11. Definition of done (phase)

`make check` green · each slice ships with the tests named above · reversible
migrations · shadow-first for any behaviour-changing overlay (circuit gate) with a
daily readiness banner before any `active` flip · `§8` before promoting the circuit
gate or R1 factors, with your sign-off · relevant agent reviews clean · the
**doc-sync ritual** run at each slice (PHASES top block + this tracker + CHANGELOG +
CLAUDE.md + memory) · a `docs/phases/phase-06.8-*.md` closure report at the gate.

**Guiding line:** Phase 6.8 buys **honesty** (paper P&L that tells the truth on
illiquid names and un-fillable stops) and **safety** (guards built and measured
before they guard real money) — so that when Phase 7 wires the broker, there is
nothing left to discover about the exchange, only about the order API.

---

## Build log

- **2026-08-17 — 6.8.1 DONE (order-book depth capture).** New `app/broker/depth.py`
  (`Depth` dataclass + `spread`/`mid`/`spread_bps`; `extract_top_of_book`; `serialize_depth`/
  `parse_depth`; `write_depth`; `get_live_depth` mirroring `get_live_ltp`). Redis KEY
  `depth:{stock_id}` (JSON, Decimal-string prices, 60 s TTL); new `depth_capture_enabled`
  flag (default on). PROVISIONAL — no DB column, no migration, never in a candle/backtest.
  **26 tests** (extraction edge cases, Decimal-exact round trip, Redis seam + TTL, consumer +
  live-worker integration); ruff + mypy strict clean; 184 tests green across the changed
  modules and their importers.
  - **bug-hunter → 1 MEDIUM fixed + regression-tested:** `extract_top_of_book` sat *outside*
    the fail-open try and could raise on a truthy-but-non-list `depth["buy"]` (a dict →
    `KeyError: 0`), which would drop the whole tick batch and roll back earlier candle
    upserts. Fixed at the source (guard the indexing) *and* by wrapping the call.
  - **perf-auditor → 1 HIGH (correctness) fixed — the load-bearing lesson:** the first cut
    wired depth ONLY into `tick_consumer.py`, which is the **dormant v1 consumer** (`main.py`
    forbids its auto-start; it runs only via an admin button). **The soak-proven production
    live path is `live_worker.py`** (`python -m app.broker.live_worker` / `make live-worker`),
    a separate process that owns the tables. Depth would therefore never populate in
    production and 6.8.2 would read an empty key. **Fix:** wired depth into `live_worker`'s
    `_ffi_batch` (harvest behind the same accept/stale gate as the FFI tuple) + `_publish_ltp`
    (the depth SET is **folded into the existing per-batch pipeline — one round trip, never a
    per-tick set**), so the p99 ≤ 50 ms budget is untouched. Kept the v1 wiring too (parity;
    fail-open). **Remember: `live_worker.py` is the live path, `tick_consumer.py` is dormant
    v1** — a feature wired only into the v1 consumer is inert in production.
  - **Pending:** a live-session smoke — confirm `depth:{stock_id}` actually populates from real
    Kite `MODE_FULL` ticks with the live worker running (needs a market session + token). The
    seams are proven against a real Redis + the execute-faithful pipeline spy + a real
    `tradecore.LiveBook`, but real-tick population is unverified until the next session.

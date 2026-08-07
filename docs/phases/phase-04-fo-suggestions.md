# Phase 4 slice 4.3 — F&O option-selling suggestion engine (v1 FINALIZED)

> **Status: v1 built & calibrated 2026-08-06** (`app/services/fo_suggestions.py`,
> `GET /fo/suggestions`, 23 tests, quant-verifier PASS). The user approved the
> conservative recommendations below; the numeric defaults live in `SellRules`
> and are still **forward-tested on paper** before any live use. Suggestions
> only — never auto-trades.
>
> **Two clinical corrections made during the build (important):**
> 1. **Expectancy is REPORT-ONLY, not a gate.** With a risk-neutral (breakeven
>    N(d2)) POP, a fairly-priced credit spread's expectancy is ≈0 by
>    construction — so gating `expectancy > 0` would reject everything. The edge
>    is the **volatility risk premium** (selling IV that exceeds later realized
>    vol), which the **IV-rank gate proxies** and **forward-testing validates**;
>    it is NOT provable from prices. (Reported expectancy uses a conservative,
>    slightly negative-biased two-point estimator — a mildly negative value on a
>    fair spread is expected.)
> 2. **Hard vetoes fail CLOSED.** The India-VIX regime veto stands down not only
>    on a confirmed high-vol regime but also when the regime can't be assessed
>    (no VIX data) — a blind safety gate must not pass, because a vol spike
>    lifts IV-rank (so that gate passes) leaving VIX as the only backstop.
>
> The remaining **follow-ups** (still open) are in §7; the calibratable knobs are
> §4 (now the shipped defaults, not placeholders).

## 1. Scope & principles

- **Option-*selling* candidates** (defined-risk, credit structures) + a thin
  **futures-directional** hook. This slice focuses on the selling engine; the
  futures-directional side reuses the frozen confluence engine + an OI-confirm
  gate and is sketched in §6.
- **Deterministic, rules-based.** No ML. Everything is derived from data we
  already compute in 4.1/4.2: chain (OI/LTP), IV & Greeks (`tradecore`),
  IV-rank, PCR, max-pain, basis, India-VIX regime.
- **Suggestions, never auto-trades.** The engine emits ranked candidates with
  full economics; a human (or, later, the paper/live layer behind the go-live
  gate) decides. This mirrors the Market-Context-Engine principle: context
  sizes and gates; it never originates a fill on its own.
- **Defined-risk only** in v1: bull put spread, bear call spread, iron condor.
  No naked shorts (margin + tail risk). Cash-secured / ratio / calendars are
  out of scope pending calibration.
- **Forward-tested, not backtested.** Recorded chain history is thin, and POP
  is a forward claim — the UI must label realized-vs-POP tracking as
  forward-tested (that dashboard is Phase 5/6, not here).

## 2. Where it sits

```
chain + OI/LTP (4.1) ┐
IV & Greeks (4.2, tradecore) ┤
IV-rank (4.2b) ┤→  gates + strike selection  →  build defined-risk structures
PCR / max-pain / basis (4.1) ┤     (§4 rules)          →  economics (§3 math)
India-VIX regime (4.1) ┘                               →  rank → ranked candidates
```

New module `app/services/fo_suggestions.py`; endpoint `GET /fo/suggestions`.
The rules live in one `SellRules` dataclass — **that is the calibration
surface**; the rest is model-independent.

## 3. Payoff math (settled — calibration-independent)

For a credit spread with short strike `Ks`, long (protection) strike `Kl`,
net credit `C = premium(short) − premium(long) > 0`, width `W = |Ks − Kl|`:

| Structure | Legs | Max profit | Max loss | Breakeven | Profit zone |
|---|---|---|---|---|---|
| **Bull put** | sell put Ks, buy put Kl (Kl<Ks) | `C` | `W − C` | `Ks − C` | `S_T ≥ Ks − C` |
| **Bear call** | sell call Ks, buy call Kh (Kh>Ks) | `C` | `W − C` | `Ks + C` | `S_T ≤ Ks + C` |
| **Iron condor** | bull put + bear call (both OTM) | `C_put + C_call` | `max(Wput, Wcall) − Ctotal` | `Ksput − Ctotal` (low), `Kscall + Ctotal` (high) | between breakevens |

- **Margin estimate (v1):** defined-risk → margin ≈ **max loss**. Return-on-margin
  `RoM = C / max_loss`. (The plan's Kite-margins-API refinement is a follow-up;
  max-loss is a safe upper bound for a defined-risk spread.)
- **POP (probability of profit) — SHIPPED = breakeven-exact:** risk-neutral
  `P(finish on the profitable side of the breakeven)` = `N(d2)` at the breakeven
  (Black-76 on the future), computed in `breakeven_pop`. The delta proxy
  (`1 − |Δ(short)|`) remains a fallback when a strike's IV can't be priced.
- **Expectancy:** `POP·C − (1−POP)·max_loss`, **reported not gated** (see the
  correction in the status banner — risk-neutral expectancy is ≈0 by
  construction; the edge is the VRP, gated via IV-rank + forward-testing).
- **Fills (conservative):** each leg is haircut by `max(premium·slippage_frac,
  min_slippage)` — sold legs down, bought legs up — so the credit is never
  optimistic. A per-leg absolute floor (default 1 pt) prevents narrow index
  spreads from being over-slipped by a naive %-of-premium. (Real per-leg bid/ask
  from the intraday snapshots is the calibration refinement.)

## 4. Selection rules — SHIPPED v1 DEFAULTS (`SellRules`, calibratable)

The v1 defaults (user-approved 2026-08-06). Conservative; forward-tested before
live. Tighten/loosen in `SellRules`.

| Rule | v1 default (`SellRules`) | Rationale |
|---|---|---|
| Universe | **index only** {NIFTY, BANKNIFTY, FINNIFTY} | cash-settled → no physical settlement / assignment |
| IV-rank ≥ | **50** (`iv_rank_min`) | sell rich vol only (VRP proxy) |
| Short-strike | **\|Δ\| ≈ 0.16 ± 0.06** (`short_delta_target/_band`) | ≈1 SD OTM |
| Spread width | **1 strike** (`width_strikes`) | defined risk; wider = calibrate |
| DTE window | **20–45 days** (`dte_min/_max`) | theta window, off the gamma zone |
| Min OI / leg | **500** (`min_oi`) | liquidity floor |
| VIX regime | **skip if high OR unknown** (`skip_high_vix`) | hard veto, **fail-closed** |
| Reward floor | **credit ≥ 0.30·width** (`min_credit_to_width`) | no high-POP "pennies" |
| POP floor | **0.65** (`min_pop`) | breakeven-exact; reject low-probability |
| Fills | **max(0.5%·prem, 1 pt)/leg** (`slippage_frac`,`min_slippage`) | conservative bid/ask haircut |
| Exits (metadata) | **TP 50% · SL 2×credit · 21 DTE** | mechanical; execution is Phase-6/7 |
| Rank by | **RoM × POP** | `rank_candidates` |

**Note on the default's selectivity:** 0.16Δ + a 0.30 reward-floor on a 1-strike
spread is *deliberately* very selective — far-OTM narrow spreads rarely clear a
30% credit/width, so the engine often returns **nothing** (a safe "no trade"
stance). Sell nearer (~0.30Δ) or wider for more credit/width if you want more
signals. **Sizing** (2% account-risk against defined-risk max-loss) is applied
at the trade layer, not in this suggestions slice.

## 5. Output contract

```python
SpreadCandidate = {
  structure: "bull_put" | "bear_call" | "iron_condor",
  legs: [{action: sell|buy, option_type: CE|PE, strike, premium}],
  net_credit, max_profit, max_loss, width,
  breakevens: [..],           # 1 for a vertical, 2 for a condor
  pop, margin_est, return_on_margin,
  short_delta, iv_rank, dte, expiry,
  gates_passed: [...], rationale: "IV-rank 63, 0.16Δ short, above max-pain",
}
```
Ranked best-first; empty list is a valid answer (nothing passes the gates).

## 6. Futures-directional hook (sketch — not built in the strawman)

Reuse the **frozen confluence engine** on the underlying + an **OI-confirmation
gate** (price up + OI up = long build-up; price up + OI down = short covering,
weaker). Emits a directional futures idea with the same sizing discipline.
Deferred until the selling engine is calibrated — flagging so it isn't
forgotten. Touching the confluence framework needs your sign-off (it's frozen).

## 7. Calibration decisions (v1) + remaining follow-ups

**Answered / shipped in v1** (2026-08-06):
1. **Structures** — bull put / bear call / iron condor only (defined-risk). No
   naked / cash-secured / ratio / calendars in v1.
2. **Short-strike** — by delta, ≈0.16 ± 0.06.
3. **IV gate** — IV-rank ≥ 50.
4. **Premium source** — chain close with a conservative per-leg haircut (bid/ask
   proxy); model price is the fallback for IV when a quote won't invert.
5. **POP** — breakeven-exact `N(d2)`; min POP 0.65. Expectancy report-only (VRP).
6. **DTE / expiry** — 20–45 days, monthly index (weeklies excluded in v1).
7. **Vetoes** — index-only universe; VIX high/unknown fail-closed; per-leg OI.
8. **Exits** — TP 50% / SL 2× credit / 21-DTE (metadata).

**Still open (deliberate follow-ups, NOT in v1):**
- **Direction tilt (Q8):** v1 emits neutral condor + both verticals and ranks;
  gating the directional tilt on the **frozen confluence engine** (on the index)
  is a follow-up (needs sign-off — the engine is frozen).
- **Event/ban gate (Q9):** beyond VIX, the full event calendar + F&O-ban veto is
  the **deferred Market Context Engine** (post-Phase-6) — this is exactly its
  hook. See [[market-context-engine-deferred]].
- **Sizing (Q6):** the 2%-of-capital-on-max-loss rule is applied at the trade
  layer, not this suggestions slice.
- **Margin:** Kite SPAN-margin API refinement (v1 uses defined-risk max-loss).
- **Realized-vs-POP forward-validation dashboard:** Phase 6.
- **Premium source refinement:** true per-leg bid/ask from the intraday snapshots
  (v1 uses close + haircut).

## 8. What shipped

`app/services/fo_suggestions.py` (structures + payoff math + breakeven POP +
expectancy + `SellRules` + `suggest_option_sells` orchestration wired to 4.1/4.2
+ `tradecore`), `GET /fo/suggestions`, `tests/test_fo_suggestions.py` (23),
quant-verifier PASS. Next: (Phase 5) chain-ladder UI + strategy cards; (Phase 6)
forward-validation dashboard; the direction-tilt + event-gate follow-ups above.


## 9. Amendment (2026-08-07) — expiry selection dead-ended, and a look-ahead

Two defects found while closing the Phase-5 gate. The first was logged there as
"imminent" (`phase-05-ui-overhaul.md` §8) and turned out to be already tripped;
the second was found by the quant-verifier pass that the same §8 recorded as
owed. Neither changes any calibrated number.

### 9.1 The expiry walk (the logged bug)

`_pick_expiry` returned the first option expiry whose DTE fell in
`[dte_min, dte_max]`. `suggest_option_sells` then priced it with
`fa.futures_basis`, which needs a futures row with the **same expiry** and
returns `None` otherwise — at which point the whole engine did `return []`.

Index options expire **weekly**; index futures only **monthly** (§7.6 excludes
weeklies from v1 for exactly the liquidity reasons quantified in 9.3). So
whenever a weekly sat in *front* of an in-window monthly, the engine stopped on
the weekly, failed to price it, and returned an empty list —
**indistinguishable from "no candidate cleared the gates"**, which this document
teaches you to read as normal.

Real NIFTY bhavcopy, latest recorded day 2026-08-05 (spot 24,624.65). Futures
existed for exactly three expiries — 08-25, 09-29, 10-27:

| Option expiry | DTE | in [20,45] | same-expiry future? |
|---|---:|:--:|:--:|
| 2026-08-11 | 6 | no | no |
| 2026-08-18 | 13 | no | no |
| **2026-08-25** | **20** | **YES → picked** | **YES (monthly)** |
| 2026-09-01 | 27 | yes | no (weekly) |
| 2026-09-08 | 34 | yes | no (weekly) |
| 2026-09-29 | 55 | no | yes (monthly) |

The monthly sat at DTE exactly **20** — the floor of the window — so 08-05 was
the *last* day it would be picked, not a safe margin. From the next bhavcopy day
the first in-window expiry is the 09-01 weekly and the engine goes silent.

Simulated over the real expiry calendar, the 42 **weekdays** 2026-08-06 → 10-02
(weekday count, not NSE-calendar trading days — this is a descriptive
measurement, not a validity window, so holidays would shift all three rows
together):

| Selection policy | days producing |
|---|---:|
| OLD — first in-window expiry must itself own a future | **7 / 42** |
| **Walk the window, monthly-only (shipped)** | **33 / 42** |
| Walk the window, weeklies allowed (flag off) | 42 / 42 |

**The shipped default still goes dark on 9 of those 42 days** — 2026-08-06 →
08-14 (seven consecutive weekdays) and 09-10 → 09-11 — because no monthly sits
in the 20–45 DTE window then. That is a *policy* consequence of monthly-only,
not a bug, and it is exactly what the new `no ELIGIBLE in-window expiry` warning
exists to make legible: **the warning, not the empty list, is the signal.**

**Fix:** `_pick_expiry` now returns `(day, expiry, ChainForward)` and walks the
in-window expiries, taking the first **eligible** one, where eligibility is
"prices via `fa.forward_for_expiry`" plus the new `require_exact_expiry_future`
flag. That recovers 26 of the 35 lost days **without changing a single
calibrated number**. When nothing in the window is eligible it logs that the
empty result is a pricing/policy outcome, not a gate rejection — closing the
ambiguity that made this invisible.

### 9.2 The look-ahead (found by quant-verifier)

`suggest_option_sells` called `fa.load_chain(db, symbol, expiry, source="eod")`
with **no `as_of`**. `_chain_from_bhavcopy` then takes `max(trade_date)` for that
expiry, **unbounded** — while `day`, the forward and `t` all came from
`_pick_expiry`'s `trade_date <= as_of`. Any historical `as_of` therefore priced a
**later** chain against an **earlier** forward.

Demonstrated: with a chain seeded on 2026-08-03 and another on 08-04 (spot
gapped +5%, IV halved), `suggest_option_sells(as_of=2026-08-03)` built its
candidates from **08-04's** premia — net credit 38.51 instead of 21.94.

Inert on the live endpoint, which never passes `as_of` — but the Phase-6
realized-vs-POP forward-validation dashboard is *precisely* a historical-`as_of`
consumer, so this would have silently corrupted the evidence used to validate
the engine. Violates `.claude/rules/trading-domain.md` §"No look-ahead".

**Fix:** the chain is bound to `day`, the same day the forward and `t` come from.

### 9.3 Weeklies stay excluded — and `min_oi` is NOT what excludes them

An earlier draft of this amendment let weeklies through and argued the
`min_oi = 500` per-leg floor made them safe. **That was wrong, and the real data
says so.** NIFTY, 2026-08-05:

| Expiry | legs | legs ≥ 500 OI | total chain OI |
|---|---:|---:|---:|
| 2026-08-25 (monthly) | 242 | 197 | **95,937,855** |
| 2026-09-01 (weekly) | 210 | 68 | 921,960 |
| 2026-09-08 (weekly) | 142 | **3** | **3,705** |
| 2026-09-29 (monthly) | 246 | 150 | 37,059,615 |

The 09-01 weekly's *entire chain* carries ~1% of the 08-25 monthly's OI; the
09-08 weekly totals 3,705 across 142 legs, of which three clear the floor — on
daily volumes of 43 / 39 / 14 contracts. A **per-leg** floor of 500 cannot tell a
live chain from a dead one, and the fill haircut (`slippage_frac` 0.005,
`min_slippage` 1.0) was fitted to monthly quotes: on a 1%-OI chain the true
half-spread exceeds 1 point, so `net_credit` would be **overstated**, inflating
`min_credit_to_width`, `return_on_margin` and the RoM×POP ranking.

So §7.6 ("weeklies excluded in v1") stands, and it is now **enforced in code**
rather than emerging by accident from which expiry happens to own a futures row:

```python
require_exact_expiry_future: bool = True   # SellRules
```

Index futures are monthly, so "has a same-expiry future" *is* the monthly test.

**Open question for the user — a real ruling, not a formality.** Flipping this
flag to `False` takes the engine from 33/42 to 42/42 producing days. It should
not be flipped until there is a **chain-level** liquidity gate to go with it
(e.g. total chain OI as a fraction of the front monthly's) and a fill model
calibrated on weekly quotes — otherwise the extra 9 days are exactly the days
whose credit is most overstated. Recommended order: per-leg bid/ask from the
intraday snapshots (§7 follow-up) → chain-level gate → then revisit.

### 9.4 Why this is NOT a recalibration

`SellRules` were calibrated against an exact-expiry-future forward, which is why
the fix was deferred at the Phase-5 gate. With `require_exact_expiry_future`
defaulting to True the engine prices against **only** exact-expiry futures, and
`forward_for_expiry` short-circuits to that future's close **verbatim** on that
path. The forward is the same number, to the Decimal.

Verified on the real dev DB rather than argued:

| Expiry | DTE | old `futures_basis` | new forward | source |
|---|---:|---|---|---|
| 2026-08-25 (monthly) | 20 | `24647.7000` | `24647.7000` | `fut_exact` |
| 2026-09-01 (weekly) | 27 | `None` → engine `[]` | `24695.8967` | `fut_carry_implied` |

The carry-implied column is what the flag currently withholds. Hand-checked:
with the 09-29 future at 24,770.00, `b = ln(24770/24624.65)/(55/365) = 0.039053`
and `F(09-01) = 24624.65·e^(0.039053·27/365) = 24695.89` ✓. Because the query
requires `expiry_date >= expiry`, this always **interpolates** in log-space
between `(0, spot)` and `(T_fut, F_fut)` — never extrapolates — so
`spot < F < F_fut` is a structural property, not a fixture accident. The algebra
is also day-count invariant (`ln(F/S)/T_fut × T_opt` cancels the /365).

**One behavioural difference from the old code, and it is an improvement.**
`futures_basis` filtered `trade_date <= as_of`, so a missing same-expiry futures
row on `day` silently priced `day`'s option closes against an **earlier day's**
futures close. `forward_for_expiry` is pinned to `day` with an equality and
refuses instead. Not reachable on 2026-08-05 (all three FUT rows present).

### 9.5 Robustness: one unpriced future no longer kills the front chain

`forward_for_expiry` took the nearest future on/after the option with `limit(1)`
and returned `None` if that row had no settlement price — so a single bad
recorder row killed the forward, and therefore every Greek, for the whole front
chain even with a perfectly good future one expiry further out. It now takes the
nearest **priced** future among the first few candidates, exact-expiry
short-circuit still first.

### 9.6 Provenance

`_pick_expiry` returns the whole `ChainForward`, and a non-exact forward is
disclosed in every candidate's `rationale`. This matters because §6c of the
Phase-5 report measured the carry-implied forward's error as **consistently
positive** ~0.12–0.19%, not zero-mean: at F=24,625, t=22/365, iv=0.14 a +0.12%
bias moves bull-put POP 0.7675 → 0.7781 and bear-call 0.7723 → 0.7616 — ~1.1pp,
enough to cross the hard `min_pop = 0.65` gate. A carry-implied suggestion must
never present itself as one priced off a traded future.

### 9.7 Known, unchanged, and deliberately not touched here

- **`dte_min = 20 < time_stop_dte = 21`** — a candidate selected at DTE 20–21 is
  born already satisfying its own mechanical time stop. Pre-existing; the walk
  actually **reduces** the exposure rather than leaving it flat. Measured
  08-06 → 10-02: the old path picked DTE ≤ 21 on **2 of its 7** producing days
  (29%), the new one on **2 of 33** (6%) — because it now reaches the whole
  20–43 DTE span instead of only the monthly's brief pass through the window's
  floor. Changing `dte_min` remains a calibration decision left to the user.
- **Gate/price day misalignment (pre-existing).** Gate 1 (`iv_rank`) and Gate 2
  (`vix_regime`) are bounded by the requested `as_of` — no look-ahead — but are
  not *aligned* to the day the chain is priced on, and are not freshness-checked.
  So `suggest_option_sells(as_of=2026-09-30)` against a database whose last
  bhavcopy is 08-05 judges the vol gates on ~8-week-old data and says nothing.
  Live condition, not hypothetical: EOD ingestion missed 2026-08-06 entirely.
  Made **loud** (a warning when `ivr.as_of != day`) rather than fatal, because
  turning staleness into a hard rejection changes gate semantics and is a
  calibration decision. **Open for a user ruling:** hard-reject on stale gates?
- **Per-leg bid/ask** (§7 follow-up) remains the right fix for the fill model;
  until it lands, `min_slippage = 1.0` should not be assumed conservative on
  anything but a liquid monthly chain.
- **`forward_source` is not yet a typed field** on `SpreadCandidate` /
  `SuggestionOut` the way it is on `ChainOut` — it rides in `rationale` text.
  Dormant while weeklies are excluded; promote it to a real field if the §9.3
  ruling ever flips the flag, so consumers can filter on it.

### 9.8 Tests

`tests/test_fo_suggestions.py` 23 → **33**. A fixture reproduces the real NSE
topology — a tradeable weekly chain sitting in front of a monthly that owns the
only futures row, with a **non-zero carry** so the exact and carry-implied
branches yield different numbers (a zero-carry fixture would let a calibration
guard pass even with the short-circuit deleted). Then:

- a **canary** that `futures_basis` genuinely cannot price the leading weekly;
- **the walk regression** — targeted-revert-proven to fail on the original
  dead-on-first-expiry logic;
- **weeklies excluded by default**, and selectable **only** when the flag is
  flipped — the escape hatch is a named knob, not an emergent property;
- the carry-implied forward bounded strictly inside `(spot, F_fut)` and matching
  a hand-computed 50098.07;
- carry-implied provenance present in the rationale, and absent on the exact path;
- **the look-ahead canary** — targeted-revert-proven: on the unbound chain the
  engine builds from the later day's premia (credit 38.51 vs 21.94);
- an unpriced nearest future falling through to a priced one —
  targeted-revert-proven against `limit(1)`;
- no priced future anywhere → `None`, never a guessed forward;
- a **calibration guard** asserting both the `fut_exact` **branch** and
  Decimal-equality with `futures_basis(...).fut_close`. The branch assertion is
  the load-bearing half: for a *same-expiry* future `t_fut == t_opt`, so the
  carry formula is an algebraic identity (`S·e^((ln(F/S)/t)·t) == F`) and the
  numbers agree either way. The corollary is a stronger invariance claim than
  the one this section started with — bypassing the short-circuit entirely is
  accurate to ~5e-11, which quantization to `Decimal("0.0001")` absorbs.

### 9.9 Review record

quant-verifier round 1 → **FAIL**: the look-ahead in 9.2, and a first draft of
this amendment that overrode §7.6 to admit weeklies and justified it with a
`min_oi` claim the OI data refutes (9.3). Round 2 → **PASS-WITH-NOTES**, with all
three blockers independently revert-proven and the 7/33/42 calendar numbers
reproduced from a scratch rebuild of the expiry calendar. Notes folded in above:
the corrected reason for the calibration guard (9.8), the DTE-distribution
correction and the gate-staleness hole (9.7), weekday-vs-trading-day wording and
the nine dark days (9.1). Not verified in either round: real per-leg bid/ask on
weeklies — the recorder stores closes, not quotes, so 9.3's fill-model argument
rests on OI and volume, not a measured spread.

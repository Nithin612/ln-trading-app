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

# Phase 4 slice 4.3 — F&O suggestion engine (DESIGN DRAFT / strawman)

> **Status: DRAFT for calibration.** This is option **B** from the 2026-07-30
> discussion — a concrete strawman to react to, *not* a finished spec. Every
> numeric threshold here is a **conservative placeholder** to be replaced by the
> user's masterclass option rules. Structure and payoff math are settled; the
> **rules** (§4) and the **open questions** (§7) are what we calibrate together.

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
- **POP (probability of profit):** two options, both computable from what we have:
  1. **Delta proxy (v1 default):** `POP ≈ 1 − |Δ(short strike)|` — the trader
     heuristic (a 0.16-delta short ≈ 84% POP). Uses `tradecore.option_greeks`.
     Ignores the credit's breakeven shift, so it is *slightly conservative* for
     credit spreads.
  2. **Breakeven-exact (refinement):** risk-neutral `P(finish on the profitable
     side of the breakeven)` = `N(d2)` at the breakeven strike (Black-76 on the
     future). More accurate; needs a tiny `prob_itm` FFI or a Python normal-CDF.
     **Open question §7.5** — which POP do you want as the headline number?

Premiums come from the chain LTP when liquid, else the `tradecore` model price
at the strike's IV — **open question §7.4** (LTP vs model, and mid-vs-last).

## 4. Selection rules — CONSERVATIVE PLACEHOLDERS (⚠ calibrate)

These are the `SellRules` defaults. **None are your rules yet** — they are
defensible conservative starting points so the strawman runs end-to-end.

| Rule | Placeholder | Rationale / to calibrate |
|---|---|---|
| Sell only when IV-rank ≥ | **50** | sell rich vol; you may prefer an absolute IV floor too |
| Short-strike selection | **\|Δ\| ≈ 0.16** (±0.04 band) | ≈1 SD OTM; you may select by % OTM or max-pain distance |
| Spread width | **1–2 strikes** | balance credit vs max-loss |
| DTE window | **14–45 days** | theta sweet spot; NSE weeklies (Tue) vs monthly? |
| Min OI / leg | **500** | liquidity floor; per-underlying? |
| VIX regime = high | **skip** (or halve) | risk-off; §7.9 which events hard-block |
| Expiry week | **skip** | pin/gamma risk; calibrate |
| Direction bias | max-pain + (optional) confluence | bull put if under-lying > max-pain & not bearish; bear call if <; iron condor if range-bound (near max-pain, low ADX) |
| Min POP | **0.70** | reject low-probability credits |
| Rank by | **RoM × POP** | or credit/width, or POP-first |
| Max risk / trade | **reuse account risk% (2%)** | defined-risk max-loss ≤ risk budget; §7.6 |

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

## 7. OPEN QUESTIONS FOR CALIBRATION (the point of this doc)

1. **Structures** — bull put / bear call / iron condor only, or also
   ratio spreads, broken-wing, calendars, cash-secured puts?
2. **Short-strike selection** — by delta (what target?), % OTM, max-pain
   distance, or S/R levels?
3. **IV gate** — IV-rank threshold, and/or an absolute IV floor? Per underlying?
4. **Premium source** — chain LTP (last vs mid) when liquid, model price when not?
5. **POP** — delta proxy or breakeven-exact `N(d2)`? Minimum POP?
6. **Sizing** — reuse the account 2% risk rule against defined-risk max-loss, or
   a fixed max-loss per trade, or margin-based?
7. **DTE / expiry** — window, and weekly (NSE Tue / BSE Thu) vs monthly?
8. **Direction bias** — from the confluence engine, PCR, max-pain, or a manual
   regime switch? When do you prefer a neutral condor vs a directional vertical?
9. **Regime / event gates** — which events hard-block selling (RBI, results,
   F&O ban)? This is where the deferred Market Context Engine plugs in.
10. **Exits / adjustments** — roll at X% credit captured, stop at Y× credit loss?
    (Likely Phase-6/live, but shapes the candidate metadata.)

## 8. Build plan once calibrated

`SellRules` ← your answers → finalize `suggest_option_sells` orchestration →
`GET /fo/suggestions` → tests on real recorded chains → quant-verifier →
(Phase 5) chain-ladder UI + strategy cards → (Phase 6) forward-validation
(POP vs realized) dashboard.

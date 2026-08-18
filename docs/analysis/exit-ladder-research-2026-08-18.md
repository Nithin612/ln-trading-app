# Exit-ladder research — profit-booking rules replayed on real trades (2026-08-18)

**Status: PARKED for discussion after the entry-quality filter is built.** This records
the analysis we did on profit-booking / exit rules so we can resume it with the numbers
intact. No code was changed as a result of this yet.

## The question

The user observed: *trades that crossed ~₹800–1,000 in profit, then reversed to a loss,
give back too much.* Two proposed profit-booking rules:

1. **Hard ₹500 floor** — once peak profit crosses ~₹800–1,000, set the stop to lock ~₹500
   (a ratcheting seal above it). "Either way we minimise the loss."
2. **Net-₹100 floor** — a tighter variant: once past ₹800–1,000, guarantee at least **₹100
   NET** (after brokerage + GST).
3. Also: "choose 1R **or** the ladder, whichever is higher profit."

**Key finding up front:** all three ideas are already *built* in
`app/trading/profit_lock.py::absolute_ladder_stop` — a rupee-denominated ladder that takes
the tightest-of {original risk SL, breakeven@`breakeven_inr`, seal `peak − giveback_inr`
above `trail_start_inr`}, one-way. The user re-derived the existing mechanism; the real
question is only **what to set the thresholds to** (and the current ones — BE ₹2,000, seal
peak−₹1,000 above ₹3,000 — arm too late, so most trades never reach them: the known
FIX_PLAN P2 / profit-protection A/B finding of ~₹21k given back).

## Method — replay over the real 1-minute tape

We replayed candidate exit policies over the **actual 1m tape of trades that were really
taken** (reusing `services/profit_lock_shadow.py`'s `_load_bars` + `_replay` + the
`absolute_ladder_stop` / `layered_ratchet_stop` step functions, netting Zerodha charges via
`fees.roundtrip_charges`). This is the right data for an *exit* question — a synthetic 2y
fresh-signal backtest can't help (we don't keep 1m tape that far back, and it would be
different trades).

**Clean sample = 18 trades** after excluding: my 2026-08-17 manual closes (hand-picked exit
prices, not natural), known off-tape / pre-market-exit-bug trades, and one mis-sized outlier
(PNCINFRA, original stop −₹6,779 ≈ 3× the risk budget). Filter: natural exit
(`sl_hit`/`tp_hit`), on-tape, and **peak profit ≥ ₹800** (the population the rule targets).

Policies (all rupee amounts are position-level):

| Policy | breakeven | trail_start | giveback | atr_k |
|---|--:|--:|--:|--:|
| **Current** (today's default) | ₹2,000 | ₹3,000 | ₹1,000 | 2.0 |
| **Lock ₹500** (idea #1) | ₹800 | ₹1,000 | ₹500 | 0 |
| **Net ₹100** (idea #2) | ₹350 | ₹700 | ₹250 | 0 |
| **Early-BE** (hybrid: arm early, trail wide) | ₹800 | ₹1,500 | ₹1,000 | 2.0 |
| **Higher-of-1R-or-₹500** | max(`layered_ratchet_stop` 1R ladder, Lock ₹500) | | | |

## Results

| Policy | Total net (18) | Avg/trade | Capture % of peak | Losing trades |
|---|--:|--:|--:|--:|
| Actual (live monitor) | ₹10,386 | ₹577 | — | 5 |
| **Current ladder** | **₹19,871** | ₹1,104 | 34% | 5 |
| Lock ₹500 | ₹16,772 | ₹932 | **40%** | **3** |
| **Net ₹100** | **₹4,585** | ₹255 | 12% | **8** |
| Early-BE hybrid | ₹16,984 | ₹944 | 36% | 8 |
| Higher-of-1R-or-₹500 | ₹16,772 | ₹932 | 40% | 3 |
| Peak (theoretical ceiling) | ₹41,508 | ₹2,306 | 100% | 0 |

Lock ₹500 vs Current: **better on 6 trades, worse on 9.**

Exemplars (net ₹, Current → Lock ₹500):
- **Rescued** (peaked then crashed to a loss under Current): TNPL −2,092 → **+984** · KOTHARIPET −89 → **+1,420** · PCBL −2,737 → **+445** · NATCOPHARM −414 → **+358**.
- **Clipped** (genuine runner cut short): DMCC +1,450 → **−69** · GLOBAL +2,406 → **+1,558** · WONDERLA +1,244 → **+942**.

## Verdicts

- **Net-₹100 floor — REJECT.** Worst of everything (₹4,585; 8 of 18 still lost). A ~₹350-gross
  guarantee exits winners on the first wiggle after they turn green — locks pennies, misses
  everything, and is so busy exiting it doesn't even prevent the losses.
- **Hard ₹500 floor — a risk dial, not a profit booster.** vs Current: **−16% total P&L** but
  **best capture rate (40%) and fewest blow-ups (3 vs 5).** It does exactly what the user
  wanted on the giveback-to-loss trades, at the cost of clipping genuine runners. It buys
  "less pain," not "more money."
- **Current ladder makes the most total** — it lets trends run (wide seal + ATR room), with
  more downside variance.
- **Early-BE hybrid (arm breakeven at ₹800, trail wide) did NOT clearly win** — "arm early +
  trail wide" is not a free lunch on this sample.
- **The one change the data supports:** arm the **breakeven (no-loss) rung earlier — ₹800
  instead of ₹2,000** (`profit_lock_breakeven_inr`). It cut blow-ups (3 vs 5) at little cost,
  it's a single config knob, no engine change, and it's already FIX_PLAN P2.

## The bigger point — entry, not exit

Peak-capture is only **25–48%** across every policy, because **most of these trades peaked and
then reversed** — a weak-*entry* symptom (SRTL is the archetype: a near-single-factor
RSI-divergence signal on an illiquid ₹39 micro-cap, sized to 2,666 shares so a ₹0.50
gap-through-stop became a ₹3.5k loss). Better exits recover a third of the peak; **better
entries would raise the ceiling AND stop the reversals.** Exit-tuning is second-order.

## Caveats (why we do NOT hardcode a floor off this)

1. **Sample is tiny (18 natural trades)** — cannot reliably distinguish a 16% difference.
2. **Replay is intrabar-conservative** (assumes the low is hit before the high within a 1m
   bar) — understates every ladder.
3. Sample pollution (manual closes, off-tape bugs, mis-sizing) was stripped, but the residue
   is small-n.

## Decisions / next steps

1. **Reject Net-₹100.** Do NOT ship a tight net floor.
2. **Bundle the safe knob:** move `profit_lock_breakeven_inr` 2,000 → ~800 (early breakeven),
   run it as a forward A/B (the `profit_lock_shadow` / `GET /trading/shadow-compare` infra
   already A/Bs this). Do NOT ship the hard ₹500 seal — it clips winners.
3. **Build the entry-quality filter FIRST** (the first-order lever): a factor-diversity floor
   (kill near-single-factor "80% but one indicator" signals) + a low-price/illiquidity sizing
   guard (kill the huge-qty-on-cheap-stock gap amplification). Downstream overlay, frozen
   engine untouched, shadow-first — the `regime_guard`/`circuit_guard` pattern.
4. **Re-run this replay on 50–100+ natural trades** once accrued, before committing any exit
   threshold. This is the argument for NOT starting a fresh 30-day paper clock on today's rules.

## Reproducibility

The replay harness (throwaway) loaded each closed paper position's 1m tape via
`profit_lock_shadow._load_bars`, stepped it through each policy's `_Step` with `_replay`, and
netted charges with `roundtrip_charges`. Policy params are in the table above. To formalise:
turn it into a repeatable report (a `services/` function + a `docs/analysis/exit-ladder-<date>.md`
sidecar) so it re-runs as trades accrue — deferred until there's a sample worth trusting.

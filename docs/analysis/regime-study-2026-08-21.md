# Market-regime study — 2026-08-21

_Read-only research over 575 classified sessions (2024-04-25 → 2026-08-21). Each day is put in a level×breadth quadrant AS-OF that day (200-DMA level × short-term breadth / 20-DMA, the reviewed `summarize_regime` classifier — no classifier look-ahead), then FORWARD 5/10/20-session NIFTY return that followed is measured. This tests the two-window finding: does **below-200-DMA + STRONG breadth (Window A)** actually beat **below + WEAK breadth (Window B)**? A study looks forward by design; the live engine is untouched._

## 1. Forward returns by regime quadrant (the thesis test)

| quadrant | days | fwd-5 | fwd-10 | fwd-20 | fwd-20 win% | avg VIX |
|---|--:|--:|--:|--:|--:|--:|
| above+strong | 208 | -0.07% | -0.00% | +0.03% | 61% | 13.7 |
| above+weak | 164 | +0.19% | +0.19% | +0.12% | 57% | 13.5 |
| below+strong | 73 | -0.40% | -0.57% | +0.21% | 59% | 14.7 |
| below+weak | 130 | +0.47% | +0.87% | +1.33% | 61% | 16.6 |

**Thesis check: does NOT confirm the thesis on this sample.** Below-200-DMA & STRONG breadth → fwd-20 +0.21% (n=64 of 73 days); below & WEAK breadth → fwd-20 +1.33% (n=119 of 130 days). The 200-DMA level alone lumps both together; breadth separates them.

> **⚠ Fragility:** the arithmetic is verified correct, but the forward-20 windows overlap heavily — the below+weak edge rests on ~2 drawdown episodes (one still open), NOT the labelled ~independent observations. See the robustness re-estimates below. And 3y is ONE bull cycle where every dip recovered — a 'buy the dip' prior would be dangerous in a structural bear (falling knife). We are currently in the deepest/longest below-200-DMA episode (still open) — exactly the 'bull dip or regime change?' case the study cannot resolve.

### Robustness — does the gap survive the overlap?

- **Non-overlapping subsample** (days ≥20 apart): below+weak +0.51% (n=8) vs below+strong +4.08% (n=2) → gap **-3.57%** (vs the naive ~6× — collapses, as expected).
- **Moving-block bootstrap** (1000 replicates, block=20): mean gap +1.09%, 95% CI [-1.36%, +3.36%], **P(below-weak > below-strong) = 83%**.
- **Verdict:** if the CI straddles 0 (or P is near 50%), the direction is NOT statistically established — treat as a weak prior, not a rule. Re-run as data grows.

## 2. Below-200-DMA episodes (how bad, how long, did it recover)

| start | end | sessions | depth (trough vs cross) | recovered | avg VIX |
|---|---|--:|--:|:--:|--:|
| 2024-11-14 | 2024-11-21 | 4 | -0.78% | yes | 15.4 |
| 2024-12-20 | 2025-01-01 | 8 | +0.00% | yes | 14.0 |
| 2025-01-06 | 2025-04-17 | 69 | -6.49% | yes | 15.1 |
| 2025-04-25 | 2025-04-25 | 1 | +0.00% | yes | 17.2 |
| 2025-05-09 | 2025-05-09 | 1 | +0.00% | yes | 21.6 |
| 2026-01-23 | 2026-01-23 | 1 | +0.00% | yes | 14.2 |
| 2026-02-02 | 2026-02-02 | 1 | +0.00% | yes | 13.9 |
| 2026-02-27 | 2026-08-21 | 118 | -11.31% | STILL BELOW | 16.5 |

_7/8 episodes recovered above the 200-DMA within data; median duration 1 sessions, deepest trough -11.3%._

## 3. Index / cap dispersion (avg fwd-20 by NIFTY quadrant)

| quadrant | NIFTY50 | BANKNIFTY | FINNIFTY |
|---|--:|--:|--:|
| above+strong | +0.03% | -0.01% | +0.03% |
| above+weak | +0.12% | +0.46% | +0.61% |
| below+strong | +0.21% | +0.50% | +0.28% |
| below+weak | +1.33% | +2.51% | +2.83% |

## 4. Playbook — what to do in each regime (data-driven)

| regime quadrant | fwd-20 | action |
|---|--:|---|
| below+weak | +1.33% | FAVOUR longs (regime tailwind) |
| below+strong | +0.21% | NEUTRAL / selective — normal size, tighter entry discipline |
| above+weak | +0.12% | NEUTRAL / selective — normal size, tighter entry discipline |
| above+strong | +0.03% | NEUTRAL / selective — normal size, tighter entry discipline |

## 5. Money-flow (FII/DII) — DATA GAP

_FII/DII recorder holds only 38 sessions (2026-07-17 → 2026-08-21) — far too little for a multi-year regime-flow study. Backfill FII/DII history to unlock the flow angle._

> **Honest limits:** this study measures PRICE / BREADTH / VIX behaviour and how regimes recovered — not *cause*. Negative-news / management / holder-issue attribution needs a news & fundamentals history we do not have (the MCE news layer helps FORWARD, not back). FII/DII flow — the one causal-ish factor — has too little history to use yet (see above). And the sample is one market cycle (~3y): treat the playbook as a prior, re-run as data grows.


# Post-news drift — does a big move keep going? (2026-09-07)

**The honest version of *check before scrapping*.** The slice-6 feasibility check
tested `corporate_filings` against the *veto* design and found its preconditions
absent. That answered a narrower question than the one that matters: **news as a
directional signal** — bank bad news dragging BANKNIFTY, a POSH complaint taking TCS
down for a week, a defence-policy push lifting the sector.

⭐ **And it needs no news feed.** A large abrupt move on heavy volume **is the
footprint of news**, so the drift is measurable from bars we already hold. If drift
exists, a feed becomes worth buying — you would know what for. If it does not, no
feed would have helped.

**Event definition:** |1-day move| ≥ **6.0%** on volume ≥ **1.5×** its
20-day average, in names with ≥ ₹1.0 Cr median daily traded value.
**29,352 events** — 22,560 up, 6,792 down.

⚠ **A move is not a news event.** Earnings, index rebalances, block deals, sector
rotations and plain volatility all jump. This measures the *population of large
moves*, a superset of news — so absence here makes presence in news alone unlikely,
while presence would point at which subset to identify next.

### UP jumps — does strength continue, or give back?

**22,560 events on 773 dates.** Continuation would be a momentum long; reversion would be a fade.

| horizon | mean fwd return | median | % positive | 90% interval (day-block) |
|---|--:|--:|--:|---|
| t+1 ⭐ | **+0.355%** | -0.142% | 48% | [+0.233, +0.476]% |
| t+3 | **+0.100%** | -0.568% | 46% | [-0.107, +0.303]% |
| t+5 | **+0.242%** | -0.608% | 46% | [-0.038, +0.530]% |
| t+10 ⭐ | **+0.551%** | -0.820% | 47% | [+0.145, +0.961]% |

### DOWN jumps — the TCS-shaped case

**6,792 events on 733 dates.** **Continuation here is the short opportunity** the instruction described.

| horizon | mean fwd return | median | % positive | 90% interval (day-block) |
|---|--:|--:|--:|---|
| t+1 | **+0.209%** | +0.118% | 51% | [-0.396, +0.812]% |
| t+3 | **+0.806%** | +0.325% | 52% | [-0.276, +1.869]% |
| t+5 | **+1.172%** | +0.403% | 52% | [-0.171, +2.516]% |
| t+10 ⭐ | **+1.846%** | +0.297% | 51% | [+0.008, +3.658]% |

## Verdict

**Drift IS detectable at some horizons:**

- **UP jumps, t+1: +0.355%**, interval [+0.233, +0.476]% — **excludes zero**
- **UP jumps, t+10: +0.551%**, interval [+0.145, +0.961]% — **excludes zero**
- **DOWN jumps, t+10: +1.846%**, interval [+0.008, +3.658]% — **excludes zero**

### ⚠⚠ But read the MEDIAN before believing any of it

- **UP t+1**: mean +0.355% but median -0.142%, only 48% positive — **the mean is a right tail, not a typical trade**
- **UP t+3**: mean +0.100% but median -0.568%, only 46% positive — **the mean is a right tail, not a typical trade**
- **UP t+5**: mean +0.242% but median -0.608%, only 46% positive — **the mean is a right tail, not a typical trade**
- **UP t+10**: mean +0.551% but median -0.820%, only 47% positive — **the mean is a right tail, not a typical trade**

**A positive mean with a negative median and under half the trades positive
is a lottery-ticket distribution, not an edge.** You would lose on most
trades and rely on rare large winners to carry it — which needs far more
capital and patience than a ₹1 lakh book has, and blows up under a stop-loss
that cuts the very tail you are depending on.

This is the market-regime lesson repeating: its would-block set had a −₹302
mean and a **+₹200 trimmed mean** — trimming reversed the sign. Mean alone
would have recommended the gate.

⚠ **Detectable is not tradeable.** Before this becomes a strategy:

1. **Costs.** Our round-trip is 22–62 bps plus ₹15.34 DP on a delivery sell. A
   drift smaller than that is a loss with extra steps.
2. **Timeliness.** We would be acting on the CLOSE of the jump day at the
   earliest — the intraday move is already gone. The table's t+1 onward is
   exactly what a next-day entry could have captured, which is the honest
   comparison.
3. **Shorting.** A DOWN-jump continuation trade needs a short, and cash-equity
   delivery shorts are not possible — that is futures, i.e. Phase 7+.
4. **Trial count.** 8 horizon/direction cells were examined. Any survivor must
   be charged for that before being believed.

**⇒ The next step, if pursued, is a cost-and-timing-aware version** — same
events, entry at the next open, costs applied, held to each horizon. That turns
a statistical drift into a P&L question.

### ⭐ And note which direction actually held up

**DOWN jumps BOUNCE, they do not continue down.** Mean *and* median are positive
at t+3/t+5/t+10, with over half the events positive — the most internally
consistent result in this study. **That is the opposite of the shorting
hypothesis**: on the population of large adverse moves, buying the fall beat
shorting it.

The TCS-style narrative (bad news, down for a week) is a real *story*; it is not
what the population of 6,792 down-jumps does on average. That gap between a
vivid case and the base rate is the whole reason to measure.

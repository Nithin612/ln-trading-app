# Factor sweep — 17 configurations, 20-day horizon (2026-09-07)

**Trying many possibilities, and charging for having tried.** Volume ratios across
four lookbacks, every SMA pair, price against three references, and 52-week
position — evaluated against forward returns over the full daily history.

- observations: **52,830** on **39** non-overlapping dates
- universe floor: ≥ ₹1.0 Cr median daily traded value
- **configurations tried: 17** ← the number the winner is charged for

## ⚠ The three guards, and why each is needed

1. **Non-overlapping dates.** A 20-day forward return on consecutive days
   overlaps 95% with its neighbour. Sampling every
   20th date removes that; not doing so inflates significance ~√20×.
2. **Day-block bootstrap.** Every stock on one date shares that date's market move,
   so the independent unit is the DATE, not the row (the CAS-2 lesson).
3. **Trial count = 17.** A sweep this wide WILL produce a good-looking winner
   by chance — `momentum ×1.5` was best-of-12 and its ranking did not survive a
   larger corpus. The winner is judged against that count, not against zero.

## Ranked by |Q5 − Q1| spread

| configuration | n | IC | Q1 | Q5 | spread | monotone | 90% interval |
|---|--:|--:|--:|--:|--:|:-:|---|
| `sma50_over_sma200` | 52,830 | -0.0161 | +1.602% | +0.233% | **-1.369%** | 3/4 | [-4.491, +1.569]% |
| `sma20_over_sma200` | 52,830 | -0.0187 | +1.785% | +0.504% | **-1.281%** | 3/4 | [-5.101, +1.696]% |
| `close_over_sma200` | 52,830 | -0.0174 | +1.761% | +0.623% | **-1.139%** | 3/4 | [-4.668, +1.808]% |
| `sma20_over_sma150` | 52,830 | -0.0181 | +1.748% | +0.630% | **-1.118%** | 3/4 | [-4.978, +1.939]% |
| `sma50_over_sma150` | 52,830 | -0.0160 | +1.548% | +0.442% | **-1.106%** | 3/4 | [-4.571, +1.853]% |
| `sma20_over_sma50` | 52,830 | -0.0221 | +1.917% | +0.861% | **-1.055%** | 2/4 | [-4.490, +2.259]% |
| `close_over_sma150` | 52,830 | -0.0171 | +1.669% | +0.658% | **-1.011%** | 3/4 | — |
| `rvol_5` | 52,830 | -0.0243 | +1.569% | +0.580% | **-0.990%** | 3/4 | — |
| `close_over_vwap20` | 52,830 | +0.0330 | +0.454% | +1.428% | **+0.974%** | 3/4 | — |
| `sma150_over_sma200` | 52,830 | -0.0216 | +1.065% | +0.126% | **-0.939%** | 2/4 | — |
| `rvol_10` | 52,830 | -0.0130 | +1.171% | +0.477% | **-0.694%** | 2/4 | — |
| `close_over_sma50` | 52,830 | -0.0075 | +1.349% | +0.850% | **-0.499%** | 3/4 | — |
| `close_over_sma20` | 52,830 | +0.0129 | +0.687% | +1.162% | **+0.475%** | 2/4 | — |
| `pos_52w` | 52,830 | +0.0036 | +1.640% | +1.199% | **-0.441%** | 2/4 | — |
| `rvol_20` | 52,830 | +0.0052 | +0.850% | +0.703% | **-0.147%** | 2/4 | — |
| `close_over_vwap50` | 52,830 | +0.0129 | +0.992% | +1.102% | **+0.110%** | 3/4 | — |
| `rvol_50` | 52,830 | +0.0111 | +0.657% | +0.657% | **-0.000%** | 2/4 | — |

## Verdict

⛔ **Nothing in the top 6 has an interval excluding zero.**

Across 17 configurations, no parameterisation of volume ratio, SMA
relationship, price-vs-reference or 52-week position separates forward returns
in a way that survives a day-block bootstrap. **That is a real answer**: the
period choice in `volume_factor` is not where the problem is, and neither is the
SMA pair.

## ⚠ What this cannot tell you

- **Forward return is not our P&L.** No costs, no stops, no position sizing. A
  feature can rank forward returns and still lose money once the 22–62 bps
  round-trip and a stop-loss are applied.
- **One regime.** The whole history is ~3.2 years of a single broad regime.
- **Cross-sectional, unconditional.** This asks 'does the feature rank returns',
  not 'does it improve OUR confluence', which is a different and harder question.

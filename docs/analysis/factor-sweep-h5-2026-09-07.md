# Factor sweep — 17 configurations, 5-day horizon (2026-09-07)

**Trying many possibilities, and charging for having tried.** Volume ratios across
four lookbacks, every SMA pair, price against three references, and 52-week
position — evaluated against forward returns over the full daily history.

- observations: **212,129** on **156** non-overlapping dates
- universe floor: ≥ ₹1.0 Cr median daily traded value
- **configurations tried: 17** ← the number the winner is charged for

## ⚠ The three guards, and why each is needed

1. **Non-overlapping dates.** A 5-day forward return on consecutive days
   overlaps 80% with its neighbour. Sampling every
   5th date removes that; not doing so inflates significance ~√5×.
2. **Day-block bootstrap.** Every stock on one date shares that date's market move,
   so the independent unit is the DATE, not the row (the CAS-2 lesson).
3. **Trial count = 17.** A sweep this wide WILL produce a good-looking winner
   by chance — `momentum ×1.5` was best-of-12 and its ranking did not survive a
   larger corpus. The winner is judged against that count, not against zero.

## Ranked by |Q5 − Q1| spread

| configuration | n | IC | Q1 | Q5 | spread | monotone | 90% interval |
|---|--:|--:|--:|--:|--:|:-:|---|
| `close_over_sma20` | 212,129 | -0.0224 | +0.535% | +0.222% | **-0.313%** | 2/4 | [-1.030, +0.405]% |
| `sma150_over_sma200` | 212,129 | -0.0065 | +0.308% | -0.000% | **-0.309%** | 3/4 | [-0.885, +0.269]% |
| `sma50_over_sma200` | 212,129 | +0.0067 | +0.392% | +0.109% | **-0.283%** | 3/4 | [-1.034, +0.499]% |
| `close_over_vwap20` | 212,129 | -0.0145 | +0.505% | +0.240% | **-0.265%** | 2/4 | [-0.995, +0.443]% |
| `close_over_sma200` | 212,129 | +0.0000 | +0.463% | +0.206% | **-0.257%** | 2/4 | [-1.100, +0.490]% |
| `rvol_50` | 212,129 | +0.0158 | -0.004% | +0.250% | **+0.253%** | 2/4 | [-0.062, +0.594]% |
| `close_over_sma150` | 212,129 | +0.0006 | +0.439% | +0.240% | **-0.200%** | 2/4 | — |
| `sma20_over_sma200` | 212,129 | +0.0091 | +0.384% | +0.188% | **-0.196%** | 3/4 | — |
| `sma50_over_sma150` | 212,129 | +0.0093 | +0.333% | +0.140% | **-0.193%** | 3/4 | — |
| `rvol_5` | 212,129 | +0.0151 | +0.151% | +0.317% | **+0.166%** | 3/4 | — |
| `close_over_sma50` | 212,129 | -0.0074 | +0.422% | +0.263% | **-0.159%** | 2/4 | — |
| `sma20_over_sma150` | 212,129 | +0.0111 | +0.343% | +0.219% | **-0.124%** | 3/4 | — |
| `rvol_20` | 212,129 | +0.0113 | +0.145% | +0.253% | **+0.108%** | 3/4 | — |
| `close_over_vwap50` | 212,129 | +0.0011 | +0.361% | +0.268% | **-0.093%** | 2/4 | — |
| `rvol_10` | 212,129 | +0.0037 | +0.251% | +0.204% | **-0.048%** | 2/4 | — |
| `pos_52w` | 212,129 | +0.0093 | +0.388% | +0.341% | **-0.047%** | 3/4 | — |
| `sma20_over_sma50` | 212,129 | +0.0094 | +0.244% | +0.276% | **+0.032%** | 3/4 | — |

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

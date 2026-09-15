# Sector/index relative-strength shadow (live signals) — 2026-09-06

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (559 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 227 | 33 | ₹-5,712 | ₹-173 | 48% |
| eligible (RS in favour of the side) | 332 | 62 | ₹-6,040 | ₹-97 | 50% |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ⏳ NOT READY — VETOED by a shared readiness guard — [tail] dropping the worst 4 of 33 would-block trades moves its mean from ₹-173 to ₹293 — the negative sign is tail-driven, not a property of the cohort. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).


### Evidence of record — sector-RS gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 227 | 33 | ₹-173 | ₹-4 | ₹293 | 48% |
| eligible (kept) | 332 | 62 | ₹-97 | ₹-7 | ₹411 | 50% |

**Shared guards:**
- ✅ `side_proxy` — the partition is not explained by side alone
- 🚫 `tail` — dropping the worst 4 of 33 would-block trades moves its mean from ₹-173 to ₹293 — the negative sign is tail-driven, not a property of the cohort
- ✅ `win_rate` — would-block win rate 48% ≤ eligible 50%

- **eligible set (the book a flip would leave you holding) — deflated Sharpe bar:** ⏳ does NOT clear · **n=62, and MORE DATA CANNOT RESCUE IT (not ahead of the bar)**
  - observed Sharpe -0.041 does not exceed the 20-trial benchmark +0.241 — more data cannot rescue it; the candidate is not ahead
  - n=62 · mean -97.4195 · sd 2386.1659 · **Sharpe -0.041** · skew +0.02 · kurtosis 3.96
  - P(true Sharpe > 0) = 37.5% · **after deflating for 20 trials: 1.4%** (bar 95%)
  - ⚠ trials are treated as INDEPENDENT; ours overlap (same book, shared cohorts), so the true deflation is WORSE than shown — this number is optimistic.
- **eligible set — block bootstrap (2,000 resamples, blocks of 4):** ⏳ the sign does NOT survive resampling
  - observed Sharpe **-0.041** · 90% interval [**-0.241**, +0.144] · median -0.048
  - the Sharpe comes out ≤ 0 in **66%** of plausible histories
  - ⚠ prices SAMPLING uncertainty only, not selection (that is DSR's job), and assumes the series was passed in chronological order.
- ⚠ **the `n/20` bar above is a process convention, not the statistical requirement** — the implied sample on the deflated-Sharpe line is what decides. Reaching 20 resolved trades is not evidence of anything on its own.

## Per-entry context (each committed signal's sector/index RS)

| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |
|---|---|---|---|--:|---|--:|
| 2026-09-04 | AAATECH | SHORT | NIFTY50 | +2.51% | 🚫 would-block | open/none |
| 2026-09-04 | PRESTIGE | SHORT | NIFTY50 | +2.88% | 🚫 would-block | open/none |
| 2026-09-04 | CASTROLIND | LONG | NIFTY50 | +1.80% | ✅ eligible | open/none |
| 2026-09-04 | HILINFRA | SHORT | NIFTY50 | +1.49% | 🚫 would-block | open/none |
| 2026-09-04 | KIRLOSBROS | SHORT | NIFTY50 | +0.65% | 🚫 would-block | open/none |
| 2026-09-04 | LALPATHLAB | SHORT | NIFTY50 | -0.06% | ✅ eligible | open/none |
| 2026-09-04 | CASTROLIND | LONG | NIFTY50 | +1.80% | ✅ eligible | open/none |
| 2026-09-03 | CYBERMEDIA | LONG | NIFTY50 | +50.01% | ✅ eligible | open/none |
| 2026-09-03 | TCS | SHORT | NIFTY50 | +0.87% | 🚫 would-block | open/none |
| 2026-09-03 | MASKINVEST | SHORT | NIFTY50 | -9.80% | ✅ eligible | open/none |
| 2026-09-03 | MANAKCOAT | SHORT | NIFTY50 | +9.05% | 🚫 would-block | open/none |
| 2026-09-03 | CYBERMEDIA | LONG | NIFTY50 | +50.01% | ✅ eligible | open/none |
| 2026-09-03 | TCS | SHORT | NIFTY50 | +0.87% | 🚫 would-block | open/none |
| 2026-09-02 | BCPL | SHORT | NIFTY50 | +0.02% | 🚫 would-block | open/none |
| 2026-09-01 | FUSION | SHORT | NIFTY50 | -4.56% | ✅ eligible | open/none |
| 2026-09-01 | AMBIKCO | SHORT | NIFTY50 | -6.39% | ✅ eligible | open/none |
| 2026-09-01 | MUKANDLTD | SHORT | NIFTY50 | -2.10% | ✅ eligible | open/none |
| 2026-09-01 | HEXT | SHORT | NIFTY50 | +1.58% | 🚫 would-block | open/none |
| 2026-09-01 | MAHLOG | SHORT | NIFTY50 | -5.76% | ✅ eligible | open/none |
| 2026-08-31 | NOCIL | LONG | NIFTY50 | +1.31% | ✅ eligible | open/none |
| 2026-08-31 | SUPREMEIND | SHORT | NIFTY50 | +3.62% | 🚫 would-block | open/none |
| 2026-08-31 | SHRINGARMS | SHORT | NIFTY50 | -1.70% | ✅ eligible | open/none |
| 2026-08-31 | GRPLTD | SHORT | NIFTY50 | -0.31% | ✅ eligible | open/none |
| 2026-08-31 | PNGJL | SHORT | NIFTY50 | -8.47% | ✅ eligible | open/none |
| 2026-08-31 | NOCIL | LONG | NIFTY50 | +1.31% | ✅ eligible | open/none |
| 2026-08-28 | PIDILITIND | SHORT | NIFTY50 | +1.98% | 🚫 would-block | open/none |
| 2026-08-27 | ASHIMASYN | LONG | NIFTY50 | +3.88% | ✅ eligible | open/none |
| 2026-08-27 | IMAGICAA | LONG | NIFTY50 | +33.29% | ✅ eligible | open/none |
| 2026-08-27 | VRLLOG | LONG | NIFTY50 | +14.36% | ✅ eligible | open/none |
| 2026-08-27 | DELHIVERY | LONG | NIFTY50 | +0.44% | ✅ eligible | open/none |
| 2026-08-27 | NEPHROPLUS | LONG | NIFTY50 | +1.27% | ✅ eligible | open/none |
| 2026-08-27 | BLIL | LONG | NIFTY50 | +4.09% | ✅ eligible | open/none |
| 2026-08-27 | DELHIVERY | LONG | NIFTY50 | +0.44% | ✅ eligible | open/none |
| 2026-08-27 | VRLLOG | LONG | NIFTY50 | +14.36% | ✅ eligible | open/none |
| 2026-08-27 | WALCHANNAG | LONG | NIFTY50 | -2.77% | 🚫 would-block | open/none |
| 2026-08-27 | LICHSGFIN | LONG | FINNIFTY | -1.11% | 🚫 would-block | open/none |
| 2026-08-27 | CCL | LONG | NIFTY50 | -4.39% | 🚫 would-block | open/none |
| 2026-08-27 | ADANIPORTS | LONG | NIFTY50 | +3.93% | ✅ eligible | open/none |
| 2026-08-27 | MSPL | LONG | NIFTY50 | -3.12% | 🚫 would-block | open/none |
| 2026-08-27 | PREMIERENE | LONG | NIFTY50 | +2.69% | ✅ eligible | open/none |
| 2026-08-27 | SINCLAIR | LONG | NIFTY50 | +9.28% | ✅ eligible | open/none |
| 2026-08-27 | WENDT | LONG | NIFTY50 | +4.29% | ✅ eligible | open/none |
| 2026-08-27 | IMAGICAA | LONG | NIFTY50 | +33.29% | ✅ eligible | open/none |
| 2026-08-27 | PICCADIL | LONG | NIFTY50 | -8.19% | 🚫 would-block | open/none |
| 2026-08-27 | ASHIMASYN | LONG | NIFTY50 | +3.88% | ✅ eligible | open/none |
| 2026-08-27 | ANTELOPUS | LONG | NIFTY50 | -1.13% | 🚫 would-block | open/none |
| 2026-08-27 | BETA | LONG | NIFTY50 | +0.51% | ✅ eligible | open/none |
| 2026-08-27 | KKCL | LONG | NIFTY50 | -0.54% | 🚫 would-block | open/none |
| 2026-08-27 | RELIGARE | LONG | NIFTY50 | -6.28% | 🚫 would-block | open/none |
| 2026-08-26 | IDBI | LONG | NIFTY50 | +12.78% | ✅ eligible | ₹-2,331 |

_… 509 more assessable signals not shown._


# Market-regime shadow (live signals) — 2026-09-06

_Read-only. The market-regime overlay recomputed over the tradeable signal cohort since 2026-07-19 (559 signals), broad-market (NIFTY50) trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when the market regime is AGAINST its side — a long while NIFTY50 is below its 200-DMA, a short while above. 'no market data' = fewer than 200 index sessions yet (fails open live; needs the deep index backfill). VIX is reported per entry but never gates. A would-block set net-negative AND worse than the with-regime set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (regime against the side) | 409 | 62 | ₹-11,530 | ₹-186 | 52% |
| with-regime (eligible) | 150 | 33 | ₹-221 | ₹-7 | 45% |
| no market data (< 200-DMA history) | 0 | 0 | — | — | — |

**market-regime flip readiness:** ⏳ NOT READY — VETOED by a shared readiness guard — [side_proxy] the partition is a PROXY FOR SIDE — 100% of would-block entries are LONG and 100% of eligible are SHORT. This evidence measures long-vs-short performance over the window, not the gate, so it cannot certify a flip however good the headline looks; [tail] would-block MEDIAN is ₹81 (positive) while its mean is ₹-186 — the negative mean is carried by a few large losses, so the gate would suppress a cohort that is TYPICALLY profitable; [win_rate] would-block wins MORE often than eligible (52% vs 45%) — the gate is suppressing the higher-win-rate cohort. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `market_regime_gate_mode=shadow`).


### Evidence of record — market-regime gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 409 | 62 | ₹-186 | ₹81 | ₹361 | 52% |
| eligible (kept) | 150 | 33 | ₹-7 | ₹-59 | ₹346 | 45% |

**Shared guards:**
- 🚫 `side_proxy` — the partition is a PROXY FOR SIDE — 100% of would-block entries are LONG and 100% of eligible are SHORT. This evidence measures long-vs-short performance over the window, not the gate, so it cannot certify a flip however good the headline looks
- 🚫 `tail` — would-block MEDIAN is ₹81 (positive) while its mean is ₹-186 — the negative mean is carried by a few large losses, so the gate would suppress a cohort that is TYPICALLY profitable
- 🚫 `win_rate` — would-block wins MORE often than eligible (52% vs 45%) — the gate is suppressing the higher-win-rate cohort

- **eligible set (the book a flip would leave you holding) — deflated Sharpe bar:** ⏳ does NOT clear · **n=33, and MORE DATA CANNOT RESCUE IT (not ahead of the bar)**
  - observed Sharpe -0.004 does not exceed the 20-trial benchmark +0.331 — more data cannot rescue it; the candidate is not ahead
  - n=33 · mean -6.7094 · sd 1670.3765 · **Sharpe -0.004** · skew +0.06 · kurtosis 2.21
  - P(true Sharpe > 0) = 49.1% · **after deflating for 20 trials: 2.9%** (bar 95%)
  - ⚠ trials are treated as INDEPENDENT; ours overlap (same book, shared cohorts), so the true deflation is WORSE than shown — this number is optimistic.
- **eligible set — block bootstrap (2,000 resamples, blocks of 4):** ⏳ the sign does NOT survive resampling
  - observed Sharpe **-0.004** · 90% interval [**-0.420**, +0.363] · median -0.030
  - the Sharpe comes out ≤ 0 in **55%** of plausible histories
  - ⚠ prices SAMPLING uncertainty only, not selection (that is DSR's job), and assumes the series was passed in chronological order.
- ⚠ **the `n/20` bar above is a process convention, not the statistical requirement** — the implied sample on the deflated-Sharpe line is what decides. Reaching 20 resolved trades is not evidence of anything on its own.

## Per-entry context (each committed signal's market regime)

| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |
|---|---|---|--:|--:|---|--:|
| 2026-09-04 | AAATECH | SHORT | -2.90% | 10.68 | ✅ with-regime | open/none |
| 2026-09-04 | PRESTIGE | SHORT | -2.90% | 10.68 | ✅ with-regime | open/none |
| 2026-09-04 | CASTROLIND | LONG | -2.90% | 10.68 | 🚫 would-block | open/none |
| 2026-09-04 | HILINFRA | SHORT | -2.90% | 10.68 | ✅ with-regime | open/none |
| 2026-09-04 | KIRLOSBROS | SHORT | -2.90% | 10.68 | ✅ with-regime | open/none |
| 2026-09-04 | LALPATHLAB | SHORT | -2.90% | 10.68 | ✅ with-regime | open/none |
| 2026-09-04 | CASTROLIND | LONG | -2.90% | 10.68 | 🚫 would-block | open/none |
| 2026-09-03 | CYBERMEDIA | LONG | -3.04% | 11.34 | 🚫 would-block | open/none |
| 2026-09-03 | TCS | SHORT | -3.04% | 11.34 | ✅ with-regime | open/none |
| 2026-09-03 | MASKINVEST | SHORT | -3.04% | 11.34 | ✅ with-regime | open/none |
| 2026-09-03 | MANAKCOAT | SHORT | -3.04% | 11.34 | ✅ with-regime | open/none |
| 2026-09-03 | CYBERMEDIA | LONG | -3.04% | 11.34 | 🚫 would-block | open/none |
| 2026-09-03 | TCS | SHORT | -3.04% | 11.34 | ✅ with-regime | open/none |
| 2026-09-02 | BCPL | SHORT | -2.91% | 11.59 | ✅ with-regime | open/none |
| 2026-09-01 | FUSION | SHORT | -2.37% | 11.49 | ✅ with-regime | open/none |
| 2026-09-01 | AMBIKCO | SHORT | -2.37% | 11.49 | ✅ with-regime | open/none |
| 2026-09-01 | MUKANDLTD | SHORT | -2.37% | 11.49 | ✅ with-regime | open/none |
| 2026-09-01 | HEXT | SHORT | -2.37% | 11.49 | ✅ with-regime | open/none |
| 2026-09-01 | MAHLOG | SHORT | -2.37% | 11.49 | ✅ with-regime | open/none |
| 2026-08-31 | NOCIL | LONG | -2.30% | 11.19 | 🚫 would-block | open/none |
| 2026-08-31 | SUPREMEIND | SHORT | -2.30% | 11.19 | ✅ with-regime | open/none |
| 2026-08-31 | SHRINGARMS | SHORT | -2.30% | 11.19 | ✅ with-regime | open/none |
| 2026-08-31 | GRPLTD | SHORT | -2.30% | 11.19 | ✅ with-regime | open/none |
| 2026-08-31 | PNGJL | SHORT | -2.30% | 11.19 | ✅ with-regime | open/none |
| 2026-08-31 | NOCIL | LONG | -2.30% | 11.19 | 🚫 would-block | open/none |
| 2026-08-28 | PIDILITIND | SHORT | -1.95% | 10.68 | ✅ with-regime | open/none |
| 2026-08-27 | ASHIMASYN | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | IMAGICAA | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | VRLLOG | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | DELHIVERY | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | NEPHROPLUS | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | BLIL | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | DELHIVERY | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | VRLLOG | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | WALCHANNAG | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | LICHSGFIN | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | CCL | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | ADANIPORTS | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | MSPL | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | PREMIERENE | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | SINCLAIR | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | WENDT | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | IMAGICAA | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | PICCADIL | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | ASHIMASYN | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | ANTELOPUS | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | BETA | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | KKCL | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-27 | RELIGARE | LONG | -2.32% | 11.07 | 🚫 would-block | open/none |
| 2026-08-26 | IDBI | LONG | -1.87% | 10.57 | 🚫 would-block | ₹-2,331 |

_… 509 more assessable signals not shown._


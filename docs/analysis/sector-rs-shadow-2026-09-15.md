# Sector/index relative-strength shadow (live signals) — 2026-09-15

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (38 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 11 | 0 | — | — | — |
| eligible (RS in favour of the side) | 27 | 0 | — | — | — |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ⏳ NOT READY — 0/20 resolved would-block trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).


### Evidence of record — sector-RS gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 11 | 0 | — | — | — | — |
| eligible (kept) | 27 | 0 | — | — | — | — |

**Shared guards:**
- ✅ `side_proxy` — the partition is not explained by side alone
- ✅ `tail` — only 0 resolved would-block trades — not assessable
- ✅ `win_rate` — a side of the partition has no resolved trades

- **deflated Sharpe:** no resolved eligible trades yet

## Per-entry context (each committed signal's sector/index RS)

| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |
|---|---|---|---|--:|---|--:|
| 2026-09-15 | GOKEX | LONG | NIFTY50 | +4.21% | ✅ eligible | open/none |
| 2026-09-15 | APARINDS | LONG | NIFTY50 | +8.82% | ✅ eligible | open/none |
| 2026-09-15 | MANAKCOAT | LONG | NIFTY50 | +14.44% | ✅ eligible | open/none |
| 2026-09-11 | INTLCONV | LONG | NIFTY50 | +7.34% | ✅ eligible | open/none |
| 2026-09-11 | GARUDA | LONG | NIFTY50 | +3.35% | ✅ eligible | open/none |
| 2026-09-10 | MANBA | LONG | NIFTY50 | +3.76% | ✅ eligible | open/none |
| 2026-09-10 | SHINDL | LONG | NIFTY50 | +3.76% | ✅ eligible | open/none |
| 2026-09-10 | TVSSCS | LONG | NIFTY50 | +4.70% | ✅ eligible | open/none |
| 2026-09-09 | HILINFRA | LONG | NIFTY50 | +0.37% | ✅ eligible | open/none |
| 2026-09-09 | MAXHEALTH | LONG | NIFTY50 | +7.09% | ✅ eligible | open/none |
| 2026-09-09 | LIKHITHA | LONG | NIFTY50 | +1.59% | ✅ eligible | open/none |
| 2026-09-09 | KIRANVYPAR | LONG | NIFTY50 | +8.64% | ✅ eligible | open/none |
| 2026-09-09 | DREAMFOLKS | LONG | NIFTY50 | +3.24% | ✅ eligible | open/none |
| 2026-09-09 | ALIVUS | LONG | NIFTY50 | +6.98% | ✅ eligible | open/none |
| 2026-09-09 | EVEREADY | LONG | NIFTY50 | +2.89% | ✅ eligible | open/none |
| 2026-09-09 | FRONTSP | LONG | NIFTY50 | -12.16% | 🚫 would-block | open/none |
| 2026-09-09 | OBCL | LONG | NIFTY50 | +9.73% | ✅ eligible | open/none |
| 2026-09-09 | VRAJ | LONG | NIFTY50 | +5.05% | ✅ eligible | open/none |
| 2026-09-09 | BIMETAL | LONG | NIFTY50 | +4.43% | ✅ eligible | open/none |
| 2026-09-09 | PRAVEG | SHORT | NIFTY50 | +1.06% | 🚫 would-block | open/none |
| 2026-09-09 | BAJAJST | LONG | NIFTY50 | +4.64% | ✅ eligible | open/none |
| 2026-09-09 | SUNDROP | LONG | NIFTY50 | +3.86% | ✅ eligible | open/none |
| 2026-09-09 | AVANTEL | LONG | NIFTY50 | +5.61% | ✅ eligible | open/none |
| 2026-09-09 | BHAGCHEM | LONG | NIFTY50 | -2.24% | 🚫 would-block | open/none |
| 2026-09-09 | LLOYDSENT | LONG | NIFTY50 | -5.47% | 🚫 would-block | open/none |
| 2026-09-09 | HILINFRA | SHORT | NIFTY50 | +0.37% | 🚫 would-block | open/none |
| 2026-09-09 | PNGJL | LONG | NIFTY50 | +3.21% | ✅ eligible | open/none |
| 2026-09-09 | AYE | SHORT | NIFTY50 | +5.17% | 🚫 would-block | open/none |
| 2026-09-09 | IIFLCAPS | LONG | NIFTY50 | +5.02% | ✅ eligible | open/none |
| 2026-09-09 | TREL | LONG | NIFTY50 | +2.18% | ✅ eligible | open/none |
| 2026-09-09 | TRAVELFOOD | LONG | NIFTY50 | -2.47% | 🚫 would-block | open/none |
| 2026-09-09 | GANESHCP | SHORT | NIFTY50 | +7.39% | 🚫 would-block | open/none |
| 2026-09-09 | NIRLON | SHORT | NIFTY50 | +1.31% | 🚫 would-block | open/none |
| 2026-09-09 | FABTECH | LONG | NIFTY50 | +5.37% | ✅ eligible | open/none |
| 2026-09-09 | AAATECH | SHORT | NIFTY50 | +1.28% | 🚫 would-block | open/none |
| 2026-09-09 | ZYDUSLIFE | SHORT | NIFTY50 | -2.33% | ✅ eligible | open/none |
| 2026-09-09 | ACCURACY | LONG | NIFTY50 | -6.09% | 🚫 would-block | open/none |
| 2026-09-09 | PREMCO | LONG | NIFTY50 | +5.54% | ✅ eligible | open/none |


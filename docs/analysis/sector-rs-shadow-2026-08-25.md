# Sector/index relative-strength shadow (live signals) — 2026-08-25

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (477 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 200 | 26 | ₹-3,181 | ₹-122 | 50% |
| eligible (RS in favour of the side) | 277 | 48 | ₹-6,284 | ₹-131 | 52% |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ⏳ NOT READY — would-block (-122.3484615384615384615384615) not worse than eligible (-130.9195833333333333333333333) — do NOT flip. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).

## Per-entry context (each committed signal's sector/index RS)

| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |
|---|---|---|---|--:|---|--:|
| 2026-08-25 | BAJAJHLDNG | LONG | NIFTY50 | +2.78% | ✅ eligible | open/none |
| 2026-08-25 | OBCL | LONG | NIFTY50 | +6.27% | ✅ eligible | open/none |
| 2026-08-25 | BVCL | LONG | NIFTY50 | +3.73% | ✅ eligible | open/none |
| 2026-08-25 | FMGOETZE | LONG | NIFTY50 | +8.94% | ✅ eligible | open/none |
| 2026-08-25 | GOKULAGRO | LONG | NIFTY50 | +18.50% | ✅ eligible | open/none |
| 2026-08-25 | ABMKNO | LONG | NIFTY50 | -2.17% | 🚫 would-block | open/none |
| 2026-08-25 | COCHINSHIP | SHORT | NIFTY50 | +8.37% | 🚫 would-block | open/none |
| 2026-08-25 | SHREDIGCEM | LONG | NIFTY50 | +0.64% | ✅ eligible | open/none |
| 2026-08-25 | CDSL | LONG | NIFTY50 | +2.24% | ✅ eligible | open/none |
| 2026-08-25 | MOSCHIP | SHORT | NIFTY50 | -0.11% | ✅ eligible | open/none |
| 2026-08-25 | GLOBUSSPR | LONG | NIFTY50 | +3.51% | ✅ eligible | open/none |
| 2026-08-25 | AUROPHARMA | LONG | NIFTY50 | +2.97% | ✅ eligible | open/none |
| 2026-08-25 | GOKULAGRO | LONG | NIFTY50 | +18.50% | ✅ eligible | open/none |
| 2026-08-25 | FMGOETZE | LONG | NIFTY50 | +8.94% | ✅ eligible | open/none |
| 2026-08-25 | BVCL | LONG | NIFTY50 | +3.73% | ✅ eligible | open/none |
| 2026-08-25 | DBCORP | SHORT | NIFTY50 | -2.93% | ✅ eligible | open/none |
| 2026-08-25 | PRIMESECU | LONG | NIFTY50 | +0.23% | ✅ eligible | open/none |
| 2026-08-25 | OBCL | LONG | NIFTY50 | +6.27% | ✅ eligible | open/none |
| 2026-08-25 | ENRIN | SHORT | NIFTY50 | +5.11% | 🚫 would-block | open/none |
| 2026-08-25 | NIRLON | SHORT | NIFTY50 | +2.32% | 🚫 would-block | open/none |
| 2026-08-25 | BAJAJHLDNG | LONG | NIFTY50 | +2.78% | ✅ eligible | open/none |
| 2026-08-25 | KIRLOSENG | LONG | NIFTY50 | -8.89% | 🚫 would-block | open/none |
| 2026-08-25 | RAMAPHO | LONG | NIFTY50 | -4.29% | 🚫 would-block | open/none |
| 2026-08-25 | SRTL | SHORT | NIFTY50 | -2.15% | ✅ eligible | open/none |
| 2026-08-25 | KSB | LONG | NIFTY50 | -6.64% | 🚫 would-block | open/none |
| 2026-08-24 | GOKUL | LONG | NIFTY50 | +11.06% | ✅ eligible | open/none |
| 2026-08-24 | ADROITINFO | LONG | NIFTY50 | +11.97% | ✅ eligible | open/none |
| 2026-08-24 | AJAXENGG | LONG | NIFTY50 | +0.83% | ✅ eligible | open/none |
| 2026-08-24 | 20MICRONS | LONG | NIFTY50 | +3.61% | ✅ eligible | open/none |
| 2026-08-24 | DVL | LONG | NIFTY50 | +16.65% | ✅ eligible | open/none |
| 2026-08-24 | RICOAUTO | LONG | NIFTY50 | -13.58% | 🚫 would-block | open/none |
| 2026-08-24 | EMKAY | LONG | NIFTY50 | +2.41% | ✅ eligible | open/none |
| 2026-08-24 | HIRECT | LONG | NIFTY50 | -9.11% | 🚫 would-block | open/none |
| 2026-08-24 | 21STCENMGM | LONG | NIFTY50 | +15.24% | ✅ eligible | open/none |
| 2026-08-24 | STARPAPER | LONG | NIFTY50 | -4.00% | 🚫 would-block | open/none |
| 2026-08-24 | ZYDUSLIFE | LONG | NIFTY50 | -1.33% | 🚫 would-block | open/none |
| 2026-08-24 | WELSPLSOL | LONG | NIFTY50 | -1.12% | 🚫 would-block | open/none |
| 2026-08-24 | MARICO | LONG | NIFTY50 | -2.39% | 🚫 would-block | open/none |
| 2026-08-24 | DVL | LONG | NIFTY50 | +16.65% | ✅ eligible | open/none |
| 2026-08-24 | ASHOKLEY | LONG | NIFTY50 | +10.83% | ✅ eligible | open/none |
| 2026-08-24 | BHARTIHEXA | LONG | NIFTY50 | -1.46% | 🚫 would-block | open/none |
| 2026-08-24 | TIPSMUSIC | LONG | NIFTY50 | -10.59% | 🚫 would-block | open/none |
| 2026-08-24 | ACCURACY | LONG | NIFTY50 | -6.09% | 🚫 would-block | open/none |
| 2026-08-24 | 20MICRONS | LONG | NIFTY50 | +3.61% | ✅ eligible | open/none |
| 2026-08-24 | AYE | LONG | NIFTY50 | -0.71% | 🚫 would-block | open/none |
| 2026-08-24 | BORANA | LONG | NIFTY50 | -7.73% | 🚫 would-block | open/none |
| 2026-08-24 | AJAXENGG | LONG | NIFTY50 | +0.83% | ✅ eligible | open/none |
| 2026-08-24 | SHIVATEX | LONG | NIFTY50 | +8.26% | ✅ eligible | open/none |
| 2026-08-24 | KIRLOSIND | LONG | NIFTY50 | -4.70% | 🚫 would-block | open/none |
| 2026-08-24 | TRAVELFOOD | LONG | NIFTY50 | +1.45% | ✅ eligible | open/none |

_… 427 more assessable signals not shown._


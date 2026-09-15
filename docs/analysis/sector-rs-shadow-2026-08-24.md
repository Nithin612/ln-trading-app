# Sector/index relative-strength shadow (live signals) — 2026-08-24

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (452 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 193 | 25 | ₹-6,031 | ₹-241 | 48% |
| eligible (RS in favour of the side) | 259 | 47 | ₹-4,187 | ₹-89 | 53% |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ✅ READY — would-block net-negative (-241.2444), worse than eligible (-89.09446808510638297872340426) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).

## Per-entry context (each committed signal's sector/index RS)

| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |
|---|---|---|---|--:|---|--:|
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
| 2026-08-24 | CGPOWER | LONG | NIFTY50 | -0.91% | 🚫 would-block | open/none |
| 2026-08-24 | SAIPARENT | LONG | NIFTY50 | -6.47% | 🚫 would-block | open/none |
| 2026-08-24 | BIOCON | LONG | NIFTY50 | -7.08% | 🚫 would-block | open/none |
| 2026-08-24 | ADROITINFO | LONG | NIFTY50 | +11.97% | ✅ eligible | open/none |
| 2026-08-24 | ARKADE | LONG | NIFTY50 | -2.99% | 🚫 would-block | open/none |
| 2026-08-24 | CAPITALSFB | LONG | NIFTY50 | -5.72% | 🚫 would-block | open/none |
| 2026-08-24 | GOKUL | LONG | NIFTY50 | +11.06% | ✅ eligible | open/none |
| 2026-08-24 | ALGOQUANT | LONG | NIFTY50 | -5.63% | 🚫 would-block | open/none |
| 2026-08-24 | KIRLFER | LONG | NIFTY50 | -8.59% | 🚫 would-block | open/none |
| 2026-08-24 | GRAUWEIL | LONG | NIFTY50 | -6.29% | 🚫 would-block | open/none |
| 2026-08-21 | GUJTHEM | LONG | NIFTY50 | +3.70% | ✅ eligible | open/none |
| 2026-08-21 | BENGALASM | LONG | NIFTY50 | -1.17% | 🚫 would-block | open/none |
| 2026-08-21 | GUJTHEM | LONG | NIFTY50 | +3.70% | ✅ eligible | open/none |
| 2026-08-19 | TFCILTD | LONG | NIFTY50 | +60.29% | ✅ eligible | open/none |
| 2026-08-19 | YUKEN | LONG | NIFTY50 | +30.44% | ✅ eligible | open/none |
| 2026-08-19 | KALYANIFRG | LONG | NIFTY50 | +10.51% | ✅ eligible | open/none |
| 2026-08-19 | KALYANIFRG | LONG | NIFTY50 | +10.51% | ✅ eligible | open/none |
| 2026-08-19 | YUKEN | LONG | NIFTY50 | +30.44% | ✅ eligible | open/none |
| 2026-08-19 | ZENITHEXPO | LONG | NIFTY50 | +3.94% | ✅ eligible | open/none |
| 2026-08-19 | TFCILTD | LONG | NIFTY50 | +60.29% | ✅ eligible | open/none |
| 2026-08-18 | JTLIND | SHORT | NIFTY50 | -1.89% | ✅ eligible | open/none |
| 2026-08-18 | CUMMINSIND | SHORT | NIFTY50 | -4.04% | ✅ eligible | open/none |
| 2026-08-17 | SOUTHBANK | SHORT | NIFTY50 | -2.28% | ✅ eligible | open/none |
| 2026-08-14 | BPCL | LONG | NIFTY50 | +1.11% | ✅ eligible | open/none |
| 2026-08-14 | HATSUN | LONG | NIFTY50 | +5.59% | ✅ eligible | open/none |

_… 402 more assessable signals not shown._


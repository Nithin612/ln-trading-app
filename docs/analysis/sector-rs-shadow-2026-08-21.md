# Sector/index relative-strength shadow (live signals) — 2026-08-21

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (417 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 173 | 24 | ₹-2,560 | ₹-107 | 50% |
| eligible (RS in favour of the side) | 244 | 47 | ₹-4,187 | ₹-89 | 53% |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ✅ READY — would-block net-negative (-106.68), worse than eligible (-89.09446808510638297872340426) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).

## Per-entry context (each committed signal's sector/index RS)

| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |
|---|---|---|---|--:|---|--:|
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
| 2026-08-14 | GROBTEA | LONG | NIFTY50 | +5.78% | ✅ eligible | open/none |
| 2026-08-14 | MARUTI | SHORT | NIFTY50 | +0.09% | 🚫 would-block | open/none |
| 2026-08-14 | MCLOUD | SHORT | NIFTY50 | +0.26% | 🚫 would-block | open/none |
| 2026-08-14 | LTTS | SHORT | NIFTY50 | +1.67% | 🚫 would-block | open/none |
| 2026-08-14 | SEIL | LONG | NIFTY50 | +3.72% | ✅ eligible | open/none |
| 2026-08-14 | AERONEU | LONG | NIFTY50 | -4.00% | 🚫 would-block | open/none |
| 2026-08-14 | MARUTI | SHORT | NIFTY50 | +0.09% | 🚫 would-block | open/none |
| 2026-08-14 | RELIABLE | SHORT | NIFTY50 | -6.20% | ✅ eligible | open/none |
| 2026-08-14 | PREMIERENE | SHORT | NIFTY50 | -6.47% | ✅ eligible | ₹-2,257 |
| 2026-08-14 | RITES | SHORT | NIFTY50 | +1.23% | 🚫 would-block | open/none |
| 2026-08-14 | KOVAI | LONG | NIFTY50 | +0.75% | ✅ eligible | open/none |
| 2026-08-14 | IMAGICAA | LONG | NIFTY50 | -0.05% | 🚫 would-block | open/none |
| 2026-08-14 | INDIAMART | SHORT | NIFTY50 | -6.42% | ✅ eligible | open/none |
| 2026-08-14 | LEMERITE | SHORT | NIFTY50 | +13.50% | 🚫 would-block | open/none |
| 2026-08-14 | STUDDS | SHORT | NIFTY50 | -5.89% | ✅ eligible | open/none |
| 2026-08-14 | KSL | SHORT | NIFTY50 | -9.54% | ✅ eligible | ₹-2,278 |
| 2026-08-14 | AVANTEL | SHORT | NIFTY50 | -6.97% | ✅ eligible | open/none |
| 2026-08-14 | HATSUN | LONG | NIFTY50 | +5.59% | ✅ eligible | open/none |
| 2026-08-14 | DONEAR | LONG | NIFTY50 | +4.60% | ✅ eligible | open/none |
| 2026-08-14 | SKIPPER | SHORT | NIFTY50 | -2.63% | ✅ eligible | open/none |
| 2026-08-14 | BPCL | LONG | NIFTY50 | +1.11% | ✅ eligible | open/none |
| 2026-08-14 | CGCL | LONG | NIFTY50 | -11.78% | 🚫 would-block | open/none |
| 2026-08-13 | TEJASNET | LONG | NIFTY50 | -2.65% | 🚫 would-block | open/none |
| 2026-08-13 | TARMAT | LONG | NIFTY50 | +32.49% | ✅ eligible | open/none |
| 2026-08-13 | PODDARMENT | LONG | NIFTY50 | +11.13% | ✅ eligible | open/none |
| 2026-08-13 | GRSE | LONG | NIFTY50 | +0.26% | ✅ eligible | open/none |
| 2026-08-13 | UCAL | LONG | NIFTY50 | +3.31% | ✅ eligible | open/none |
| 2026-08-13 | BEL | LONG | NIFTY50 | -0.51% | 🚫 would-block | open/none |
| 2026-08-13 | BAJFINANCE | SHORT | FINNIFTY | +5.99% | 🚫 would-block | open/none |
| 2026-08-13 | BEL | LONG | NIFTY50 | -0.51% | 🚫 would-block | open/none |
| 2026-08-13 | 3PLAND | LONG | NIFTY50 | -0.31% | 🚫 would-block | open/none |
| 2026-08-13 | APLLTD | SHORT | NIFTY50 | -2.36% | ✅ eligible | open/none |
| 2026-08-13 | VISHWARAJ | LONG | NIFTY50 | +0.15% | ✅ eligible | open/none |
| 2026-08-13 | MODTHREAD | LONG | NIFTY50 | -3.86% | 🚫 would-block | open/none |
| 2026-08-13 | GMDCLTD | SHORT | NIFTY50 | -0.22% | ✅ eligible | open/none |

_… 367 more assessable signals not shown._


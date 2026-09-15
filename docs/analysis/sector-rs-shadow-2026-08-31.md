# Sector/index relative-strength shadow (live signals) — 2026-08-31

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (540 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 218 | 29 | ₹-7,232 | ₹-249 | 48% |
| eligible (RS in favour of the side) | 322 | 53 | ₹660 | ₹12 | 55% |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ✅ READY — would-block net-negative (-249.3672413793103448275862069), worse than eligible (12.45094339622641509433962264) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).

## Per-entry context (each committed signal's sector/index RS)

| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |
|---|---|---|---|--:|---|--:|
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
| 2026-08-26 | IDBI | LONG | NIFTY50 | +12.78% | ✅ eligible | open/none |
| 2026-08-26 | ROSSELLIND | LONG | NIFTY50 | +5.64% | ✅ eligible | open/none |
| 2026-08-26 | ORIENTELEC | LONG | NIFTY50 | +7.23% | ✅ eligible | open/none |
| 2026-08-26 | KIRIINDUS | LONG | NIFTY50 | +26.65% | ✅ eligible | open/none |
| 2026-08-26 | GENCON | LONG | NIFTY50 | +18.28% | ✅ eligible | open/none |
| 2026-08-26 | RAMRAT | LONG | NIFTY50 | +14.90% | ✅ eligible | open/none |
| 2026-08-26 | AXISBANK | LONG | BANKNIFTY | +0.58% | ✅ eligible | open/none |
| 2026-08-26 | GPPL | LONG | NIFTY50 | +13.01% | ✅ eligible | open/none |
| 2026-08-26 | SATIN | LONG | NIFTY50 | -11.97% | 🚫 would-block | open/none |
| 2026-08-26 | CERA | LONG | NIFTY50 | -6.76% | 🚫 would-block | open/none |
| 2026-08-26 | ATLANTAA | LONG | NIFTY50 | +5.29% | ✅ eligible | open/none |
| 2026-08-26 | GRINFRA | LONG | NIFTY50 | +2.47% | ✅ eligible | open/none |
| 2026-08-26 | BOSCH-HCIL | LONG | NIFTY50 | +29.62% | ✅ eligible | open/none |
| 2026-08-26 | GPPL | LONG | NIFTY50 | +13.01% | ✅ eligible | open/none |
| 2026-08-26 | RELTD | LONG | NIFTY50 | -9.08% | 🚫 would-block | ₹-3,137 |
| 2026-08-26 | SEIL | LONG | NIFTY50 | +1.92% | ✅ eligible | open/none |
| 2026-08-26 | AXISBANK | LONG | BANKNIFTY | +0.58% | ✅ eligible | open/none |
| 2026-08-26 | KOVAI | LONG | NIFTY50 | +3.15% | ✅ eligible | open/none |
| 2026-08-26 | RAMRAT | LONG | NIFTY50 | +14.90% | ✅ eligible | open/none |
| 2026-08-26 | GENCON | LONG | NIFTY50 | +18.28% | ✅ eligible | open/none |

_… 490 more assessable signals not shown._


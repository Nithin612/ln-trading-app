# Sector/index relative-strength shadow (live signals) — 2026-08-26

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (510 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 208 | 27 | ₹-1,902 | ₹-70 | 52% |
| eligible (RS in favour of the side) | 302 | 48 | ₹-6,284 | ₹-131 | 52% |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ⏳ NOT READY — would-block (-70.44185185185185185185185185) not worse than eligible (-130.9195833333333333333333333) — do NOT flip. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).

## Per-entry context (each committed signal's sector/index RS)

| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |
|---|---|---|---|--:|---|--:|
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
| 2026-08-26 | RELTD | LONG | NIFTY50 | -9.08% | 🚫 would-block | open/none |
| 2026-08-26 | SEIL | LONG | NIFTY50 | +1.92% | ✅ eligible | open/none |
| 2026-08-26 | AXISBANK | LONG | BANKNIFTY | +0.58% | ✅ eligible | open/none |
| 2026-08-26 | KOVAI | LONG | NIFTY50 | +3.15% | ✅ eligible | open/none |
| 2026-08-26 | RAMRAT | LONG | NIFTY50 | +14.90% | ✅ eligible | open/none |
| 2026-08-26 | GENCON | LONG | NIFTY50 | +18.28% | ✅ eligible | open/none |
| 2026-08-26 | LOVABLE | LONG | NIFTY50 | +5.17% | ✅ eligible | open/none |
| 2026-08-26 | CORONA | LONG | NIFTY50 | -0.03% | 🚫 would-block | open/none |
| 2026-08-26 | SMCGLOBAL | LONG | NIFTY50 | -0.79% | 🚫 would-block | open/none |
| 2026-08-26 | STAR | LONG | NIFTY50 | -7.10% | 🚫 would-block | open/none |
| 2026-08-26 | KIRIINDUS | LONG | NIFTY50 | +26.65% | ✅ eligible | open/none |
| 2026-08-26 | ENIL | LONG | NIFTY50 | -0.59% | 🚫 would-block | open/none |
| 2026-08-26 | PRSMJOHNSN | LONG | NIFTY50 | +4.24% | ✅ eligible | open/none |
| 2026-08-26 | CMPDI | LONG | NIFTY50 | -5.07% | 🚫 would-block | open/none |
| 2026-08-26 | ORIENTELEC | LONG | NIFTY50 | +7.23% | ✅ eligible | open/none |
| 2026-08-26 | ROSSELLIND | LONG | NIFTY50 | +5.64% | ✅ eligible | open/none |
| 2026-08-26 | ORKLAINDIA | LONG | NIFTY50 | +2.69% | ✅ eligible | open/none |
| 2026-08-26 | RAJPALAYAM | LONG | NIFTY50 | +1.03% | ✅ eligible | open/none |
| 2026-08-26 | IDBI | LONG | NIFTY50 | +12.78% | ✅ eligible | open/none |
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

_… 460 more assessable signals not shown._


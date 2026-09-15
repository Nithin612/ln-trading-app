# Market-regime shadow (live signals) — 2026-08-26

_Read-only. The market-regime overlay recomputed over the tradeable signal cohort since 2026-07-19 (510 signals), broad-market (NIFTY50) trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when the market regime is AGAINST its side — a long while NIFTY50 is below its 200-DMA, a short while above. 'no market data' = fewer than 200 index sessions yet (fails open live; needs the deep index backfill). VIX is reported per entry but never gates. A would-block set net-negative AND worse than the with-regime set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (regime against the side) | 380 | 44 | ₹-9,485 | ₹-216 | 57% |
| with-regime (eligible) | 130 | 31 | ₹1,299 | ₹42 | 45% |
| no market data (< 200-DMA history) | 0 | 0 | — | — | — |

**market-regime flip readiness:** ✅ READY — would-block net-negative (-215.5606818181818181818181818), worse than eligible (41.89032258064516129032258065) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `market_regime_gate_mode=shadow`).

## Per-entry context (each committed signal's market regime)

| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |
|---|---|---|--:|--:|---|--:|
| 2026-08-26 | IDBI | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | ROSSELLIND | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | ORIENTELEC | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | KIRIINDUS | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | GENCON | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | RAMRAT | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | AXISBANK | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | GPPL | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | SATIN | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | CERA | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | ATLANTAA | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | GRINFRA | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | BOSCH-HCIL | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | GPPL | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | RELTD | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | SEIL | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | AXISBANK | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | KOVAI | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | RAMRAT | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | GENCON | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | LOVABLE | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | CORONA | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | SMCGLOBAL | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | STAR | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | KIRIINDUS | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | ENIL | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | PRSMJOHNSN | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | CMPDI | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | ORIENTELEC | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | ROSSELLIND | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | ORKLAINDIA | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | RAJPALAYAM | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-26 | IDBI | LONG | -1.87% | 10.57 | 🚫 would-block | open/none |
| 2026-08-25 | BAJAJHLDNG | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | OBCL | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | BVCL | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | FMGOETZE | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | GOKULAGRO | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | ABMKNO | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | COCHINSHIP | SHORT | -1.39% | 11.08 | ✅ with-regime | open/none |
| 2026-08-25 | SHREDIGCEM | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | CDSL | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | MOSCHIP | SHORT | -1.39% | 11.08 | ✅ with-regime | open/none |
| 2026-08-25 | GLOBUSSPR | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | AUROPHARMA | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | GOKULAGRO | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | FMGOETZE | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | BVCL | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | DBCORP | SHORT | -1.39% | 11.08 | ✅ with-regime | open/none |
| 2026-08-25 | PRIMESECU | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |

_… 460 more assessable signals not shown._


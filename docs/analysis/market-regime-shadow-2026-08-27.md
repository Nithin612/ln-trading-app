# Market-regime shadow (live signals) — 2026-08-27

_Read-only. The market-regime overlay recomputed over the tradeable signal cohort since 2026-07-19 (533 signals), broad-market (NIFTY50) trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when the market regime is AGAINST its side — a long while NIFTY50 is below its 200-DMA, a short while above. 'no market data' = fewer than 200 index sessions yet (fails open live; needs the deep index backfill). VIX is reported per entry but never gates. A would-block set net-negative AND worse than the with-regime set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (regime against the side) | 403 | 47 | ₹-5,773 | ₹-123 | 57% |
| with-regime (eligible) | 130 | 32 | ₹-1,420 | ₹-44 | 44% |
| no market data (< 200-DMA history) | 0 | 0 | — | — | — |

**market-regime flip readiness:** ✅ READY — would-block net-negative (-122.8197872340425531914893617), worse than eligible (-44.3859375) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `market_regime_gate_mode=shadow`).

## Per-entry context (each committed signal's market regime)

| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |
|---|---|---|--:|--:|---|--:|
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
| 2026-08-26 | RELTD | LONG | -1.87% | 10.57 | 🚫 would-block | ₹-3,137 |
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

_… 483 more assessable signals not shown._


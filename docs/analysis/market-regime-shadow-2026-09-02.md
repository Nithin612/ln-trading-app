# Market-regime shadow (live signals) — 2026-09-02

_Read-only. The market-regime overlay recomputed over the tradeable signal cohort since 2026-07-19 (546 signals), broad-market (NIFTY50) trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when the market regime is AGAINST its side — a long while NIFTY50 is below its 200-DMA, a short while above. 'no market data' = fewer than 200 index sessions yet (fails open live; needs the deep index backfill). VIX is reported per entry but never gates. A would-block set net-negative AND worse than the with-regime set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (regime against the side) | 405 | 58 | ₹-17,519 | ₹-302 | 52% |
| with-regime (eligible) | 141 | 33 | ₹-221 | ₹-7 | 45% |
| no market data (< 200-DMA history) | 0 | 0 | — | — | — |

**market-regime flip readiness:** ✅ READY — would-block net-negative (-302.0532758620689655172413793), worse than eligible (-6.709393939393939393939393939) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `market_regime_gate_mode=shadow`).

## Per-entry context (each committed signal's market regime)

| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |
|---|---|---|--:|--:|---|--:|
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

_… 496 more assessable signals not shown._


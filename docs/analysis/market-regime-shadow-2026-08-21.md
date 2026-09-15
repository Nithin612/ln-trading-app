# Market-regime shadow (live signals) — 2026-08-21

_Read-only. The market-regime overlay recomputed over the tradeable signal cohort since 2026-07-19 (417 signals), broad-market (NIFTY50) trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when the market regime is AGAINST its side — a long while NIFTY50 is below its 200-DMA, a short while above. 'no market data' = fewer than 200 index sessions yet (fails open live; needs the deep index backfill). VIX is reported per entry but never gates. A would-block set net-negative AND worse than the with-regime set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (regime against the side) | 293 | 41 | ₹-6,767 | ₹-165 | 59% |
| with-regime (eligible) | 124 | 30 | ₹19 | ₹1 | 43% |
| no market data (< 200-DMA history) | 0 | 0 | — | — | — |

**market-regime flip readiness:** ✅ READY — would-block net-negative (-165.0543902439024390243902439), worse than eligible (0.649) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `market_regime_gate_mode=shadow`).

## Per-entry context (each committed signal's market regime)

| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |
|---|---|---|--:|--:|---|--:|
| 2026-08-21 | GUJTHEM | LONG | -1.78% | 11.20 | 🚫 would-block | open/none |
| 2026-08-21 | BENGALASM | LONG | -1.78% | 11.20 | 🚫 would-block | open/none |
| 2026-08-21 | GUJTHEM | LONG | -1.78% | 11.20 | 🚫 would-block | open/none |
| 2026-08-19 | TFCILTD | LONG | -2.56% | 11.32 | 🚫 would-block | open/none |
| 2026-08-19 | YUKEN | LONG | -2.56% | 11.32 | 🚫 would-block | open/none |
| 2026-08-19 | KALYANIFRG | LONG | -2.56% | 11.32 | 🚫 would-block | open/none |
| 2026-08-19 | KALYANIFRG | LONG | -2.56% | 11.32 | 🚫 would-block | open/none |
| 2026-08-19 | YUKEN | LONG | -2.56% | 11.32 | 🚫 would-block | open/none |
| 2026-08-19 | ZENITHEXPO | LONG | -2.56% | 11.32 | 🚫 would-block | open/none |
| 2026-08-19 | TFCILTD | LONG | -2.56% | 11.32 | 🚫 would-block | open/none |
| 2026-08-18 | JTLIND | SHORT | -2.28% | 11.39 | ✅ with-regime | open/none |
| 2026-08-18 | CUMMINSIND | SHORT | -2.28% | 11.39 | ✅ with-regime | open/none |
| 2026-08-17 | SOUTHBANK | SHORT | -1.78% | 11.33 | ✅ with-regime | open/none |
| 2026-08-14 | BPCL | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | HATSUN | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | GROBTEA | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | MARUTI | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | MCLOUD | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | LTTS | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | SEIL | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | AERONEU | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | MARUTI | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | RELIABLE | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | PREMIERENE | SHORT | -1.49% | 11.31 | ✅ with-regime | ₹-2,257 |
| 2026-08-14 | RITES | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | KOVAI | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | IMAGICAA | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | INDIAMART | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | LEMERITE | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | STUDDS | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | KSL | SHORT | -1.49% | 11.31 | ✅ with-regime | ₹-2,278 |
| 2026-08-14 | AVANTEL | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | HATSUN | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | DONEAR | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | SKIPPER | SHORT | -1.49% | 11.31 | ✅ with-regime | open/none |
| 2026-08-14 | BPCL | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-14 | CGCL | LONG | -1.49% | 11.31 | 🚫 would-block | open/none |
| 2026-08-13 | TEJASNET | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | TARMAT | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | PODDARMENT | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | GRSE | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | UCAL | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | BEL | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | BAJFINANCE | SHORT | -1.40% | 11.42 | ✅ with-regime | open/none |
| 2026-08-13 | BEL | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | 3PLAND | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | APLLTD | SHORT | -1.40% | 11.42 | ✅ with-regime | open/none |
| 2026-08-13 | VISHWARAJ | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | MODTHREAD | LONG | -1.40% | 11.42 | 🚫 would-block | open/none |
| 2026-08-13 | GMDCLTD | SHORT | -1.40% | 11.42 | ✅ with-regime | open/none |

_… 367 more assessable signals not shown._


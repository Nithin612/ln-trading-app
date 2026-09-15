# Market-regime shadow (live signals) — 2026-08-25

_Read-only. The market-regime overlay recomputed over the tradeable signal cohort since 2026-07-19 (477 signals), broad-market (NIFTY50) trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when the market regime is AGAINST its side — a long while NIFTY50 is below its 200-DMA, a short while above. 'no market data' = fewer than 200 index sessions yet (fails open live; needs the deep index backfill). VIX is reported per entry but never gates. A would-block set net-negative AND worse than the with-regime set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (regime against the side) | 347 | 44 | ₹-9,485 | ₹-216 | 57% |
| with-regime (eligible) | 130 | 30 | ₹19 | ₹1 | 43% |
| no market data (< 200-DMA history) | 0 | 0 | — | — | — |

**market-regime flip readiness:** ✅ READY — would-block net-negative (-215.5606818181818181818181818), worse than eligible (0.649) — READY for sign-off. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `market_regime_gate_mode=shadow`).

## Per-entry context (each committed signal's market regime)

| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |
|---|---|---|--:|--:|---|--:|
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
| 2026-08-25 | OBCL | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | ENRIN | SHORT | -1.39% | 11.08 | ✅ with-regime | open/none |
| 2026-08-25 | NIRLON | SHORT | -1.39% | 11.08 | ✅ with-regime | open/none |
| 2026-08-25 | BAJAJHLDNG | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | KIRLOSENG | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | RAMAPHO | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-25 | SRTL | SHORT | -1.39% | 11.08 | ✅ with-regime | open/none |
| 2026-08-25 | KSB | LONG | -1.39% | 11.08 | 🚫 would-block | open/none |
| 2026-08-24 | GOKUL | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | ADROITINFO | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | AJAXENGG | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | 20MICRONS | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | DVL | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | RICOAUTO | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | EMKAY | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | HIRECT | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | 21STCENMGM | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | STARPAPER | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | ZYDUSLIFE | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | WELSPLSOL | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | MARICO | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | DVL | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | ASHOKLEY | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | BHARTIHEXA | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | TIPSMUSIC | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | ACCURACY | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | 20MICRONS | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | AYE | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | BORANA | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | AJAXENGG | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | SHIVATEX | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | KIRLOSIND | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |
| 2026-08-24 | TRAVELFOOD | LONG | -1.88% | 11.53 | 🚫 would-block | open/none |

_… 427 more assessable signals not shown._


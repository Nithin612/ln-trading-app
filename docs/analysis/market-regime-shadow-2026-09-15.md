# Market-regime shadow (live signals) — 2026-09-15

_Read-only. The market-regime overlay recomputed over the tradeable signal cohort since 2026-07-19 (38 signals), broad-market (NIFTY50) trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when the market regime is AGAINST its side — a long while NIFTY50 is below its 200-DMA, a short while above. 'no market data' = fewer than 200 index sessions yet (fails open live; needs the deep index backfill). VIX is reported per entry but never gates. A would-block set net-negative AND worse than the with-regime set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (regime against the side) | 31 | 0 | — | — | — |
| with-regime (eligible) | 7 | 0 | — | — | — |
| no market data (< 200-DMA history) | 0 | 0 | — | — | — |

**market-regime flip readiness:** ⏳ NOT READY — VETOED by a shared readiness guard — [side_proxy] the partition is a PROXY FOR SIDE — 100% of would-block entries are LONG and 100% of eligible are SHORT. This evidence measures long-vs-short performance over the window, not the gate, so it cannot certify a flip however good the headline looks. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `market_regime_gate_mode=shadow`).


### Evidence of record — market-regime gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 31 | 0 | — | — | — | — |
| eligible (kept) | 7 | 0 | — | — | — | — |

**Shared guards:**
- 🚫 `side_proxy` — the partition is a PROXY FOR SIDE — 100% of would-block entries are LONG and 100% of eligible are SHORT. This evidence measures long-vs-short performance over the window, not the gate, so it cannot certify a flip however good the headline looks
- ✅ `tail` — only 0 resolved would-block trades — not assessable
- ✅ `win_rate` — a side of the partition has no resolved trades

- **deflated Sharpe:** no resolved eligible trades yet

## Per-entry context (each committed signal's market regime)

| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |
|---|---|---|--:|--:|---|--:|
| 2026-09-15 | GOKEX | LONG | -5.77% | 13.43 | 🚫 would-block | open/none |
| 2026-09-15 | APARINDS | LONG | -5.77% | 13.43 | 🚫 would-block | open/none |
| 2026-09-15 | MANAKCOAT | LONG | -5.77% | 13.43 | 🚫 would-block | open/none |
| 2026-09-11 | INTLCONV | LONG | -4.69% | 12.29 | 🚫 would-block | open/none |
| 2026-09-11 | GARUDA | LONG | -4.69% | 12.29 | 🚫 would-block | open/none |
| 2026-09-10 | MANBA | LONG | -4.42% | 11.80 | 🚫 would-block | open/none |
| 2026-09-10 | SHINDL | LONG | -4.42% | 11.80 | 🚫 would-block | open/none |
| 2026-09-10 | TVSSCS | LONG | -4.42% | 11.80 | 🚫 would-block | open/none |
| 2026-09-09 | HILINFRA | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | MAXHEALTH | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | LIKHITHA | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | KIRANVYPAR | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | DREAMFOLKS | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | ALIVUS | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | EVEREADY | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | FRONTSP | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | OBCL | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | VRAJ | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | BIMETAL | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | PRAVEG | SHORT | -4.66% | 11.92 | ✅ with-regime | open/none |
| 2026-09-09 | BAJAJST | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | SUNDROP | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | AVANTEL | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | BHAGCHEM | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | LLOYDSENT | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | HILINFRA | SHORT | -4.66% | 11.92 | ✅ with-regime | open/none |
| 2026-09-09 | PNGJL | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | AYE | SHORT | -4.66% | 11.92 | ✅ with-regime | open/none |
| 2026-09-09 | IIFLCAPS | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | TREL | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | TRAVELFOOD | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | GANESHCP | SHORT | -4.66% | 11.92 | ✅ with-regime | open/none |
| 2026-09-09 | NIRLON | SHORT | -4.66% | 11.92 | ✅ with-regime | open/none |
| 2026-09-09 | FABTECH | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | AAATECH | SHORT | -4.66% | 11.92 | ✅ with-regime | open/none |
| 2026-09-09 | ZYDUSLIFE | SHORT | -4.66% | 11.92 | ✅ with-regime | open/none |
| 2026-09-09 | ACCURACY | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |
| 2026-09-09 | PREMCO | LONG | -4.66% | 11.92 | 🚫 would-block | open/none |


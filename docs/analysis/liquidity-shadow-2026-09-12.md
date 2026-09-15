# Liquidity shadow (live signals) — 2026-09-12

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (35 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 19 | 0 | — | — | — |
| liquid (eligible) | 16 | 0 | — | — | — |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — 0/20 resolved illiquid trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).


### Evidence of record — liquidity gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 19 | 0 | — | — | — | — |
| eligible (kept) | 16 | 0 | — | — | — | — |

**Shared guards:**
- ✅ `side_proxy` — the partition is not explained by side alone
- ✅ `tail` — only 0 resolved would-block trades — not assessable
- ✅ `win_rate` — a side of the partition has no resolved trades

- **deflated Sharpe:** no resolved eligible trades yet

## Per-entry context (each committed signal's liquidity)

| date | stock | side | median ₹/day | liquidity | outcome |
|---|---|---|--:|---|--:|
| 2026-09-11 | INTLCONV | LONG | ₹3,465,030 | 🚫 illiquid | open/none |
| 2026-09-11 | GARUDA | LONG | ₹64,657,904 | ✅ liquid | open/none |
| 2026-09-10 | MANBA | LONG | ₹8,730,358 | 🚫 illiquid | open/none |
| 2026-09-10 | SHINDL | LONG | ₹35,709,307 | ✅ liquid | open/none |
| 2026-09-10 | TVSSCS | LONG | ₹83,068,016 | ✅ liquid | open/none |
| 2026-09-09 | HILINFRA | LONG | ₹2,684,500 | 🚫 illiquid | open/none |
| 2026-09-09 | MAXHEALTH | LONG | ₹1,838,169,996 | ✅ liquid | open/none |
| 2026-09-09 | LIKHITHA | LONG | ₹8,090,427 | 🚫 illiquid | open/none |
| 2026-09-09 | KIRANVYPAR | LONG | ₹441,794 | 🚫 illiquid | open/none |
| 2026-09-09 | DREAMFOLKS | LONG | ₹3,006,608 | 🚫 illiquid | open/none |
| 2026-09-09 | ALIVUS | LONG | ₹113,954,087 | ✅ liquid | open/none |
| 2026-09-09 | EVEREADY | LONG | ₹24,189,058 | ✅ liquid | open/none |
| 2026-09-09 | FRONTSP | LONG | ₹18,219,477 | ✅ liquid | open/none |
| 2026-09-09 | OBCL | LONG | ₹431,285 | 🚫 illiquid | open/none |
| 2026-09-09 | VRAJ | LONG | ₹1,329,408 | 🚫 illiquid | open/none |
| 2026-09-09 | BIMETAL | LONG | ₹228,667 | 🚫 illiquid | open/none |
| 2026-09-09 | PRAVEG | SHORT | ₹9,054,326 | 🚫 illiquid | open/none |
| 2026-09-09 | BAJAJST | LONG | ₹2,635,250 | 🚫 illiquid | open/none |
| 2026-09-09 | SUNDROP | LONG | ₹6,766,394 | 🚫 illiquid | open/none |
| 2026-09-09 | AVANTEL | LONG | ₹96,969,300 | ✅ liquid | open/none |
| 2026-09-09 | BHAGCHEM | LONG | ₹16,353,936 | ✅ liquid | open/none |
| 2026-09-09 | LLOYDSENT | LONG | ₹185,164,579 | ✅ liquid | open/none |
| 2026-09-09 | HILINFRA | SHORT | ₹2,684,500 | 🚫 illiquid | open/none |
| 2026-09-09 | PNGJL | LONG | ₹296,802,254 | ✅ liquid | open/none |
| 2026-09-09 | AYE | SHORT | ₹184,044,331 | ✅ liquid | open/none |
| 2026-09-09 | IIFLCAPS | LONG | ₹70,410,707 | ✅ liquid | open/none |
| 2026-09-09 | TREL | LONG | ₹3,360,533 | 🚫 illiquid | open/none |
| 2026-09-09 | TRAVELFOOD | LONG | ₹49,969,309 | ✅ liquid | open/none |
| 2026-09-09 | GANESHCP | SHORT | ₹25,159,318 | ✅ liquid | open/none |
| 2026-09-09 | NIRLON | SHORT | ₹5,192,846 | 🚫 illiquid | open/none |
| 2026-09-09 | FABTECH | LONG | ₹9,468,017 | 🚫 illiquid | open/none |
| 2026-09-09 | AAATECH | SHORT | ₹1,058,788 | 🚫 illiquid | open/none |
| 2026-09-09 | ZYDUSLIFE | SHORT | ₹1,361,404,916 | ✅ liquid | open/none |
| 2026-09-09 | ACCURACY | LONG | ₹492,276 | 🚫 illiquid | open/none |
| 2026-09-09 | PREMCO | LONG | ₹212,129 | 🚫 illiquid | open/none |


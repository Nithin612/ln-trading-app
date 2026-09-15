# Liquidity shadow (live signals) — 2026-09-04

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (559 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 174 | 19 | ₹6,201 | ₹326 | 58% |
| liquid (eligible) | 385 | 76 | ₹-17,953 | ₹-236 | 47% |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — VETOED by a shared readiness guard — [tail] would-block MEDIAN is ₹515 (positive) and its mean is ₹326 too — the would-block set is net-POSITIVE, so the gate would suppress a profitable cohort outright; [win_rate] would-block wins MORE often than eligible (58% vs 47%) — the gate is suppressing the higher-win-rate cohort. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).


### Evidence of record — liquidity gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 174 | 19 | ₹326 | ₹515 | ₹779 | 58% |
| eligible (kept) | 385 | 76 | ₹-236 | ₹-68 | ₹225 | 47% |

**Shared guards:**
- ✅ `side_proxy` — the partition is not explained by side alone
- 🚫 `tail` — would-block MEDIAN is ₹515 (positive) and its mean is ₹326 too — the would-block set is net-POSITIVE, so the gate would suppress a profitable cohort outright
- 🚫 `win_rate` — would-block wins MORE often than eligible (58% vs 47%) — the gate is suppressing the higher-win-rate cohort

- **eligible set (the book a flip would leave you holding) — deflated Sharpe bar:** ⏳ does NOT clear — observed Sharpe -0.102 does not exceed the 20-trial benchmark +0.218 — more data cannot rescue it; the candidate is not ahead
  - n=76 · mean -236.2192 · sd 2324.6757 · **Sharpe -0.102** · skew +0.09 · kurtosis 3.81
  - P(true Sharpe > 0) = 19.1% · **after deflating for 20 trials: 0.3%** (bar 95%)
  - ⚠ trials are treated as INDEPENDENT; ours overlap (same book, shared cohorts), so the true deflation is WORSE than shown — this number is optimistic.

## Per-entry context (each committed signal's liquidity)

| date | stock | side | median ₹/day | liquidity | outcome |
|---|---|---|--:|---|--:|
| 2026-09-04 | AAATECH | SHORT | ₹1,256,714 | 🚫 illiquid | open/none |
| 2026-09-04 | PRESTIGE | SHORT | ₹697,659,632 | ✅ liquid | open/none |
| 2026-09-04 | CASTROLIND | LONG | ₹238,192,633 | ✅ liquid | open/none |
| 2026-09-04 | HILINFRA | SHORT | ₹2,731,714 | 🚫 illiquid | open/none |
| 2026-09-04 | KIRLOSBROS | SHORT | ₹65,383,659 | ✅ liquid | open/none |
| 2026-09-04 | LALPATHLAB | SHORT | ₹357,246,392 | ✅ liquid | open/none |
| 2026-09-04 | CASTROLIND | LONG | ₹238,192,633 | ✅ liquid | open/none |
| 2026-09-03 | CYBERMEDIA | LONG | ₹496,271 | 🚫 illiquid | open/none |
| 2026-09-03 | TCS | SHORT | ₹5,223,114,678 | ✅ liquid | open/none |
| 2026-09-03 | MASKINVEST | SHORT | ₹4,123 | 🚫 illiquid | open/none |
| 2026-09-03 | MANAKCOAT | SHORT | ₹47,390,431 | ✅ liquid | open/none |
| 2026-09-03 | CYBERMEDIA | LONG | ₹496,271 | 🚫 illiquid | open/none |
| 2026-09-03 | TCS | SHORT | ₹5,223,114,678 | ✅ liquid | open/none |
| 2026-09-02 | BCPL | SHORT | ₹460,277 | 🚫 illiquid | open/none |
| 2026-09-01 | FUSION | SHORT | ₹128,735,097 | ✅ liquid | open/none |
| 2026-09-01 | AMBIKCO | SHORT | ₹22,854,385 | ✅ liquid | open/none |
| 2026-09-01 | MUKANDLTD | SHORT | ₹10,816,045 | ✅ liquid | open/none |
| 2026-09-01 | HEXT | SHORT | ₹114,825,986 | ✅ liquid | open/none |
| 2026-09-01 | MAHLOG | SHORT | ₹52,606,742 | ✅ liquid | open/none |
| 2026-08-31 | NOCIL | LONG | ₹57,002,244 | ✅ liquid | open/none |
| 2026-08-31 | SUPREMEIND | SHORT | ₹580,288,965 | ✅ liquid | open/none |
| 2026-08-31 | SHRINGARMS | SHORT | ₹106,075,910 | ✅ liquid | open/none |
| 2026-08-31 | GRPLTD | SHORT | ₹2,771,499 | 🚫 illiquid | open/none |
| 2026-08-31 | PNGJL | SHORT | ₹267,493,655 | ✅ liquid | open/none |
| 2026-08-31 | NOCIL | LONG | ₹57,002,244 | ✅ liquid | open/none |
| 2026-08-28 | PIDILITIND | SHORT | ₹1,189,371,643 | ✅ liquid | open/none |
| 2026-08-27 | ASHIMASYN | LONG | ₹1,481,036 | 🚫 illiquid | open/none |
| 2026-08-27 | IMAGICAA | LONG | ₹39,407,193 | ✅ liquid | open/none |
| 2026-08-27 | VRLLOG | LONG | ₹61,363,329 | ✅ liquid | open/none |
| 2026-08-27 | DELHIVERY | LONG | ₹856,534,721 | ✅ liquid | open/none |
| 2026-08-27 | NEPHROPLUS | LONG | ₹98,431,988 | ✅ liquid | open/none |
| 2026-08-27 | BLIL | LONG | ₹3,402,566 | 🚫 illiquid | open/none |
| 2026-08-27 | DELHIVERY | LONG | ₹856,534,721 | ✅ liquid | open/none |
| 2026-08-27 | VRLLOG | LONG | ₹61,363,329 | ✅ liquid | open/none |
| 2026-08-27 | WALCHANNAG | LONG | ₹131,970,099 | ✅ liquid | open/none |
| 2026-08-27 | LICHSGFIN | LONG | ₹1,031,064,367 | ✅ liquid | open/none |
| 2026-08-27 | CCL | LONG | ₹161,412,404 | ✅ liquid | open/none |
| 2026-08-27 | ADANIPORTS | LONG | ₹2,824,899,748 | ✅ liquid | open/none |
| 2026-08-27 | MSPL | LONG | ₹24,756,554 | ✅ liquid | open/none |
| 2026-08-27 | PREMIERENE | LONG | ₹622,444,772 | ✅ liquid | open/none |
| 2026-08-27 | SINCLAIR | LONG | ₹1,213,889 | 🚫 illiquid | open/none |
| 2026-08-27 | WENDT | LONG | ₹40,672,749 | ✅ liquid | open/none |
| 2026-08-27 | IMAGICAA | LONG | ₹39,407,193 | ✅ liquid | open/none |
| 2026-08-27 | PICCADIL | LONG | ₹193,778,470 | ✅ liquid | open/none |
| 2026-08-27 | ASHIMASYN | LONG | ₹1,481,036 | 🚫 illiquid | open/none |
| 2026-08-27 | ANTELOPUS | LONG | ₹106,176,700 | ✅ liquid | open/none |
| 2026-08-27 | BETA | LONG | ₹60,851,780 | ✅ liquid | open/none |
| 2026-08-27 | KKCL | LONG | ₹17,263,273 | ✅ liquid | open/none |
| 2026-08-27 | RELIGARE | LONG | ₹195,928,323 | ✅ liquid | open/none |
| 2026-08-26 | IDBI | LONG | ₹253,751,747 | ✅ liquid | ₹-2,331 |

_… 509 more assessable signals not shown._


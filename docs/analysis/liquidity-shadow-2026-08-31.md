# Liquidity shadow (live signals) — 2026-08-31

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (540 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 168 | 17 | ₹986 | ₹58 | 53% |
| liquid (eligible) | 372 | 65 | ₹-7,558 | ₹-116 | 52% |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — 17/20 resolved illiquid trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).

## Per-entry context (each committed signal's liquidity)

| date | stock | side | median ₹/day | liquidity | outcome |
|---|---|---|--:|---|--:|
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
| 2026-08-26 | IDBI | LONG | ₹253,751,747 | ✅ liquid | open/none |
| 2026-08-26 | ROSSELLIND | LONG | ₹1,283,147 | 🚫 illiquid | open/none |
| 2026-08-26 | ORIENTELEC | LONG | ₹38,905,247 | ✅ liquid | open/none |
| 2026-08-26 | KIRIINDUS | LONG | ₹135,703,302 | ✅ liquid | open/none |
| 2026-08-26 | GENCON | LONG | ₹9,780,148 | 🚫 illiquid | open/none |
| 2026-08-26 | RAMRAT | LONG | ₹88,555,722 | ✅ liquid | open/none |
| 2026-08-26 | AXISBANK | LONG | ₹6,190,866,562 | ✅ liquid | open/none |
| 2026-08-26 | GPPL | LONG | ₹198,152,833 | ✅ liquid | open/none |
| 2026-08-26 | SATIN | LONG | ₹71,729,142 | ✅ liquid | open/none |
| 2026-08-26 | CERA | LONG | ₹37,374,850 | ✅ liquid | open/none |
| 2026-08-26 | ATLANTAA | LONG | ₹1,481,143 | 🚫 illiquid | open/none |
| 2026-08-26 | GRINFRA | LONG | ₹16,435,144 | ✅ liquid | open/none |
| 2026-08-26 | BOSCH-HCIL | LONG | ₹111,860,712 | ✅ liquid | open/none |
| 2026-08-26 | GPPL | LONG | ₹198,152,833 | ✅ liquid | open/none |
| 2026-08-26 | RELTD | LONG | ₹28,222,081 | ✅ liquid | ₹-3,137 |
| 2026-08-26 | SEIL | LONG | ₹55,004,658 | ✅ liquid | open/none |
| 2026-08-26 | AXISBANK | LONG | ₹6,190,866,562 | ✅ liquid | open/none |
| 2026-08-26 | KOVAI | LONG | ₹22,942,988 | ✅ liquid | open/none |
| 2026-08-26 | RAMRAT | LONG | ₹88,555,722 | ✅ liquid | open/none |
| 2026-08-26 | GENCON | LONG | ₹9,780,148 | 🚫 illiquid | open/none |

_… 490 more assessable signals not shown._


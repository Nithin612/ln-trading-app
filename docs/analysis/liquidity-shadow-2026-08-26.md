# Liquidity shadow (live signals) — 2026-08-26

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (510 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 163 | 16 | ₹-525 | ₹-33 | 50% |
| liquid (eligible) | 347 | 59 | ₹-7,661 | ₹-130 | 53% |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — 16/20 resolved illiquid trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).

## Per-entry context (each committed signal's liquidity)

| date | stock | side | median ₹/day | liquidity | outcome |
|---|---|---|--:|---|--:|
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
| 2026-08-26 | RELTD | LONG | ₹28,222,081 | ✅ liquid | open/none |
| 2026-08-26 | SEIL | LONG | ₹55,004,658 | ✅ liquid | open/none |
| 2026-08-26 | AXISBANK | LONG | ₹6,190,866,562 | ✅ liquid | open/none |
| 2026-08-26 | KOVAI | LONG | ₹22,942,988 | ✅ liquid | open/none |
| 2026-08-26 | RAMRAT | LONG | ₹88,555,722 | ✅ liquid | open/none |
| 2026-08-26 | GENCON | LONG | ₹9,780,148 | 🚫 illiquid | open/none |
| 2026-08-26 | LOVABLE | LONG | ₹446,284 | 🚫 illiquid | open/none |
| 2026-08-26 | CORONA | LONG | ₹47,471,765 | ✅ liquid | open/none |
| 2026-08-26 | SMCGLOBAL | LONG | ₹33,346,493 | ✅ liquid | open/none |
| 2026-08-26 | STAR | LONG | ₹215,053,030 | ✅ liquid | open/none |
| 2026-08-26 | KIRIINDUS | LONG | ₹135,703,302 | ✅ liquid | open/none |
| 2026-08-26 | ENIL | LONG | ₹4,187,935 | 🚫 illiquid | open/none |
| 2026-08-26 | PRSMJOHNSN | LONG | ₹39,561,024 | ✅ liquid | open/none |
| 2026-08-26 | CMPDI | LONG | ₹281,344,956 | ✅ liquid | open/none |
| 2026-08-26 | ORIENTELEC | LONG | ₹38,905,247 | ✅ liquid | open/none |
| 2026-08-26 | ROSSELLIND | LONG | ₹1,283,147 | 🚫 illiquid | open/none |
| 2026-08-26 | ORKLAINDIA | LONG | ₹50,549,458 | ✅ liquid | open/none |
| 2026-08-26 | RAJPALAYAM | LONG | ₹979,410 | 🚫 illiquid | open/none |
| 2026-08-26 | IDBI | LONG | ₹253,751,747 | ✅ liquid | open/none |
| 2026-08-25 | BAJAJHLDNG | LONG | ₹388,713,750 | ✅ liquid | open/none |
| 2026-08-25 | OBCL | LONG | ₹508,304 | 🚫 illiquid | open/none |
| 2026-08-25 | BVCL | LONG | ₹672,679 | 🚫 illiquid | open/none |
| 2026-08-25 | FMGOETZE | LONG | ₹19,731,542 | ✅ liquid | open/none |
| 2026-08-25 | GOKULAGRO | LONG | ₹132,936,010 | ✅ liquid | open/none |
| 2026-08-25 | ABMKNO | LONG | ₹208,447 | 🚫 illiquid | open/none |
| 2026-08-25 | COCHINSHIP | SHORT | ₹1,249,726,260 | ✅ liquid | open/none |
| 2026-08-25 | SHREDIGCEM | LONG | ₹4,454,135 | 🚫 illiquid | open/none |
| 2026-08-25 | CDSL | LONG | ₹1,216,432,430 | ✅ liquid | open/none |
| 2026-08-25 | MOSCHIP | SHORT | ₹224,051,116 | ✅ liquid | open/none |
| 2026-08-25 | GLOBUSSPR | LONG | ₹64,439,162 | ✅ liquid | open/none |
| 2026-08-25 | AUROPHARMA | LONG | ₹1,448,415,452 | ✅ liquid | open/none |
| 2026-08-25 | GOKULAGRO | LONG | ₹132,936,010 | ✅ liquid | open/none |
| 2026-08-25 | FMGOETZE | LONG | ₹19,731,542 | ✅ liquid | open/none |
| 2026-08-25 | BVCL | LONG | ₹672,679 | 🚫 illiquid | open/none |
| 2026-08-25 | DBCORP | SHORT | ₹15,043,667 | ✅ liquid | open/none |
| 2026-08-25 | PRIMESECU | LONG | ₹5,053,184 | 🚫 illiquid | open/none |

_… 460 more assessable signals not shown._


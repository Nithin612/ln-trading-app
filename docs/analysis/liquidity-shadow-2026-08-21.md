# Liquidity shadow (live signals) — 2026-08-21

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (417 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 132 | 14 | ₹1,667 | ₹119 | 50% |
| liquid (eligible) | 285 | 57 | ₹-8,414 | ₹-148 | 53% |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — 14/20 resolved illiquid trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).

## Per-entry context (each committed signal's liquidity)

| date | stock | side | median ₹/day | liquidity | outcome |
|---|---|---|--:|---|--:|
| 2026-08-21 | GUJTHEM | LONG | ₹13,238,395 | ✅ liquid | open/none |
| 2026-08-21 | BENGALASM | LONG | ₹1,266,162 | 🚫 illiquid | open/none |
| 2026-08-21 | GUJTHEM | LONG | ₹13,238,395 | ✅ liquid | open/none |
| 2026-08-19 | TFCILTD | LONG | ₹1,927,708,135 | ✅ liquid | open/none |
| 2026-08-19 | YUKEN | LONG | ₹5,866,186 | 🚫 illiquid | open/none |
| 2026-08-19 | KALYANIFRG | LONG | ₹1,422,673 | 🚫 illiquid | open/none |
| 2026-08-19 | KALYANIFRG | LONG | ₹1,422,673 | 🚫 illiquid | open/none |
| 2026-08-19 | YUKEN | LONG | ₹5,866,186 | 🚫 illiquid | open/none |
| 2026-08-19 | ZENITHEXPO | LONG | ₹50,992 | 🚫 illiquid | open/none |
| 2026-08-19 | TFCILTD | LONG | ₹1,927,708,135 | ✅ liquid | open/none |
| 2026-08-18 | JTLIND | SHORT | ₹116,041,823 | ✅ liquid | open/none |
| 2026-08-18 | CUMMINSIND | SHORT | ₹1,915,078,680 | ✅ liquid | open/none |
| 2026-08-17 | SOUTHBANK | SHORT | ₹361,727,211 | ✅ liquid | open/none |
| 2026-08-14 | BPCL | LONG | ₹1,771,861,413 | ✅ liquid | open/none |
| 2026-08-14 | HATSUN | LONG | ₹33,248,044 | ✅ liquid | open/none |
| 2026-08-14 | GROBTEA | LONG | ₹97,737 | 🚫 illiquid | open/none |
| 2026-08-14 | MARUTI | SHORT | ₹4,661,817,494 | ✅ liquid | open/none |
| 2026-08-14 | MCLOUD | SHORT | ₹60,811,136 | ✅ liquid | open/none |
| 2026-08-14 | LTTS | SHORT | ₹334,690,799 | ✅ liquid | open/none |
| 2026-08-14 | SEIL | LONG | ₹43,987,308 | ✅ liquid | open/none |
| 2026-08-14 | AERONEU | LONG | ₹4,146,205 | 🚫 illiquid | open/none |
| 2026-08-14 | MARUTI | SHORT | ₹4,661,817,494 | ✅ liquid | open/none |
| 2026-08-14 | RELIABLE | SHORT | ₹1,974,088 | 🚫 illiquid | open/none |
| 2026-08-14 | PREMIERENE | SHORT | ₹807,750,750 | ✅ liquid | ₹-2,257 |
| 2026-08-14 | RITES | SHORT | ₹103,244,505 | ✅ liquid | open/none |
| 2026-08-14 | KOVAI | LONG | ₹20,003,432 | ✅ liquid | open/none |
| 2026-08-14 | IMAGICAA | LONG | ₹28,909,556 | ✅ liquid | open/none |
| 2026-08-14 | INDIAMART | SHORT | ₹271,118,206 | ✅ liquid | open/none |
| 2026-08-14 | LEMERITE | SHORT | ₹8,772,313 | 🚫 illiquid | open/none |
| 2026-08-14 | STUDDS | SHORT | ₹16,491,262 | ✅ liquid | open/none |
| 2026-08-14 | KSL | SHORT | ₹20,878,877 | ✅ liquid | ₹-2,278 |
| 2026-08-14 | AVANTEL | SHORT | ₹113,589,226 | ✅ liquid | open/none |
| 2026-08-14 | HATSUN | LONG | ₹33,248,044 | ✅ liquid | open/none |
| 2026-08-14 | DONEAR | LONG | ₹909,489 | 🚫 illiquid | open/none |
| 2026-08-14 | SKIPPER | SHORT | ₹257,172,066 | ✅ liquid | open/none |
| 2026-08-14 | BPCL | LONG | ₹1,771,861,413 | ✅ liquid | open/none |
| 2026-08-14 | CGCL | LONG | ₹588,891,163 | ✅ liquid | open/none |
| 2026-08-13 | TEJASNET | LONG | ₹642,912,022 | ✅ liquid | open/none |
| 2026-08-13 | TARMAT | LONG | ₹478,526 | 🚫 illiquid | open/none |
| 2026-08-13 | PODDARMENT | LONG | ₹1,704,673 | 🚫 illiquid | open/none |
| 2026-08-13 | GRSE | LONG | ₹843,128,971 | ✅ liquid | open/none |
| 2026-08-13 | UCAL | LONG | ₹732,149 | 🚫 illiquid | open/none |
| 2026-08-13 | BEL | LONG | ₹4,097,413,788 | ✅ liquid | open/none |
| 2026-08-13 | BAJFINANCE | SHORT | ₹8,013,998,929 | ✅ liquid | open/none |
| 2026-08-13 | BEL | LONG | ₹4,097,413,788 | ✅ liquid | open/none |
| 2026-08-13 | 3PLAND | LONG | ₹77,160 | 🚫 illiquid | open/none |
| 2026-08-13 | APLLTD | SHORT | ₹59,807,561 | ✅ liquid | open/none |
| 2026-08-13 | VISHWARAJ | LONG | ₹765,767 | 🚫 illiquid | open/none |
| 2026-08-13 | MODTHREAD | LONG | ₹35,235 | 🚫 illiquid | open/none |
| 2026-08-13 | GMDCLTD | SHORT | ₹518,070,581 | ✅ liquid | open/none |

_… 367 more assessable signals not shown._


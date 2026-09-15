# Liquidity shadow (live signals) — 2026-08-24

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (452 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 145 | 15 | ₹-1,804 | ₹-120 | 47% |
| liquid (eligible) | 307 | 57 | ₹-8,414 | ₹-148 | 53% |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — 15/20 resolved illiquid trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).

## Per-entry context (each committed signal's liquidity)

| date | stock | side | median ₹/day | liquidity | outcome |
|---|---|---|--:|---|--:|
| 2026-08-24 | GOKUL | LONG | ₹5,878,797 | 🚫 illiquid | open/none |
| 2026-08-24 | ADROITINFO | LONG | ₹282,753 | 🚫 illiquid | open/none |
| 2026-08-24 | AJAXENGG | LONG | ₹25,982,648 | ✅ liquid | open/none |
| 2026-08-24 | 20MICRONS | LONG | ₹25,643,540 | ✅ liquid | open/none |
| 2026-08-24 | DVL | LONG | ₹4,899,221 | 🚫 illiquid | open/none |
| 2026-08-24 | RICOAUTO | LONG | ₹239,764,909 | ✅ liquid | open/none |
| 2026-08-24 | EMKAY | LONG | ₹4,615,611 | 🚫 illiquid | open/none |
| 2026-08-24 | HIRECT | LONG | ₹113,817,750 | ✅ liquid | open/none |
| 2026-08-24 | 21STCENMGM | LONG | ₹396,010 | 🚫 illiquid | open/none |
| 2026-08-24 | STARPAPER | LONG | ₹1,234,979 | 🚫 illiquid | open/none |
| 2026-08-24 | ZYDUSLIFE | LONG | ₹1,110,439,726 | ✅ liquid | open/none |
| 2026-08-24 | WELSPLSOL | LONG | ₹12,879,719 | ✅ liquid | open/none |
| 2026-08-24 | MARICO | LONG | ₹1,190,403,906 | ✅ liquid | open/none |
| 2026-08-24 | DVL | LONG | ₹4,899,221 | 🚫 illiquid | open/none |
| 2026-08-24 | ASHOKLEY | LONG | ₹2,516,873,587 | ✅ liquid | open/none |
| 2026-08-24 | BHARTIHEXA | LONG | ₹184,755,236 | ✅ liquid | open/none |
| 2026-08-24 | TIPSMUSIC | LONG | ₹140,378,617 | ✅ liquid | open/none |
| 2026-08-24 | ACCURACY | LONG | ₹492,276 | 🚫 illiquid | open/none |
| 2026-08-24 | 20MICRONS | LONG | ₹25,643,540 | ✅ liquid | open/none |
| 2026-08-24 | AYE | LONG | ₹70,725,793 | ✅ liquid | open/none |
| 2026-08-24 | BORANA | LONG | ₹8,630,449 | 🚫 illiquid | open/none |
| 2026-08-24 | AJAXENGG | LONG | ₹25,982,648 | ✅ liquid | open/none |
| 2026-08-24 | SHIVATEX | LONG | ₹411,406 | 🚫 illiquid | open/none |
| 2026-08-24 | KIRLOSIND | LONG | ₹15,252,147 | ✅ liquid | open/none |
| 2026-08-24 | TRAVELFOOD | LONG | ₹51,788,411 | ✅ liquid | open/none |
| 2026-08-24 | CGPOWER | LONG | ₹1,703,432,758 | ✅ liquid | open/none |
| 2026-08-24 | SAIPARENT | LONG | ₹50,554,617 | ✅ liquid | open/none |
| 2026-08-24 | BIOCON | LONG | ₹1,357,951,281 | ✅ liquid | open/none |
| 2026-08-24 | ADROITINFO | LONG | ₹282,753 | 🚫 illiquid | open/none |
| 2026-08-24 | ARKADE | LONG | ₹48,043,764 | ✅ liquid | open/none |
| 2026-08-24 | CAPITALSFB | LONG | ₹5,613,554 | 🚫 illiquid | open/none |
| 2026-08-24 | GOKUL | LONG | ₹5,878,797 | 🚫 illiquid | open/none |
| 2026-08-24 | ALGOQUANT | LONG | ₹74,070,028 | ✅ liquid | open/none |
| 2026-08-24 | KIRLFER | LONG | ₹28,192,755 | ✅ liquid | open/none |
| 2026-08-24 | GRAUWEIL | LONG | ₹14,066,397 | ✅ liquid | open/none |
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

_… 402 more assessable signals not shown._


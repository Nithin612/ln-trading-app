# Liquidity shadow (live signals) — 2026-08-25

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (477 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 155 | 15 | ₹-1,804 | ₹-120 | 47% |
| liquid (eligible) | 322 | 59 | ₹-7,661 | ₹-130 | 53% |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — 15/20 resolved illiquid trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).

## Per-entry context (each committed signal's liquidity)

| date | stock | side | median ₹/day | liquidity | outcome |
|---|---|---|--:|---|--:|
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
| 2026-08-25 | OBCL | LONG | ₹508,304 | 🚫 illiquid | open/none |
| 2026-08-25 | ENRIN | SHORT | ₹1,340,717,271 | ✅ liquid | open/none |
| 2026-08-25 | NIRLON | SHORT | ₹2,501,520 | 🚫 illiquid | open/none |
| 2026-08-25 | BAJAJHLDNG | LONG | ₹388,713,750 | ✅ liquid | open/none |
| 2026-08-25 | KIRLOSENG | LONG | ₹796,953,437 | ✅ liquid | open/none |
| 2026-08-25 | RAMAPHO | LONG | ₹3,667,525 | 🚫 illiquid | open/none |
| 2026-08-25 | SRTL | SHORT | ₹1,184,262 | 🚫 illiquid | open/none |
| 2026-08-25 | KSB | LONG | ₹108,498,857 | ✅ liquid | open/none |
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

_… 427 more assessable signals not shown._


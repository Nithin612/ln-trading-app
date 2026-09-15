# Portfolio-heat counterfactual — 2026-09-06

_Read-only, ENFORCES NOTHING. Replays every paper entry since 2026-08-17 against a **6.0% cap on ₹100,000** (= ₹6,000 of open risk) and reports the admitted subset beside the full book._

**Why:** the paper book is deliberately a wide evidence sampler (~5 entries/day, ~5-day holds ⇒ ~25 concurrent positions), so the **30-day profit-days clock — the go-live gate — is measuring a book that will never be traded** (live is ₹1 lakh, 1–2 positions). This is the number that gate should read.

**Method:** chronological admission — take entries as they fire while open heat stays under the cap; a close frees budget for a later entry. Admission risk uses the stop **as committed on the signal**, never the trailed `current_sl` (that would leak price action the decision could not see). Risk is clamped at zero, so a stop at/past entry consumes no budget.

**Why this replay is legitimate:** declining to ENTER changes neither the market nor which other signals fire, so the admitted trades' outcomes are exactly the outcomes they really had. (An EXIT replay cannot claim that — it has to invent a price path.)

| book | entries | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ADMITTED (capped at 6.0%) | 13 | 10 | ₹-13,641 | ₹-1,364 | 30% |
| SKIPPED (cap would have declined) | 44 | 18 | ₹537 | ₹30 | 44% |

- Peak open heat the capped book carried: **₹5,997** of the ₹6,000 cap
- Peak concurrent positions: **3** (capped) vs **31** (actual book)

**Read:** [heat counterfactual @ 6.0% of ₹100,000] admitted 13 / skipped 44 · capped ₹-13,641 vs full ₹-13,104 (-537) · per-trade ₹-1,364 vs ₹-468 — cap COSTS money — it cut into the winning tail

⚠ **Method limit worth knowing:** admission is CHRONOLOGICAL, which is faithful to watching an alert feed but selects by arrival time, not by quality — one large-risk entry can consume the whole budget alone. So a favourable TOTAL can come from simply taking fewer trades at an unchanged expectancy. Compare the per-trade figures before reading a cap as an improvement, and treat a conviction-ordered variant as the separate (better) selection test.

## Per-entry admission decisions

| opened | stock | side | risk ₹ | heat before | verdict | outcome |
|---|---|---|--:|--:|---|--:|
| 2026-08-18 | PREMIERENE | SHORT | ₹1,997 | ₹0 | ✅ admitted | ₹-2,257 |
| 2026-08-18 | KSL | SHORT | ₹1,976 | ₹1,997 | ✅ admitted | ₹-2,278 |
| 2026-08-18 | LEMERITE | SHORT | ₹2,000 | ₹3,972 | ✅ admitted | ₹1,279 |
| 2026-08-18 | SRTL | LONG | ₹2,000 | ₹5,972 | 🚫 skipped | ₹-3,565 |
| 2026-08-18 | BEL | LONG | ₹1,982 | ₹5,972 | 🚫 skipped | open |
| 2026-08-19 | GRSE | LONG | ₹1,886 | ₹5,972 | 🚫 skipped | ₹-1,996 |
| 2026-08-19 | HEROMOTOCO | LONG | ₹1,911 | ₹5,972 | 🚫 skipped | ₹-2,082 |
| 2026-08-19 | SOUTHBANK | SHORT | ₹1,997 | ₹5,972 | 🚫 skipped | open |
| 2026-08-19 | RELIABLE | SHORT | ₹1,994 | ₹5,972 | 🚫 skipped | open |
| 2026-08-19 | CGCL | LONG | ₹1,994 | ₹5,972 | 🚫 skipped | ₹2,850 |
| 2026-08-21 | ASPINWALL | LONG | ₹2,000 | ₹3,976 | ✅ admitted | ₹-3,471 |
| 2026-08-21 | PFIZER | LONG | ₹1,995 | ₹5,975 | 🚫 skipped | ₹-2,097 |
| 2026-08-21 | DMCC | LONG | ₹1,998 | ₹5,975 | 🚫 skipped | open |
| 2026-08-21 | HATSUN | LONG | ₹1,982 | ₹5,975 | 🚫 skipped | ₹6,017 |
| 2026-08-25 | EMKAY | LONG | ₹1,998 | ₹2,000 | ✅ admitted | ₹1,511 |
| 2026-08-25 | 20MICRONS | LONG | ₹1,991 | ₹3,998 | ✅ admitted | ₹832 |
| 2026-08-25 | ALGOQUANT | LONG | ₹1,998 | ₹5,988 | 🚫 skipped | ₹-2,193 |
| 2026-08-25 | CGPOWER | LONG | ₹1,967 | ₹5,988 | 🚫 skipped | open |
| 2026-08-25 | BHARTIARTL | LONG | ₹1,930 | ₹5,988 | 🚫 skipped | ₹-2,045 |
| 2026-08-26 | GOKULAGRO | LONG | ₹1,998 | ₹5,988 | 🚫 skipped | ₹-2,239 |
| 2026-08-26 | MOSCHIP | SHORT | ₹1,992 | ₹5,988 | 🚫 skipped | ₹-2,719 |
| 2026-08-26 | ADROITINFO | LONG | ₹2,000 | ₹5,988 | 🚫 skipped | open |
| 2026-08-26 | BPCL | LONG | ₹22,055 | ₹5,988 | 🚫 skipped | ₹-5,076 |
| 2026-08-26 | ENRIN | SHORT | ₹1,900 | ₹5,988 | 🚫 skipped | ₹1,199 |
| 2026-08-27 | IDBI | LONG | ₹2,000 | ₹1,998 | ✅ admitted | ₹-2,331 |
| 2026-08-27 | RELTD | LONG | ₹2,000 | ₹3,997 | ✅ admitted | ₹-3,137 |
| 2026-08-27 | GPPL | LONG | ₹1,992 | ₹5,997 | 🚫 skipped | open |
| 2026-08-27 | KSB | LONG | ₹1,977 | ₹5,997 | 🚫 skipped | ₹-409 |
| 2026-08-27 | ORKLAINDIA | LONG | ₹1,969 | ₹5,997 | 🚫 skipped | ₹1,303 |
| 2026-08-28 | BLIL | LONG | ₹1,999 | ₹3,997 | ✅ admitted | open |
| 2026-08-28 | BENGALASM | LONG | ₹1,945 | ₹5,996 | 🚫 skipped | ₹2,775 |
| 2026-08-28 | GLOBUSSPR | LONG | ₹1,989 | ₹5,996 | 🚫 skipped | open |
| 2026-08-28 | CDSL | LONG | ₹1,976 | ₹5,996 | 🚫 skipped | open |
| 2026-08-28 | PRIMESECU | LONG | ₹1,999 | ₹5,996 | 🚫 skipped | ₹2,440 |
| 2026-08-31 | KIRIINDUS | LONG | ₹5,682 | ₹5,996 | 🚫 skipped | ₹6,621 |
| 2026-08-31 | VRLLOG | LONG | ₹1,990 | ₹5,996 | 🚫 skipped | open |
| 2026-08-31 | LOVABLE | LONG | ₹1,998 | ₹5,996 | 🚫 skipped | open |
| 2026-08-31 | BVCL | LONG | ₹1,998 | ₹5,996 | 🚫 skipped | open |
| 2026-08-31 | PIDILITIND | SHORT | ₹1,956 | ₹5,996 | 🚫 skipped | open |
| 2026-09-01 | AJAXENGG | LONG | ₹1,998 | ₹3,998 | ✅ admitted | ₹-3,451 |
| 2026-09-01 | NOCIL | LONG | ₹2,899 | ₹5,997 | 🚫 skipped | open |
| 2026-09-01 | DVL | LONG | ₹1,990 | ₹5,997 | 🚫 skipped | open |
| 2026-09-02 | POLYMED | LONG | ₹2,146 | ₹1,999 | ✅ admitted | ₹-338 |
| 2026-09-02 | TEJASNET | LONG | ₹1,991 | ₹4,144 | 🚫 skipped | open |
| 2026-09-02 | MUKANDLTD | SHORT | ₹1,998 | ₹4,144 | 🚫 skipped | open |
| 2026-09-02 | BOSCH-HCIL | LONG | ₹1,915 | ₹4,144 | 🚫 skipped | ₹1,751 |
| 2026-09-02 | MAHLOG | SHORT | ₹1,986 | ₹4,144 | 🚫 skipped | open |
| 2026-09-03 | BPCL | LONG | ₹1,989 | ₹4,144 | 🚫 skipped | open |
| 2026-09-03 | SHRINGARMS | SHORT | ₹1,994 | ₹4,144 | 🚫 skipped | open |
| 2026-09-03 | SUPREMEIND | SHORT | ₹1,895 | ₹4,144 | 🚫 skipped | open |
| 2026-09-03 | FUSION | SHORT | ₹1,991 | ₹4,144 | 🚫 skipped | open |
| 2026-09-03 | PREMIERENE | LONG | ₹1,982 | ₹4,144 | 🚫 skipped | open |
| 2026-09-04 | GARUDA | LONG | ₹1,994 | ₹1,999 | ✅ admitted | open |
| 2026-09-04 | AJAXENGG | LONG | ₹1,965 | ₹3,993 | ✅ admitted | open |
| 2026-09-04 | TCS | SHORT | ₹1,973 | ₹5,958 | 🚫 skipped | open |
| 2026-09-04 | BAJAJHLDNG | LONG | ₹1,555 | ₹5,958 | 🚫 skipped | open |
| 2026-09-04 | TNPL | LONG | ₹1,997 | ₹5,958 | 🚫 skipped | open |

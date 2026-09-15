# Portfolio-heat counterfactual — 2026-09-05

_Read-only, ENFORCES NOTHING. Replays every paper entry since 2026-07-19 against a **6.0% cap on ₹100,000** (= ₹6,000 of open risk) and reports the admitted subset beside the full book._

**Why:** the paper book is deliberately a wide evidence sampler (~5 entries/day, ~5-day holds ⇒ ~25 concurrent positions), so the **30-day profit-days clock — the go-live gate — is measuring a book that will never be traded** (live is ₹1 lakh, 1–2 positions). This is the number that gate should read.

**Method:** chronological admission — take entries as they fire while open heat stays under the cap; a close frees budget for a later entry. Admission risk uses the stop **as committed on the signal**, never the trailed `current_sl` (that would leak price action the decision could not see). Risk is clamped at zero, so a stop at/past entry consumes no budget.

**Why this replay is legitimate:** declining to ENTER changes neither the market nor which other signals fire, so the admitted trades' outcomes are exactly the outcomes they really had. (An EXIT replay cannot claim that — it has to invent a price path.)

| book | entries | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ADMITTED (capped at 6.0%) | 0 | 0 | ₹0 | — | — |
| SKIPPED (cap would have declined) | 0 | 0 | ₹0 | — | — |

- Peak open heat the capped book carried: **₹0** of the ₹6,000 cap
- Peak concurrent positions: **0** (capped) vs **0** (actual book)

**Read:** [heat counterfactual @ 6.0% of ₹100,000] admitted 0 / skipped 0 · capped ₹0 vs full ₹0 (+0) · per-trade ₹0 vs ₹0 — neutral

⚠ **Method limit worth knowing:** admission is CHRONOLOGICAL, which is faithful to watching an alert feed but selects by arrival time, not by quality — one large-risk entry can consume the whole budget alone. So a favourable TOTAL can come from simply taking fewer trades at an unchanged expectancy. Compare the per-trade figures before reading a cap as an improvement, and treat a conviction-ordered variant as the separate (better) selection test.


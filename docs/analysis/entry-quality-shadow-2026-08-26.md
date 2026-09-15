# Entry-quality shadow (live signals) — 2026-08-26

_Read-only. The entry-quality overlay over the tradeable signal cohort since 2026-07-19 (510 signals). **diversity** is ACTIVE (the ≥2-factor hard rule — single-factor signals no longer enter); **sl_atr** is SHADOW (measured only). A flagged set net-negative and worse than passed is the evidence to flip sl_atr active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| diversity FLAGGED (blocked live) | 68 | 9 | ₹-6,093 | ₹-677 | 44% |
| diversity passed | 442 | 66 | ₹-2,093 | ₹-32 | 53% |
| sl_atr FLAGGED (shadow) | 110 | 13 | ₹-12,658 | ₹-974 | 46% |
| sl_atr passed | 400 | 62 | ₹4,472 | ₹72 | 53% |

**sl_atr flip readiness:** ⏳ NOT READY — 13/20 resolved sl-flagged trades — keep accruing. Flipping sl_atr active also needs explicit user sign-off (behaviour-changing, reversible via `entry_sl_atr_gate_mode=shadow`).

_diversity is active by user sign-off (2026-08-18, the SRTL loss) — enforcing the stated 'never a single indicator' rule, so its flagged set no longer trades live._


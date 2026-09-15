# Entry-quality shadow (live signals) — 2026-09-02

_Read-only. The entry-quality overlay over the tradeable signal cohort since 2026-07-19 (546 signals). **diversity** is ACTIVE (the ≥2-factor hard rule — single-factor signals do not enter while it is active); **sl_atr** is SHADOW (a tunable stop-tightness floor). A flagged set net-negative and worse than passed is the evidence to flip sl_atr active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| diversity FLAGGED (blocked live) | 74 | 9 | ₹-6,093 | ₹-677 | 44% |
| diversity passed | 472 | 82 | ₹-11,648 | ₹-142 | 50% |
| sl_atr FLAGGED (shadow) | 123 | 17 | ₹-18,998 | ₹-1,118 | 41% |
| sl_atr passed | 423 | 74 | ₹1,257 | ₹17 | 51% |

**sl_atr flip readiness:** ⏳ NOT READY — 17/20 resolved sl-flagged trades — keep accruing. Flipping sl_atr active also needs explicit user sign-off (behaviour-changing, reversible via `entry_sl_atr_gate_mode=shadow`).

_diversity is active by user sign-off (2026-08-18, the SRTL loss) — enforcing the stated 'never a single indicator' rule, so its flagged set no longer trades live._


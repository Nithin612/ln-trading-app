# Entry-quality shadow (live signals) — 2026-09-05

_Read-only. The entry-quality overlay over the tradeable signal cohort since 2026-07-19 (0 signals). **diversity** is ACTIVE (the ≥2-factor hard rule — single-factor signals do not enter while it is active); **sl_atr** is SHADOW (a tunable stop-tightness floor). A flagged set net-negative and worse than passed is the evidence to flip sl_atr active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| diversity FLAGGED (blocked live) | 0 | 0 | — | — | — |
| diversity passed | 0 | 0 | — | — | — |
| sl_atr FLAGGED (shadow) | 0 | 0 | — | — | — |
| sl_atr passed | 0 | 0 | — | — | — |

**sl_atr flip readiness:** ⏳ NOT READY — 0/20 resolved sl-flagged trades — keep accruing. Flipping sl_atr active also needs explicit user sign-off (behaviour-changing, reversible via `entry_sl_atr_gate_mode=shadow`).

_diversity is active by user sign-off (2026-08-18, the SRTL loss) — enforcing the stated 'never a single indicator' rule, so its flagged set no longer trades live._


### Evidence of record — entry-quality sl_atr rung

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 0 | 0 | — | — | — | — |
| eligible (kept) | 0 | 0 | — | — | — | — |

**Shared guards:**
- ✅ `side_proxy` — one side of the partition is empty — not assessable
- ✅ `tail` — only 0 resolved would-block trades — not assessable
- ✅ `win_rate` — a side of the partition has no resolved trades

- **deflated Sharpe:** no resolved eligible trades yet


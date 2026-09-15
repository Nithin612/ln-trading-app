# Entry-quality shadow (live signals) — 2026-09-03

_Read-only. The entry-quality overlay over the tradeable signal cohort since 2026-07-19 (552 signals). **diversity** is ACTIVE (the ≥2-factor hard rule — single-factor signals do not enter while it is active); **sl_atr** is SHADOW (a tunable stop-tightness floor). A flagged set net-negative and worse than passed is the evidence to flip sl_atr active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| diversity FLAGGED (blocked live) | 74 | 9 | ₹-6,093 | ₹-677 | 44% |
| diversity passed | 478 | 83 | ₹-11,986 | ₹-144 | 49% |
| sl_atr FLAGGED (shadow) | 124 | 17 | ₹-18,998 | ₹-1,118 | 41% |
| sl_atr passed | 428 | 75 | ₹919 | ₹12 | 51% |

**sl_atr flip readiness:** ⏳ NOT READY — 17/20 resolved sl-flagged trades — keep accruing. Flipping sl_atr active also needs explicit user sign-off (behaviour-changing, reversible via `entry_sl_atr_gate_mode=shadow`).

_diversity is active by user sign-off (2026-08-18, the SRTL loss) — enforcing the stated 'never a single indicator' rule, so its flagged set no longer trades live._


### Evidence of record — entry-quality sl_atr rung

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 124 | 17 | ₹-1,118 | ₹-2,221 | ₹-545 | 41% |
| eligible (kept) | 428 | 75 | ₹12 | ₹16 | ₹395 | 51% |

**Shared guards:**
- ✅ `side_proxy` — the partition is not explained by side alone
- ✅ `tail` — the would-block set stays net-negative after trimming the tail
- ✅ `win_rate` — would-block win rate 41% ≤ eligible 51%

- **eligible set (the book a flip would leave you holding) — deflated Sharpe bar:** ⏳ does NOT clear — observed Sharpe +0.006 does not exceed the 20-trial benchmark +0.219 — more data cannot rescue it; the candidate is not ahead
  - n=75 · mean +12.2520 · sd 1893.9013 · **Sharpe +0.006** · skew -0.02 · kurtosis 3.84
  - P(true Sharpe > 0) = 52.2% · **after deflating for 20 trials: 3.3%** (bar 95%)
  - ⚠ trials are treated as INDEPENDENT; ours overlap (same book, shared cohorts), so the true deflation is WORSE than shown — this number is optimistic.


# Liquidity shadow (live signals) — 2026-09-07

_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since 2026-07-19 (0 signals), each judged on its stock's median daily traded value (₹ = close × volume) over 20 sessions as of its decision time (no look-ahead). Gate mode: **shadow**. 'illiquid' = median below the ₹10,000,000 floor — too thin to exit safely, either side (the SRTL archetype). A would-block set net-negative AND worse than the liquid set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| ILLIQUID (< ₹10,000,000/day, would-block) | 0 | 0 | — | — | — |
| liquid (eligible) | 0 | 0 | — | — | — |
| no data (< 20 sessions) | 0 | 0 | — | — | — |

**liquidity flip readiness:** ⏳ NOT READY — 0/20 resolved illiquid trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `liquidity_gate_mode=shadow`).

_No signals had ≥ lookback sessions of history yet._


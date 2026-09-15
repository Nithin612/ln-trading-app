# Sector/index relative-strength shadow (live signals) — 2026-09-05

_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since 2026-07-19 (0 signals), benchmark closes aligned to each signal's decision time (no look-ahead). Gate mode: **shadow**. A signal is 'would-block' when it UNDER-performs its benchmark index (a short: out-performs) by more than `sector_rs_min_excess_pct` (0.0%) over 20 sessions. 'no benchmark data' = index history not deep enough yet (fails open live). A would-block set net-negative AND worse than the eligible set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| would-BLOCK (RS against the side) | 0 | 0 | — | — | — |
| eligible (RS in favour of the side) | 0 | 0 | — | — | — |
| no benchmark data (fails open) | 0 | 0 | — | — | — |

**sector-RS flip readiness:** ⏳ NOT READY — 0/20 resolved would-block trades — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user sign-off (reversible via `sector_rs_gate_mode=shadow`).

_No signals had benchmark history yet — index OHLC still backfilling._


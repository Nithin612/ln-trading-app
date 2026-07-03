---
name: signal-audit
description: Deep end-to-end verification of one strategy profile or factor against SIGNAL_ENGINE.md — formulas, weights, levels, validity, sizing, plus a metrics comparison. Load when the user questions a signal ("why did/didn't X fire?"), after tuning weights, or before promoting a profile.
---

# Signal audit

Answers, with evidence: "is this signal/profile behaving exactly as
specified — and is it earning its place?"

## Procedure

1. **Scope.** Name the profile/factor/signal under audit and pull its exact
   spec lines from docs/SIGNAL_ENGINE.md (quote them).
2. **Trace one real evaluation.** Pick a concrete stock + timestamp (from
   the user's question, or the latest fired/near-miss signal in the DB).
   Load the exact candle window the engine saw
   (`is_complete = true`, last-300 canon) and recompute by hand:
   - each factor's inputs → score → weight × score,
   - total weighted / total active weight → normalized → `int()` confidence,
   - classification, SL/TP placement, cap check, qty.
   Do it in a scratch script with `uv run python` and SHOW the arithmetic
   next to the stored `factor_scores` JSONB. Any mismatch = finding.
3. **Boundary probes.** Test the spec's edges around the case: confidence
   69.9 vs 70.0, RSI 29.99/30.01, ADX 24.9/25.1, volume 1.49×/1.51×,
   SL just inside/outside the cap. Confirm gate behavior (reject not clamp).
4. **Look-ahead sweep.** For the code path involved: confirm compute-on-N /
   valid-from-N+1, no incomplete candles, no future rows in any window
   (check the SQL and the slicing).
5. **Metrics.** Run the profile's standing backtest; compare to its recorded
   golden (docs/phases/). If auditing a proposed change, run before/after
   and present the delta table.
6. **Verdict.** Per-factor table (spec vs code vs recomputed value, match?),
   overall PASS/FAIL, and — if the user asked "why (not) this signal" — a
   plain-language explanation citing the decisive factors and numbers.

## Rules

- Recompute; never trust stored explanations as proof.
- Spec is canon: a "sensible" deviation is still FAIL until the user amends
  the spec (protected file — they edit it or explicitly instruct).
- Every number in the report traces to a command or query shown in the
  report.

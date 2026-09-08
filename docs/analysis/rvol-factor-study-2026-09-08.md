# RVOL-factor counterfactual (D1 / R1) — 2026-09-08

> ## ⛔ VERDICT: R1-RVOL does not earn the frozen change. D1 → decline sign-off.
>
> On 1,152 baseline swing+positional signals (150 liquid names, 2023-07-03+):
> **§1 (design-free): RVOL-at-entry carries no positive outcome signal — it is mildly INVERSE.**
> The two *elevated* buckets are the worst (1.5–2.0× −0.237R, t=−1.71; ≥2.0× −0.157R), which is the
> opposite of the R1 hypothesis and exactly the region where the existing VOLUME factor fires and
> where R1-RVOL would pile on more weight.
> **§2: injecting a graded RVOL factor makes the book significantly worse** — augmented −0.095R vs
> baseline −0.026R (t=−1.91), and the 294 signals it newly admits average **−0.291R at t=−2.91**.
> Because the scorer normalizes, the factor dilutes and re-shuffles rather than adds.
> **VWAP is untestable** (no intraday data), deferrable only to forward capture.
> ⇒ No frozen-engine spec change: the existing binary VOLUME factor already captures — arguably
> over-captures — what volume confirmation is worth. **No frozen code touched, no recorded number moved.**
>
> ⚙ Reproduce: `uv run python scripts/rvol_factor_study.py --universe liquid --max-stocks 150`
> (a `--universe nifty50` re-run overwrites this file with the 5-stock sample — the liquid run is decisive).

Universe **liquid** (150 stocks) · window 2023-07-03 → today (CA-clean) · min_confidence 70. **No frozen edit / no recorded number.**

**VWAP is excluded — not backtestable (no intraday data).** The existing binary VOLUME factor already encodes RVOL at 1.5×; only the GRADED increment over it is in question.

## 1. Does RVOL-at-entry predict outcome? (baseline signals, design-agnostic)

If RVOL carries no outcome information here, NO factor design can extract edge from it. Buckets by relative volume at the decision bar.

| RVOL bucket | n | mean R | t | win% |
|---|--:|--:|--:|--:|
| <1.0× | 767 | -0.003 | -0.05 | 38 |
| 1.0–1.5× | 214 | +0.022 | +0.21 | 40 |
| 1.5–2.0× | 65 | -0.237 | -1.71 | 34 |
| ≥2.0× | 106 | -0.157 | -0.96 | 26 |

## 2. Effect of injecting a graded RVOL factor (weight 10)

Adding the factor is NOT additive: baseline minted **1152**, augmented **1212** — RVOL **added 294** (lifted a weak signal over 70) and **dropped 234** (diluted a strong one under 70); shared **918** (entry/stop moved: 0).

| set | n | mean R | t | win% | tp_hit% |
|---|--:|--:|--:|--:|--:|
| baseline book B | 1152 | -0.026 | -0.52 | 37 | 36 |
| augmented book A | 1212 | -0.095 | -1.91 | 36 | 34 |
| RVOL added (A∖B) | 294 | -0.291 | -2.91 | 34 | 33 |
| RVOL dropped (B∖A) | 234 | -0.002 | -0.02 | 40 | 39 |

---

**Reading it.** §1 is decisive and design-free: if RVOL buckets show no monotonic, significant (t≈3.6) improvement in mean R, RVOL carries no outcome signal and no factor design will help — the existing binary VOLUME factor already captures what little it is worth. §2 shows the real mechanics of adding it to THIS scorer: normalization means a graded confirmation dilutes strong signals and re-shuffles the minted set, so 'add a factor' is not free. A frozen spec change (D1 sign-off) is earned only if §1 shows a real, bar-clearing RVOL edge AND §2's augmented book beats baseline. VWAP stays separate (forward-only).

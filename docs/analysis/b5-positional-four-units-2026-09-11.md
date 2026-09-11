# B5 / E1 — the positional stop-width family, in four units (2026-09-11)

Reproduce:

```
cd backend && uv run python scripts/positional_probe.py --stocks 250 --swing-stride 25 \
    --dump-trades /tmp/pos_trades.csv
```

**The question E1 exists to answer.** `R = (α + drift·T)/w` has THREE terms and only α is the
one a stop-width study wants. Re-reporting in raw % removes the `1/w` amplification; it does
**not** remove `drift × T`, because `T` rises with `w` (measured t = +6.69 on swing) and the
universe drifted +0.0816%/day. Only a benchmark **paired to each trade's own entry-to-exit
window** removes both.

**Result: positional closes the same way swing did.** Read the contrast down the units.

| unit | tight (<2%) | wide (≥2%) | contrast | SE | **t** |
|---|---:|---:|---:|---:|---:|
| **R** | −0.4570 | +0.0309 | −0.4879 | 0.2586 | **−1.89** |
| **raw %** *(removes `1/w`)* | −0.3945 | +0.3924 | −0.7870 | 0.6685 | **−1.18** |
| ⭐ **excess vs matched basket** *(removes `drift×T` too)* | −0.4339 | −0.2430 | **−0.1909** | 0.6514 | ⭐ **−0.29** |
| ret ÷ ATR20 | −0.1629 | +0.0906 | −0.2535 | 0.2757 | −0.92 |

*(gap-clean cohort, n = 359 of 390. ALL-windows reads the same shape: −1.47 → −1.20 → −0.29.)*

⇒ ⭐⭐ **The gradient decays monotonically as each mechanical term is removed and is gone by
the third unit.** No bucket contrast survives, in any unit, on either cohort.

## ⚠ And what the R column was actually measuring

`E[1/w]` in the tight bucket is **38.6** against 0.352 in the next one — a 110× jump. That is
a mean stop width of ~0.026%: degenerate, near-zero risk distances. Net ₹ in that bucket is
**−22,461 per trade**, which is risk-first sizing turning a four-paise stop into an enormous
position.

⇒ **What looked like a stop-width effect in R is a leverage artifact from stops the live order
path refuses** — the per-position notional cap is a 2% minimum-stop-width rule in disguise, and
B2's aggregate cash rail refuses the rest. **The cohort carrying the R-space signal is not
tradeable.**

## Also measured

- **Holding period rises sharply with stop width**: mean `T` 6.4 → 16.3 → 21.9 → 29.0 → 32.9
  sessions across the five buckets. This is the `drift × T` premise, confirmed independently on
  positional after being measured at t = +6.69 on swing.
- **The gap filter is a bigger deal here than on swing**: clean −0.1077 (n=359) vs straddling
  +0.7573 (n=31), contrast **−0.8651, t −1.65** (swing: t +0.88). Not significant, MDE 1.47R.

---

```
== B5 / E1: the positional family in FOUR units, with CONTRASTS (not levels) ==
========================================================================================================
  `rule=ema, capped=False` is the LIVE minter's rule (signal_service passes
  ema20_daily); `flat` is what profiles/pipeline and the backtest actually run.

  ── ALL windows (n=390) ──
  bucket          n  meanT  E[1/w]         R     raw %  excess %   ret/ATR     net Rs
  0-2%          115   6.83  38.622   -0.3121   -0.1157   -0.4110   -0.0607     -22461
  2-4%          114  17.12   0.352   -0.0447   -0.0522   +0.0132   -0.0440        -18
  4-6%           69  22.68   0.205   +0.1315   +1.0047   -0.1112   +0.4636       +275
  6-10%          76  29.71   0.132   +0.1090   +0.6333   -0.8829   +0.0789        -12
  10-999%        16  32.94   0.083   +0.5267   +4.8946   +0.6442   +1.2250       +657
    tight(<2%) vs wide(>=2%) in R                tight  -0.3121(n115)  wide  +0.0752(n275)  diff  -0.3874  SE 0.2628  t  -1.47  MDE@80% +0.736
    tight(<2%) vs wide(>=2%) in raw %            tight  -0.1157(n115)  wide  +0.6902(n275)  diff  -0.8059  SE 0.6734  t  -1.20  MDE@80% +1.887
    tight(<2%) vs wide(>=2%) in excess vs basket % tight  -0.4110(n115)  wide  -0.2289(n275)  diff  -0.1821  SE 0.6244  t  -0.29  MDE@80% +1.749
    tight(<2%) vs wide(>=2%) in ret/ATR20        tight  -0.0607(n115)  wide  +0.1912(n275)  diff  -0.2518  SE 0.2781  t  -0.91  MDE@80% +0.779
    tight(<2%) vs wide(>=2%) in net Rs           tight -22461.0733(n115)  wide +96.3424(n275)  diff -22557.4157  SE 18798.7950  t  -1.20  MDE@80% +52666.704

  ── gap-clean only (n=359) ──
  bucket          n  meanT  E[1/w]         R     raw %  excess %   ret/ATR     net Rs
  0-2%          102   6.43  43.392   -0.4570   -0.3945   -0.4339   -0.1629     -25808
  2-4%          108  16.31   0.352   -0.0567   -0.0374   +0.2341   -0.0542        -48
  4-6%           64  21.91   0.206   +0.0615   +0.5741   -0.1217   +0.3157       +147
  6-10%          71  28.96   0.133   +0.0596   +0.2611   -1.1557   -0.0598        -89
  10-999%        14  32.93   0.082   +0.4204   +3.5434   +0.1503   +0.9419       +469
    tight(<2%) vs wide(>=2%) in R                tight  -0.4570(n102)  wide  +0.0309(n257)  diff  -0.4879  SE 0.2586  t  -1.89  MDE@80% +0.725
    tight(<2%) vs wide(>=2%) in raw %            tight  -0.3945(n102)  wide  +0.3924(n257)  diff  -0.7870  SE 0.6685  t  -1.18  MDE@80% +1.873
    tight(<2%) vs wide(>=2%) in excess vs basket % tight  -0.4339(n102)  wide  -0.2430(n257)  diff  -0.1909  SE 0.6514  t  -0.29  MDE@80% +1.825
    tight(<2%) vs wide(>=2%) in ret/ATR20        tight  -0.1629(n102)  wide  +0.0906(n257)  diff  -0.2535  SE 0.2757  t  -0.92  MDE@80% +0.772
    tight(<2%) vs wide(>=2%) in net Rs           tight -25808.1036(n102)  wide +17.7072(n257)  diff -25825.8108  SE 21178.9444  t  -1.22  MDE@80% +59334.931

  ── the gap filter itself, as a contrast ──
    clean vs straddling in R                     clean  -0.1077(n359)  strdl  +0.7573(n31)  diff  -0.8651  SE 0.5246  t  -1.65  MDE@80% +1.470

== B5: dumped 1585 trades x 20 cols -> /home/nithin/.claude/jobs/11b45356/tmp/pos_trades.csv ==
```

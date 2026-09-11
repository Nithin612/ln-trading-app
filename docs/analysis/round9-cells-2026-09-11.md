# Round-9 cells — E3, the paired drift null, and five refuted claims (2026-09-11)

**Read-only.** Reproduce with:

```
cd backend
uv run python scripts/swing_dependence_probe.py --stocks 250 --stride 10 \
    --dump-trades /tmp/swing_trades.csv          # ~25 min; reproduces probe-185 exactly
uv run python scripts/round9_cells.py /tmp/swing_trades.csv
```

The probe writes the per-trade artifact (185 × 25 columns) BEFORE its report sections, so one
expensive pass serves every cell below. Adjudication of what these numbers do to the record is
§12.24–§12.31 of `quant-panel-adjudication-2026-09-10.md`; the card corrections are §16.1c.

⚠ **The universe is `top-250 by median(close × volume) over the last 180 days`** — i.e. it inherits
the 0a.3 survivorship defect (today's liquidity), which the basket also inherits. That makes the
basket's drift if anything OVERSTATED, and therefore the measured α CONSERVATIVE as a deficit.

---

```
loaded 185 trades from /home/nithin/.claude/jobs/11b45356/tmp/swing_trades.csv

============================================================================================================
0.  COHORT SIZES, and the holding period T that every per-day statement needs
============================================================================================================
  T = sessions from entry to exit. The probe CAPS at 5 but trades exit early at a
  barrier; mean T has never been emitted, so 12.20's 5-session null and every
  'per day' number in the record are conditional on a number nobody measured.
  ALL                            n= 185  mean T  3.59  median  5.0  T=0 (same-session exit)  14.6%  mean w  4.43%  E[1/w]  0.597
  BUY                            n=  82  mean T  3.55  median  5.0  T=0 (same-session exit)  17.1%  mean w  4.34%  E[1/w]  0.566
  clean                          n= 147  mean T  3.68  median  5.0  T=0 (same-session exit)  13.6%  mean w  4.41%  E[1/w]  0.586
  clean x BUY                    n=  61  mean T  3.77  median  5.0  T=0 (same-session exit)  14.8%  mean w  4.37%  E[1/w]  0.438
  clean x BUY x w>=2%  <- E3     n=  49  mean T  4.00  median  5.0  T=0 (same-session exit)  10.2%  mean w  5.20%  E[1/w]  0.220

============================================================================================================
1.  E3 + PART B — the net question in FIVE units x FIVE cohorts (explicit charges only)
============================================================================================================
  If the R row and the raw-% row disagree in SIGNIFICANCE, the R row is the 1/w
  estimator up-weighting tight stops -- the cohort the notional cap refuses.

  --- ALL  (n=185) ---
  gross R                                      n= 185  mean   -0.1489  sd  0.8776  SE  0.0645  t  -2.31  clust SE  0.0636 t  -2.34   [R]
  NET R (explicit)                             n= 185  mean   -0.3011  sd  1.0386  SE  0.0764  t  -3.94  clust SE  0.0772 t  -3.90   [R]
  gross raw return %                           n= 185  mean   -0.3279  sd  3.1689  SE  0.2330  t  -1.41  clust SE  0.2293 t  -1.43   [%]
  NET raw return % (explicit)                  n= 185  mean   -0.5829  sd  3.1689  SE  0.2330  t  -2.50  clust SE  0.2293 t  -2.54   [%]
  gross excess over matched basket %           n= 185  mean   -0.5746  sd  3.6328  SE  0.2671  t  -2.15  clust SE  0.3062 t  -1.88   [%]
  NET excess over matched basket %             n= 185  mean   -0.8296  sd  3.6328  SE  0.2671  t  -3.11  clust SE  0.3062 t  -2.71   [%]
  NET return / ATR20                           n= 185  mean   -0.2796  sd  1.2746  SE  0.0937  t  -2.98   [ATR]
  NET cash Rs                                  n= 185  mean -631.5855  sd 5339.1019  SE 392.5386  t  -1.61  clust SE 415.0661 t  -1.52   [Rs]
  cost in R (the Jensen term)                  n= 185  mean   +0.1522  sd  0.4719  SE  0.0347  t  +4.39   [R]

  --- BUY  (n=82) ---
  gross R                                      n=  82  mean   -0.0992  sd  0.9574  SE  0.1057  t  -0.94  clust SE  0.1152 t  -0.86   [R]
  NET R (explicit)                             n=  82  mean   -0.2435  sd  1.0067  SE  0.1112  t  -2.19  clust SE  0.1200 t  -2.03   [R]
  gross raw return %                           n=  82  mean   -0.1877  sd  3.2793  SE  0.3621  t  -0.52  clust SE  0.3931 t  -0.48   [%]
  NET raw return % (explicit)                  n=  82  mean   -0.4427  sd  3.2793  SE  0.3621  t  -1.22  clust SE  0.3931 t  -1.13   [%]
  gross excess over matched basket %           n=  82  mean   -0.0218  sd  3.0221  SE  0.3337  t  -0.07  clust SE  0.3712 t  -0.06   [%]
  NET excess over matched basket %             n=  82  mean   -0.2768  sd  3.0221  SE  0.3337  t  -0.83  clust SE  0.3712 t  -0.75   [%]
  NET return / ATR20                           n=  82  mean   -0.2672  sd  1.3230  SE  0.1461  t  -1.83   [ATR]
  NET cash Rs                                  n=  82  mean -236.7766  sd 5713.0723  SE 630.9033  t  -0.38  clust SE 649.4737 t  -0.36   [Rs]
  cost in R (the Jensen term)                  n=  82  mean   +0.1444  sd  0.2458  SE  0.0271  t  +5.32   [R]

  --- clean  (n=147) ---
  gross R                                      n= 147  mean   -0.1341  sd  0.9109  SE  0.0751  t  -1.79  clust SE  0.0733 t  -1.83   [R]
  NET R (explicit)                             n= 147  mean   -0.2836  sd  1.0702  SE  0.0883  t  -3.21  clust SE  0.0890 t  -3.19   [R]
  gross raw return %                           n= 147  mean   -0.4086  sd  3.1516  SE  0.2599  t  -1.57  clust SE  0.2547 t  -1.60   [%]
  NET raw return % (explicit)                  n= 147  mean   -0.6636  sd  3.1516  SE  0.2599  t  -2.55  clust SE  0.2547 t  -2.61   [%]
  gross excess over matched basket %           n= 147  mean   -0.6055  sd  3.5889  SE  0.2960  t  -2.05  clust SE  0.3384 t  -1.79   [%]
  NET excess over matched basket %             n= 147  mean   -0.8605  sd  3.5889  SE  0.2960  t  -2.91  clust SE  0.3384 t  -2.54   [%]
  NET return / ATR20                           n= 147  mean   -0.3047  sd  1.2653  SE  0.1044  t  -2.92   [ATR]
  NET cash Rs                                  n= 147  mean -525.1323  sd 5724.4976  SE 472.1486  t  -1.11  clust SE 502.8763 t  -1.04   [Rs]
  cost in R (the Jensen term)                  n= 147  mean   +0.1495  sd  0.5058  SE  0.0417  t  +3.58   [R]

  --- clean x BUY  (n=61) ---
  gross R                                      n=  61  mean   -0.0843  sd  1.0050  SE  0.1287  t  -0.66  clust SE  0.1397 t  -0.60   [R]
  NET R (explicit)                             n=  61  mean   -0.1960  sd  0.9805  SE  0.1255  t  -1.56  clust SE  0.1355 t  -1.45   [R]
  gross raw return %                           n=  61  mean   -0.5287  sd  3.1568  SE  0.4042  t  -1.31  clust SE  0.4433 t  -1.19   [%]
  NET raw return % (explicit)                  n=  61  mean   -0.7837  sd  3.1568  SE  0.4042  t  -1.94  clust SE  0.4433 t  -1.77   [%]
  gross excess over matched basket %           n=  61  mean   -0.2250  sd  2.9094  SE  0.3725  t  -0.60  clust SE  0.4143 t  -0.54   [%]
  NET excess over matched basket %             n=  61  mean   -0.4800  sd  2.9094  SE  0.3725  t  -1.29  clust SE  0.4143 t  -1.16   [%]
  NET return / ATR20                           n=  61  mean   -0.3645  sd  1.3050  SE  0.1671  t  -2.18   [ATR]
  NET cash Rs                                  n=  61  mean +185.2727  sd 6026.1938  SE 771.5751  t  +0.24  clust SE 779.1658 t  +0.24   [Rs]
  cost in R (the Jensen term)                  n=  61  mean   +0.1116  sd  0.1509  SE  0.0193  t  +5.78   [R]

  --- clean x BUY x w>=2%  <- E3  (n=49) ---
  gross R                                      n=  49  mean   -0.1212  sd  0.6712  SE  0.0959  t  -1.26  clust SE  0.0991 t  -1.22   [R]
  NET R (explicit)                             n=  49  mean   -0.1772  sd  0.6726  SE  0.0961  t  -1.84  clust SE  0.0986 t  -1.80   [R]
  gross raw return %                           n=  49  mean   -0.5781  sd  3.4587  SE  0.4941  t  -1.17  clust SE  0.5142 t  -1.12   [%]
  NET raw return % (explicit)                  n=  49  mean   -0.8331  sd  3.4587  SE  0.4941  t  -1.69  clust SE  0.5142 t  -1.62   [%]
  gross excess over matched basket %           n=  49  mean   -0.2405  sd  3.1109  SE  0.4444  t  -0.54  clust SE  0.4941 t  -0.49   [%]
  NET excess over matched basket %             n=  49  mean   -0.4955  sd  3.1109  SE  0.4444  t  -1.11  clust SE  0.4941 t  -1.00   [%]
  NET return / ATR20                           n=  49  mean   -0.3510  sd  1.4117  SE  0.2017  t  -1.74   [ATR]
  NET cash Rs                                  n=  49  mean -307.4985  sd 1291.9738  SE 184.5677  t  -1.67  clust SE 191.1311 t  -1.61   [Rs]
  cost in R (the Jensen term)                  n=  49  mean   +0.0561  sd  0.0240  SE  0.0034  t +16.39   [R]

============================================================================================================
2.  THE SLIPPAGE LADDER on the E3 cell — the assumed half, never folded in
============================================================================================================
  NET R  @ 0 bps/leg slippage                  n=  49  mean   -0.1772  sd  0.6726  SE  0.0961  t  -1.84  clust SE  0.0986 t  -1.80   [R]
  NET raw %  @ 0 bps/leg                       n=  49  mean   -0.8331  sd  3.4587  SE  0.4941  t  -1.69  clust SE  0.5142 t  -1.62   [%]
  NET R  @ 10 bps/leg slippage                 n=  49  mean   -0.2212  sd  0.6742  SE  0.0963  t  -2.30  clust SE  0.0983 t  -2.25   [R]
  NET raw %  @ 10 bps/leg                      n=  49  mean   -1.0331  sd  3.4587  SE  0.4941  t  -2.09  clust SE  0.5142 t  -2.01   [%]
  NET R  @ 15 bps/leg slippage                 n=  49  mean   -0.2432  sd  0.6752  SE  0.0965  t  -2.52  clust SE  0.0982 t  -2.48   [R]
  NET raw %  @ 15 bps/leg                      n=  49  mean   -1.1331  sd  3.4587  SE  0.4941  t  -2.29  clust SE  0.5142 t  -2.20   [%]
  NET R  @ 20 bps/leg slippage                 n=  49  mean   -0.2652  sd  0.6764  SE  0.0966  t  -2.74  clust SE  0.0980 t  -2.71   [R]
  NET raw %  @ 20 bps/leg                      n=  49  mean   -1.2331  sd  3.4587  SE  0.4941  t  -2.50  clust SE  0.5142 t  -2.40   [%]
  NET R  @ 30 bps/leg slippage                 n=  49  mean   -0.3092  sd  0.6790  SE  0.0970  t  -3.19  clust SE  0.0978 t  -3.16   [R]
  NET raw %  @ 30 bps/leg                      n=  49  mean   -1.4331  sd  3.4587  SE  0.4941  t  -2.90  clust SE  0.5142 t  -2.79   [%]

============================================================================================================
3.  G1/C2 — the stop-width family with drift x T ISOLATED
============================================================================================================
  R = (alpha + drift*T)/w. Re-reporting in raw % removes 1/w and NOT drift*T,
  because T rises with w and the universe rose. Only the matched-window basket
  (the `excess` column) removes both. Read the three rows against each other.

  --- ALL ---
  bucket          n  meanT  E[1/w]         R     raw %  excess %   ret/ATR
  0-2%           30   1.70   2.520   -0.4726   -0.5475   -0.5169   -0.1478
  2-4%           45   3.33   0.350   -0.2152   -0.6905   -1.0033   -0.3561
  4-6%           55   3.98   0.202   -0.0546   -0.1795   -0.6407   -0.0215
  6-10%          54   4.43   0.146   -0.0078   -0.0107   -0.1353   -0.0560
    tight vs wide in R                         tight  -0.4726 (n30)  wide  -0.0862 (n155)  diff  -0.3864  SE 0.2492  t  -1.55  p 0.121  MDE@80% +0.6982
    tight vs wide in raw %                     tight  -0.5475 (n30)  wide  -0.2854 (n155)  diff  -0.2622  SE 0.3381  t  -0.78  p 0.438  MDE@80% +0.9472
    tight vs wide in excess vs basket %        tight  -0.5169 (n30)  wide  -0.5858 (n155)  diff  +0.0690  SE 0.4143  t  +0.17  p 0.868  MDE@80% +1.1608

  --- clean x BUY ---
  bucket          n  meanT  E[1/w]         R     raw %  excess %   ret/ATR
  0-2%           12   2.83   1.327   +0.0659   -0.3267   -0.1616   +0.0725
  2-4%           13   3.85   0.354   -0.1023   -0.2599   -0.5486   -0.1710
  4-6%           16   3.94   0.199   -0.0735   -0.2582   +0.0676   +0.0101
  6-10%          20   4.15   0.150   -0.1716   -1.0409   -0.2866   -0.4900
    tight vs wide in R                         tight  +0.0659 (n12)  wide  -0.1212 (n49)  diff  +0.1871  SE 0.5494  t  +0.34  p 0.733  MDE@80% +1.5393
    tight vs wide in raw %                     tight  -0.3267 (n12)  wide  -0.5781 (n49)  diff  +0.2514  SE 0.6474  t  +0.39  p 0.698  MDE@80% +1.8139
    tight vs wide in excess vs basket %        tight  -0.1616 (n12)  wide  -0.2405 (n49)  diff  +0.0788  SE 0.7249  t  +0.11  p 0.913  MDE@80% +2.0308

============================================================================================================
4.  Is `ret ⟂ w` really independence, or is it the drift x T slope?
============================================================================================================
  12.18f read `ret_pct ~ w` t = +1.07 as 'independence is MEASURED'. A
  non-rejection is not an affirmation, and drift x T predicts a POSITIVE slope
  of a specific size. Compare the measured slope against that prediction.
  ALL            d(ret %)/dw = +0.10532  SE 0.10303  t  +1.02
  ALL            d(T (sessions))/dw = +0.38437  SE 0.05744  t  +6.69
  ALL            d(excess %)/dw = +0.07551  SE 0.11832  t  +0.64
  clean x BUY    d(ret %)/dw = -0.04824  SE 0.18317  t  -0.26
  clean x BUY    d(T (sessions))/dw = +0.18683  SE 0.10920  t  +1.71
  clean x BUY    d(excess %)/dw = +0.01226  SE 0.16891  t  +0.07

============================================================================================================
5.  G5 — the PAIRED drift null (12.20 computed it unpaired)
============================================================================================================
  ALL: basket over the trade's own window      n= 185  mean   +0.2468  sd  1.9559  SE  0.1438  t  +1.72  clust SE  0.2055 t  +1.20   [%]
  ALL: PAIRED excess (trade - basket)          n= 185  mean   -0.5746  sd  3.6328  SE  0.2671  t  -2.15  clust SE  0.3062 t  -1.88   [%]
  BUY: basket over the trade's own window      n=  82  mean   -0.1659  sd  2.1259  SE  0.2348  t  -0.71  clust SE  0.3024 t  -0.55   [%]
  BUY: PAIRED excess (trade - basket)          n=  82  mean   -0.0218  sd  3.0221  SE  0.3337  t  -0.07  clust SE  0.3712 t  -0.06   [%]
  clean: basket over the trade's own window    n= 147  mean   +0.1969  sd  1.9219  SE  0.1585  t  +1.24  clust SE  0.2311 t  +0.85   [%]
  clean: PAIRED excess (trade - basket)        n= 147  mean   -0.6055  sd  3.5889  SE  0.2960  t  -2.05  clust SE  0.3384 t  -1.79   [%]
  clean x BUY: basket over the trade's own window n=  61  mean   -0.3037  sd  2.1774  SE  0.2788  t  -1.09  clust SE  0.3605 t  -0.84   [%]
  clean x BUY: PAIRED excess (trade - basket)  n=  61  mean   -0.2250  sd  2.9094  SE  0.3725  t  -0.60  clust SE  0.4143 t  -0.54   [%]
  clean x BUY x w>=2%  <- E3: basket over the trade's own window n=  49  mean   -0.3376  sd  2.2519  SE  0.3217  t  -1.05  clust SE  0.4093 t  -0.82   [%]
  clean x BUY x w>=2%  <- E3: PAIRED excess (trade - basket) n=  49  mean   -0.2405  sd  3.1109  SE  0.4444  t  -0.54  clust SE  0.4941 t  -0.49   [%]

============================================================================================================
6.  G6 / plan item 22 — the account earns Rs/day, not R (at the MEASURED hold)
============================================================================================================
  basket drift, full span of this artifact: see the probe log (regime-dependent;
  12.20's +0.0816%/day is the POST-GAP block only -- do not reuse it as a constant)
  ALL                            slip    0 bps  mean T 3.74  net  -0.583%/trade  -0.3654%/day   basket +0.0746%/day   gap  -110.9 pp/yr
  ALL                            slip   15 bps  mean T 3.74  net  -0.883%/trade  -0.4895%/day   basket +0.0746%/day   gap  -142.2 pp/yr
  BUY                            slip    0 bps  mean T 3.72  net  -0.443%/trade  -0.2473%/day   basket -0.0259%/day   gap   -55.8 pp/yr
  BUY                            slip   15 bps  mean T 3.72  net  -0.743%/trade  -0.3736%/day   basket -0.0259%/day   gap   -87.6 pp/yr
  clean                          slip    0 bps  mean T 3.82  net  -0.664%/trade  -0.3495%/day   basket +0.0527%/day   gap  -101.3 pp/yr
  clean                          slip   15 bps  mean T 3.82  net  -0.964%/trade  -0.4675%/day   basket +0.0527%/day   gap  -131.1 pp/yr
  clean x BUY                    slip    0 bps  mean T 3.92  net  -0.784%/trade  -0.3782%/day   basket -0.0816%/day   gap   -74.8 pp/yr
  clean x BUY                    slip   15 bps  mean T 3.92  net  -1.084%/trade  -0.4926%/day   basket -0.0816%/day   gap  -103.6 pp/yr
  clean x BUY x w>=2%  <- E3     slip    0 bps  mean T 4.10  net  -0.833%/trade  -0.3381%/day   basket -0.0882%/day   gap   -63.0 pp/yr
  clean x BUY x w>=2%  <- E3     slip   15 bps  mean T 4.10  net  -1.133%/trade  -0.4432%/day   basket -0.0882%/day   gap   -89.5 pp/yr

============================================================================================================
7.  G4 — the `choppy` display filter (ER < 0.30) tested as a SELECTOR
============================================================================================================
  Default-ON in `signals.py`, absent from `restrictions.py`, not applied by the
  order path, never applied by the corpus. Filed as governance; never measured.

  --- ALL (n=185 with an ER) ---
    ER<0.30 (HIDDEN) vs >=0.30 in R            hidden  -0.1489 (n124)  shown  -0.1488 (n61)  diff  -0.0001  SE 0.1344  t  -0.00  p 0.999  MDE@80% +0.3766
    ER<0.30 (HIDDEN) vs >=0.30 in raw %        hidden  -0.3405 (n124)  shown  -0.3022 (n61)  diff  -0.0383  SE 0.5010  t  -0.08  p 0.939  MDE@80% +1.4036
    ER<0.30 (HIDDEN) vs >=0.30 in excess vs basket % hidden  -0.5714 (n124)  shown  -0.5811 (n61)  diff  +0.0097  SE 0.5535  t  +0.02  p 0.986  MDE@80% +1.5507

  --- clean x BUY (n=61 with an ER) ---
    ER<0.30 (HIDDEN) vs >=0.30 in R            hidden  -0.0056 (n35)  shown  -0.1903 (n26)  diff  +0.1846  SE 0.2384  t  +0.77  p 0.439  MDE@80% +0.6678
    ER<0.30 (HIDDEN) vs >=0.30 in raw %        hidden  -0.4303 (n35)  shown  -0.6611 (n26)  diff  +0.2308  SE 0.7966  t  +0.29  p 0.772  MDE@80% +2.2319
    ER<0.30 (HIDDEN) vs >=0.30 in excess vs basket % hidden  -0.0709 (n35)  shown  -0.4323 (n26)  diff  +0.3614  SE 0.7386  t  +0.49  p 0.625  MDE@80% +2.0692

============================================================================================================
8.  C3 — the confidence NORMALIZER: four rival ranking keys, same panels
============================================================================================================
  confluence.py:160 divides by the weight of SCORING factors. The deployed UI
  sorts DESCENDING on the result. If a rival key ranks better, the information
  was destroyed by the normalizer rather than absent from the factors.

  --- ALL (n=185) ---
  rho(confidence_pct  <- DEPLOYED , R) -0.0179  p 0.807   |  vs raw % -0.0262  p 0.728
  rho(raw weighted sum            , R) +0.0544  p 0.465   |  vs raw % +0.0375  p 0.608
  rho(breadth (# scoring factors) , R) +0.0295  p 0.691   |  vs raw % +0.0149  p 0.834
  rho(weight that scored          , R) +0.0416  p 0.569   |  vs raw % +0.0187  p 0.795
  rho(concentration (top share)   , R) -0.0435  p 0.555   |  vs raw % -0.0179  p 0.801
    breadth buckets:  1 factors n=33 R -0.187  2 factors n=53 R -0.175  3 factors n=64 R -0.073  4 factors n=31 R -0.275  5 factors n=3 R +0.374

  --- clean x BUY (n=61) ---
  rho(confidence_pct  <- DEPLOYED , R) +0.0246  p 0.849   |  vs raw % +0.0353  p 0.785
  rho(raw weighted sum            , R) +0.0419  p 0.744   |  vs raw % +0.0014  p 0.992
  rho(breadth (# scoring factors) , R) +0.0670  p 0.609   |  vs raw % +0.0191  p 0.879
  rho(weight that scored          , R) +0.0467  p 0.715   |  vs raw % -0.0051  p 0.965
  rho(concentration (top share)   , R) -0.0888  p 0.499   |  vs raw % -0.0105  p 0.936
    breadth buckets:  1 factors n=16 R -0.274  2 factors n=13 R -0.073  3 factors n=17 R +0.130  4 factors n=14 R -0.152
============================================================================================================
9.  D4 — the posterior, done correctly: the prior belongs on the GROSS mean
============================================================================================================
  A prior of the form 'an unfitted TA scorer has no edge' is a statement about the
  GROSS mean. Costs are KNOWN, not estimated, so they must not be shrunk toward 0.
  12.18h D4 had this right; shrinking a NET mean and comparing to 0 does not.
  The hurdle is E[cost in R] + E[basket in R] over the SAME trades, paired.

  --- clean x BUY (n=61) ---
  gross mean -0.0843R   iid SE 0.1287   clustered SE 0.1397
  hurdles: cost(explicit) +0.1116R   cost(+15bps/leg) +0.2430R   PAIRED basket -0.0558R
           break-even +0.1116   BE+basket +0.0558   BE+basket @15bps +0.1871
  SE = iid 0.1287
    prior sd 0.03: post -0.0043+-0.0292  P(>0)  44.08%  P(>BE)   0.00%  P(>BE+basket)   1.97%  P(>BE+basket@15bps)   0.00%
    prior sd 0.05: post -0.0111+-0.0466  P(>0)  40.62%  P(>BE)   0.42%  P(>BE+basket)   7.56%  P(>BE+basket@15bps)   0.00%
    prior sd 0.10: post -0.0318+-0.0790  P(>0)  34.37%  P(>BE)   3.47%  P(>BE+basket)  13.37%  P(>BE+basket@15bps)   0.28%
    prior sd 0.20: post -0.0597+-0.1082  P(>0)  29.07%  P(>BE)   5.67%  P(>BE+basket)  14.30%  P(>BE+basket@15bps)   1.13%
  SE = date-clustered 0.1397
    prior sd 0.03: post -0.0037+-0.0293  P(>0)  44.96%  P(>BE)   0.00%  P(>BE+basket)   2.12%  P(>BE+basket@15bps)   0.00%
    prior sd 0.05: post -0.0096+-0.0471  P(>0)  41.94%  P(>BE)   0.50%  P(>BE+basket)   8.24%  P(>BE+basket@15bps)   0.00%
    prior sd 0.10: post -0.0286+-0.0813  P(>0)  36.27%  P(>BE)   4.24%  P(>BE+basket)  14.97%  P(>BE+basket@15bps)   0.40%
    prior sd 0.20: post -0.0567+-0.1146  P(>0)  31.04%  P(>BE)   7.09%  P(>BE+basket)  16.30%  P(>BE+basket@15bps)   1.66%

  --- clean x BUY x w>=2%  <- E3 (n=49) ---
  gross mean -0.1212R   iid SE 0.0959   clustered SE 0.0991
  hurdles: cost(explicit) +0.0561R   cost(+15bps/leg) +0.1221R   PAIRED basket -0.0478R
           break-even +0.0561   BE+basket +0.0083   BE+basket @15bps +0.0743
  SE = iid 0.0959
    prior sd 0.03: post -0.0108+-0.0286  P(>0)  35.30%  P(>BE)   0.97%  P(>BE+basket)  25.22%  P(>BE+basket@15bps)   0.15%
    prior sd 0.05: post -0.0259+-0.0443  P(>0)  27.95%  P(>BE)   3.22%  P(>BE+basket)  22.02%  P(>BE+basket@15bps)   1.19%
    prior sd 0.10: post -0.0631+-0.0692  P(>0)  18.09%  P(>BE)   4.25%  P(>BE+basket)  15.10%  P(>BE+basket@15bps)   2.35%
    prior sd 0.20: post -0.0985+-0.0865  P(>0)  12.73%  P(>BE)   3.69%  P(>BE+basket)  10.83%  P(>BE+basket@15bps)   2.28%
  SE = date-clustered 0.0991
    prior sd 0.03: post -0.0102+-0.0287  P(>0)  36.17%  P(>BE)   1.05%  P(>BE+basket)  26.00%  P(>BE+basket@15bps)   0.16%
    prior sd 0.05: post -0.0246+-0.0446  P(>0)  29.11%  P(>BE)   3.54%  P(>BE+basket)  23.07%  P(>BE+basket@15bps)   1.34%
    prior sd 0.10: post -0.0611+-0.0704  P(>0)  19.28%  P(>BE)   4.80%  P(>BE+basket)  16.21%  P(>BE+basket@15bps)   2.72%
    prior sd 0.20: post -0.0973+-0.0888  P(>0)  13.68%  P(>BE)   4.22%  P(>BE+basket)  11.73%  P(>BE+basket@15bps)   2.67%

============================================================================================================
10. Rs/day, BOTH aggregations — the choice moves the answer by ~2x
============================================================================================================
  mean-of-ratios counts a same-session exit as a full day; ratio-of-means is what
  the ACCOUNT experiences (total return over total days deployed). Report both.
  ALL                            slip    0  mean-of-ratios -0.3654%/d vs +0.0746 =  -110.9 pp/yr  |  ratio-of-means -0.1561%/d vs +0.0661 =   -56.0 pp/yr
  ALL                            slip   15  mean-of-ratios -0.4895%/d vs +0.0746 =  -142.2 pp/yr  |  ratio-of-means -0.2364%/d vs +0.0661 =   -76.2 pp/yr
  BUY                            slip    0  mean-of-ratios -0.2473%/d vs -0.0259 =   -55.8 pp/yr  |  ratio-of-means -0.1190%/d vs -0.0446 =   -18.8 pp/yr
  BUY                            slip   15  mean-of-ratios -0.3736%/d vs -0.0259 =   -87.6 pp/yr  |  ratio-of-means -0.1997%/d vs -0.0446 =   -39.1 pp/yr
  clean                          slip    0  mean-of-ratios -0.3495%/d vs +0.0527 =  -101.3 pp/yr  |  ratio-of-means -0.1739%/d vs +0.0516 =   -56.8 pp/yr
  clean                          slip   15  mean-of-ratios -0.4675%/d vs +0.0527 =  -131.1 pp/yr  |  ratio-of-means -0.2525%/d vs +0.0516 =   -76.6 pp/yr
  clean x BUY                    slip    0  mean-of-ratios -0.3782%/d vs -0.0816 =   -74.8 pp/yr  |  ratio-of-means -0.2000%/d vs -0.0775 =   -30.9 pp/yr
  clean x BUY                    slip   15  mean-of-ratios -0.4926%/d vs -0.0816 =  -103.6 pp/yr  |  ratio-of-means -0.2766%/d vs -0.0775 =   -50.2 pp/yr
  clean x BUY x w>=2%  <- E3     slip    0  mean-of-ratios -0.3381%/d vs -0.0882 =   -63.0 pp/yr  |  ratio-of-means -0.2031%/d vs -0.0823 =   -30.4 pp/yr
  clean x BUY x w>=2%  <- E3     slip   15  mean-of-ratios -0.4432%/d vs -0.0882 =   -89.5 pp/yr  |  ratio-of-means -0.2762%/d vs -0.0823 =   -48.9 pp/yr
```

# Phase 6.5 — Pair-trading (market-neutral) · DESIGN + build tracker

**Status: BUILD STARTED 2026-08-14 (autonomous session, user away).** Shadow-first,
frozen engine untouched (a NEW overlay/profile — never a change to the confluence
engine). This doc captures the design, the options weighed, and the decisions, so we
can discuss the deferred parts later.

## The one-paragraph case

Every profile we run is **directional** — it needs a trend to make money, and the
6.2 attribution proved it leaks in choppy/transitional tape (the very regime the new
regime gate now suppresses). A **market-neutral pair trade** is regime-agnostic: it
earns from the *relative* mean-reversion of two co-moving instruments, not from market
direction, so it can make money in exactly the sideways tape our directional book
sits out. Origin: the Zerodha Varsity review named it the standout *new* candidate
(`docs/VARSITY_REVIEW_2026-08-12.md`; see memory `varsity-review-2026-08`).

## Strategy design

**Pair = two co-moving instruments (A, B).** Fit a hedge ratio β by OLS of A on B on
completed candles; the **spread** `s = A − β·B` is stationary iff A,B are cointegrated.
Trade the spread's mean-reversion:
- **Entry** when the spread's rolling z-score `|z| > z_entry` (e.g. 2.0): long the cheap
  leg, short the rich leg (dollar-matched → market-neutral).
- **Exit** when `|z| < z_exit` (e.g. 0.5) — reversion captured.
- **Stop** when `|z| > z_stop` (e.g. 3.5) — the relationship broke (cointegration lost);
  cut, don't average down.

**No look-ahead (non-negotiable, `trading-domain` rules):** β, the rolling mean/σ, and z
are computed on candles ≤ N and the signal is valid from N+1. The screen and the signal
both compute only on `is_complete` bars.

## Deps decision — numpy default + statsmodels ADF cross-check (updated 2026-08-15)

**Started numpy-only** (2026-08-14; scipy/statsmodels omitted to stay lean per the
external-libs review). **On 2026-08-15 the user approved adding statsmodels+scipy** "if it
gives an edge" — so the screen now has TWO stationarity paths, and an A/B on the live
universe answered whether ADF is actually better (see the build log — it is NOT a clean
upgrade). The math:
- **Hedge ratio** β: OLS via `numpy.linalg.lstsq` (with an intercept). Exact.
- **Half-life of mean reversion**: fit AR(1) on Δs vs s (Ornstein-Uhlenbeck),
  `half_life = −ln(2)/λ` where λ is the mean-reversion rate. Exact, standard, cheap.
- **Stationarity GATE**: the **Dickey-Fuller t-statistic** of the mean-reversion
  coefficient λ (from the Δs = c + λ·s_{t-1} regression), compared to the standard DF 5%
  critical value −2.86 (constant case). Plain DF — no lag augmentation. The **Lo–MacKinlay
  variance ratio** is also computed but is **INFORMATIONAL only** (VR(2) sits near 1 for any
  pair with a tradeable half-life, so it is a weak discriminator and does NOT gate — the DF
  t-stat does). *(Corrected 2026-08-14 per quant-verifier: an earlier draft said VR was the
  gate; the code gates on the DF t-stat.)*
- **`method="adf"` (2026-08-15, statsmodels):** Augmented DF (`adfuller`, AIC lag selection +
  MacKinnon p-value; gate p ≤ 0.05) with a **Johansen** hedge ratio (`coint_johansen`,
  symmetric / order-independent). A more rigorous *test* — but the A/B shows it's a wider net
  that also admits fragile Johansen βs, so **`df` stays the conservative default**.
- **Notional guard (both methods):** reject economically-implausible hedge ratios (leg dollar
  exposures beyond `MAX_NOTIONAL_IMBALANCE` = 5×) — kills the Johansen β≈132-type artifacts and
  over-imbalanced OLS pairs alike.
- **Follow-up (flagged for discussion):** a formal **Engle-Granger ADF** or **Johansen**
  cointegration test — needs statsmodels, or a numpy ADF validated against known
  MacKinnon CVs. Only worth it if the VR/half-life screen proves too permissive in the
  shadow evidence.

## The India short-leg constraint (why this is naturally shadow-first)

A pair trade shorts one leg. In the Indian **cash** market a short must be covered
intraday — you cannot hold a cash short overnight. A multi-day pair trade therefore
needs the short leg in **stock futures** (or SLB borrow). We do not have a futures
execution path (that's Phase 7, live trading). So pair-trading is **research/shadow only**
until then — which is fine: it's exactly the shadow-first posture the whole phase uses,
and the spread P&L can be measured hypothetically without an execution path. **Tradeability
= a documented Phase-7 dependency**, not a Phase-6 blocker.

## Slicing

- **6.5a — cointegration / mean-reversion SCREEN (offline, numpy, tested).** Given the
  universe + daily bars, for each candidate pair compute β, spread, half-life, VR, current
  z; rank and refuse to report pairs below a stationarity/half-life floor (the n<20
  no-rank precedent). Read-only, like `corpus_attribution`. **← building first (safe,
  self-contained, the foundation everything else needs).**
- **6.5b — spread z-score signal + shadow pair-profile.** Mint `is_shadow` pair signals on
  the nightly path. Needs a way to represent a 2-leg signal (see open questions).
- **6.5c — spread outcome / P&L tracking + 6.1/6.2 attribution for pairs**, so the shadow
  evidence is judged by the same machinery as everything else.
- **6.5d — tradeability (Phase 7):** stock-futures short leg, pair position sizing, borrow.

## Open questions (for our discussion — decisions NOT taken autonomously)

1. **Pair universe scope.** Same-sector pairs only, or all C(n,2) of a liquid set?
   All-pairs over Nifty50 = 1225 pairs — screening cost is fine offline, but screening that
   many **invites data-snooped false cointegration** (multiple-testing). Recommendation:
   restrict to same-sector / economically-linked pairs first (a prior), and validate any
   surviving pair out-of-sample before it ever mints a shadow signal.
2. **Signal representation.** The `signals` table is single-instrument. A pair signal is two
   legs. Options: (a) a new `pair_signals` model; (b) encode the spread as a synthetic
   instrument; (c) two linked `signals` rows with a shared `pair_id`. Leaning (a) — cleanest,
   doesn't distort the single-name schema the attribution assumes.
3. **Formal cointegration** (ADF/Johansen) vs the numpy VR/half-life proxy — revisit if the
   shadow evidence shows the proxy admits junk pairs.
4. **Rebalancing β.** β drifts; static vs rolling re-fit (Kalman filter is the sophisticated
   answer, deferred).

## Build log

- **2026-08-14:** design fixed (this doc); deps decision = numpy-only; 6.5a build started.
  6.5b–d designed + deferred for discussion.
- **2026-08-14:** **6.5a DONE** — `app/services/pair_screen.py` (OLS hedge ratio, DF stationarity
  t-stat gate + OU half-life, Lo-MacKinlay VR informational, trailing z-score); 13 tests;
  quant-verifier PASS-WITH-NOTES (math recomputed to ~1e-14; notes addressed — DF-gate doc
  reconcile, `adf_tstat`→`df_tstat`, exact-value SE canary).
- **2026-08-14:** **6.5a.2 DONE** — `app/services/pair_universe.py` + `scripts/pair_universe.py`
  → `docs/analysis/pairs-<date>.md`. Same-sector Nifty50 screen over ~400 trading days, ranked by
  DF t-stat; pure `align_closes`/`rank_pairs` + thin DB loader; 8 tests incl. a DB planted-pair.
  **First live run: 12 sensible candidates** (IT/metals/pharma/auto/financials peers;
  `docs/analysis/pairs-2026-08-14.md`). Empirical confirmation that VR(2)≈1 on real mean-reverting
  pairs — VR is informational, the DF t-stat gates. Read-only; **6.5b (signal minting) still
  deferred pending the pair-signal schema decision** (open question #2 above).
- **2026-08-15:** **statsmodels/scipy A/B DONE** (user approved the deps). Added `method="adf"`
  (Augmented DF + Johansen β) alongside the numpy `method="df"` default, plus a notional-
  imbalance guard on both. **A/B on the live universe (with the guard): df = 8 candidates, adf =
  23; df is a clean SUBSET of adf (adf misses none, adds 15).** So ADF is a *wider net*, not a
  clean upgrade — its extra pairs are unvalidated, and raw-level **Johansen produced fragile
  hedge ratios (β≈132)** the guard had to catch. **Decision: keep `df` as the conservative
  default; `adf` is an available cross-check; resolve df-vs-adf by 6.5b FORWARD shadow P&L, not
  by argument.** Report of record `docs/analysis/pairs-2026-08-15.md` (df, 8 pairs). +8 tests
  (ADF sig/insig, Johansen β recovery, adf-gate canary, notional-guard). Net edge over
  numpy-only: a more rigorous *test* available on demand + a tradeability guard — modest, honest.
- **2026-08-15:** **6.5b slice 1 DONE** — `PairSignal` model (`app/models/pair.py`) + migration
  `f4a5b6c7d8e9` (`CREATE TABLE pair_signals`). PURELY ADDITIVE + shadow-only; single-name path
  proven unaffected (`test_signals` green). Both df/adf arms mint here (the df-vs-adf A/B). +2
  tests. **User confirmed the additive/insulated/shadow model** (schema question resolved: option
  (a) new model). NEXT: slice 2 = the nightly shadow minter (screen → mint df+adf pair signals at
  |z| ≥ entry), then slice 3 = spread-outcome tracker, slice 4 = pair attribution.
- **2026-08-15:** **6.5b slice 2 DONE** — the dual-arm shadow minter. `pair_minter.mint_pair_signals`
  + `pair_tasks` (Celery nightly 19:25 IST) + CLI. Screens df+adf, mints shadow PairSignals at
  entry_z ≤ |z| < |z_stop| (long cheap / short rich). First live run: 2 signals (MAXHEALTH–SUNPHARMA
  df+adf, long_spread). `PairStat` += spread_last/z_sigma; `PairCandidate` += stock ids (bug-hunter
  Finding 2). **bug-hunter BUGS-FOUND → all fixed:** entry-past-stop (MED — would book a winning
  reversion as a stop-loss, corrupting the A/B), dual-listing id-threading (LOW), σ-rounds-to-0
  guard (LOW). +4 tests. NEXT: slice 3 = spread-outcome tracker (follow z forward to revert/stop),
  slice 4 = pair attribution.
- **2026-08-15 — KNOB-TUNING DECISION (user-accepted):** do NOT tune the entry/exit/stop z
  (2.0 / 0 / 3.5), lookback (400d), or same-sector prior now. Same discipline as the regime gate
  + retune: tune from the SHADOW EVIDENCE (slice-4 attribution), not by argument before there is
  data. **Flagged for the tuning review:** entry z = 2.0 is fairly permissive for daily pairs;
  z = 2.5 would give higher-conviction entries — but let the forward spread P&L decide. The knobs
  are all parameters on `pair_minter`/`pair_screen`, changeable in one place when the evidence says.
- **2026-08-15 — 6.5b slices 3+4 DONE → 6.5b COMPLETE.** Slice 3 = `pair_outcome` spread-outcome
  tracker (walk z forward from the tape → tp_first/sl_first/expired, `outcome_r` in single-name R
  units, gap-through-stop honest, resolution bounded by the validity date); the nightly task now
  resolves-then-mints. Slice 4 = `pair_attribution` + CLI → `pair-attribution-<date>.md` (expectancy
  by arm/sector/half-life — the df-vs-adf verdict). quant-verifier FAIL→fixed: **HIGH** (unbounded
  resolution loop → post-validity crosses mis-booked as tp/sl, corrupting the A/B) fixed +
  regression-tested; R-sign convention + frozen-z reference verified exact at every boundary. +13
  tests. **The full 6.5 pair-trading loop is built shadow-first; forward evidence accrues nightly,
  and the attribution report will answer "do pairs work + which arm" once it does.**

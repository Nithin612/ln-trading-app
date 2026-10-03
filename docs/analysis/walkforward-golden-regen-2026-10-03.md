# §8 walk-forward goldens — data-only regeneration, 2026-10-03

**Sign-off:** the author, 2026-10-03 ("proceed with the recommendation and record it"). The
recommendation was: prove that the drift is data before overwriting anything, and regenerate
**only** where the proof holds.

## What was red, and why

`make walkforward` failed on all 8 goldens. This was found during Bucket C #5 (A14). The goldens
date from 2026-07-06/07. The walk-forward reads no calendar, and no code change touches it. The
suspect was the 2026-09-17 back-fill, which recovered three NSE weekend sessions inside the golden
window: **2024-03-02, 2025-02-01 and 2026-02-01**.

## The proof (read-only against the dev DB)

A scratch harness wrapped `walkforward._load_frames`. It reran each golden on its pinned symbols
and bounds, twice: once as-is, and once with the three dates dropped at the loader.

- **Check 1:** per pinned symbol, current rows − golden rows equals the bars on those three dates.
- **Check 2:** with those three dates dropped, the rerun reproduces the golden **exactly**: the row
  counts and the sha256 trade digest.

| golden | tf | extra rows per name | check 1 | check 2 | pre-gate trades: golden → now (without the 3 days) |
|---|---|---|---|---|---|
| dc1 | 1d | 3 | PASS | PASS | 427 → 445 (427) |
| dc2 | 1d | 3 | PASS | PASS | 427 → 445 (427) |
| multibagger | 1d | 1–3 | PASS | PASS | 6341 → 6370 (6341) |
| rrbo_basic | 1d | 3 | PASS | PASS | 427 → 445 (427) |
| rrbo_trailing | 1d | 3 | PASS | PASS | 427 → 445 (427) |
| gainer_925 | 5m | **−55,329 … 0** | FAIL | FAIL | 244,440 → 237,859 |
| orb_15m | 15m | **−18,443 … 0** | FAIL | FAIL | 8,684 → 8,450 |
| pdh_pdl | 15m | **−18,443 … 0** | FAIL | FAIL | 8,684 → 8,450 |

**The daily drift is exactly the three weekend sessions and nothing else.**

**The intraday drift is LOSS, not addition.** DALBHARAT, EXIDEIND, NUVAMA and SAMMAANCAP have **no**
5m/15m bars in the window; their only intraday bars are live capture after 2026-09-07. FORCEMOT
5m stops at 2023-10-25. 360ONE and ABB 15m start at 2025-01-01, and HEROMOTOCO 15m stops at
2025-02-21. This is the 2026-09-07 dev-DB loss: the intraday back-fill restored only part of the
corpus. Regenerating these goldens would write that loss into the oracle.

## What was regenerated

The generator's default path calls `run_walkforward(symbols=None)`, which **re-resolves the universe
from live state**. After the 2026-09-14 universe repair (active 1,322 → 2,291), that would have
swapped names as well as refreshing data. So `scripts/gen_walkforward_goldens.py` gained
**`--pinned`**:

- it reruns each existing golden on its own bounds and resolved universe (the run symbols plus the
  exclusion manifest);
- it **refuses** if the set that runs moves.

It is tested in `tests/test_gen_walkforward_pinned.py`.

`--pinned --write --i-have-approval` on the five daily goldens gave:

| golden | trades | total P&L % | Sharpe | max DD % | digest |
|---|---|---|---|---|---|
| dc1 | 289 → 303 | −52.2 → **+46.3** | −0.34 → +0.21 | 99.1 → 99.1 | `6525c6e6…` → `39d04ad6…` |
| dc2 | 218 → 226 | −39.7 → −15.7 | −0.35 → −0.16 | 96.8 → 96.8 | `681886d5…` → `ebef7fc5…` |
| rrbo_basic | 58 → 62 | +41.3 → +58.8 | 1.97 → 2.68 | 40.6 → 40.2 | `ec05842b…` → `01475d15…` |
| rrbo_trailing | 58 → 62 | +41.3 → +58.8 | 1.97 → 2.68 | 40.6 → 40.2 | `ec05842b…` → `01475d15…` |
| multibagger | — | — | — | — | ⛔ **REFUSED by `--pinned`** |

**multibagger was refused.** 8 names that the July golden excluded (fewer than 300 bars before
eval_start) now qualify: AJMERA, BAJAJELEC, BOROLTD, LLOYDSME, PASUPTAC, RAYMOND, SANOFI and
SAREGAMA. They gained bars from the 09-13 breadth repair (U3), not from the weekend sessions. That
is a universe change, which this sign-off does not cover.

## ⚠ Read the moves as fragility, not news

Three extra bars out of 741 flipped dc1's total P&L from −52% to +46%. The max drawdown is about 99%
in both versions. The aggregate compounds a long losing-and-winning path, so a small shift in
which bars fall inside the 300-bar window reorders the trades and swings the sum. **These goldens
are a drift detector, not evidence about the strategies.** Nothing here revives dc1 or dc2: the
scorer was retired on 2026-09-20 on point-in-time evidence that this harness does not provide.

## State after

`make walkforward`: **5 passed, 4 failed** (gainer_925, multibagger, orb_15m, pdh_pdl). The four
reds are known and attributed above; none is a code regression. Two paths could make them green,
and neither has been taken:

- **multibagger:** a separate sign-off to accept the 8 names (a `--pinned` run would then need to
  admit them, or a fresh regenerate);
- **intraday:** re-back-fill `ohlcv_5m`/`ohlcv_15m` for the pinned names over 2023-07-03 → 2026-06-30
  first. That costs Kite REST time and needs the token. Then regenerate `--pinned`.

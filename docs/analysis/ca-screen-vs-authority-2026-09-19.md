# The 25% gap screen, measured against the authority (2026-09-19)

Item 16's payoff. `corporate_actions` now holds **348 authority-sourced rows** (174 splits,
174 bonuses, 2023-07-04 → 2026-09-11), so for the first time the screen we have been using as
a corporate-action detector can be scored against the body that actually publishes them.

⭐ **Both error directions are measured here. Only one had ever been.**

## False positives — the screen flags things that are not corporate actions

Gap candidates = `|open ÷ prev_close − 1| > 25%` in the test block's liquid pool
(≥200 sessions, median daily traded value ≥ ₹5cr).

| | count | share |
|---|--:|--:|
| flagged by the screen | **225** | |
| confirmed by the authority, **exact ex-date** | **142** | 63.1% |
| confirmed within ±1 session | 142 | 63.1% |
| **false positives** | **83** | **36.9%** |

⭐ **This corrects M70.** That measurement put the screen at **62.5% false-positive** — but on a
sample of **8 events**. On 225 it is **36.9%**. The screen is substantially better than the
small sample implied, and still wrong more than a third of the time, which is far too wrong to
decide what a study drops.

⚠ **Exact and ±1 agree to the row**, so ex-date alignment is correct — there is no off-by-one
between the authority's ex-date and the session the gap appears in.

## False negatives — and these are STRUCTURAL, not noise

The converse direction, never previously measured: of **168** authority actions on liquid-pool
names, the screen catches **146** and misses **22 (13.1%)**.

| action | factor | implied price move | n | caught |
|---|--:|--:|--:|--:|
| bonus | 1.100 | −9.1% | 1 | **0** |
| bonus | 1.200 | −16.7% | 2 | **0** |
| bonus | 1.250 | −20.0% | 2 | **0** |
| bonus | 1.333 | **−25.0%** | 4 | **0** |
| bonus | 1.500 | −33.3% | 12 | 12 |
| bonus / split | 2.000 | −50.0% | 76 | 71 |
| split | 5.000 | −80.0% | 28 | 27 |
| split | 10.000 | −90.0% | 12 | 9 |

⛔⛔ **Nine of the twenty-two misses are INVISIBLE BY CONSTRUCTION.** A small bonus moves the
price by less than the threshold — a 1:10 bonus is −9.1%, a 1:4 bonus −20% — so **no 25% screen
can ever see them, however the data behaves.** This is not a tuning problem; lowering the
threshold to catch a −9.1% bonus would sweep in every ordinary bad day.

⭐ **And the 1.333 row is a boundary bug, not a sensitivity limit.** A 1:3 bonus is
**exactly −25.0%**, and the strict `> 0.25` comparison misses **all four** of them. A screen
whose threshold sits precisely on a common corporate-action ratio will always fail on it.

## What this means for item 5's 3b

3b — the matched-tail contrast, and the last undecided estimand — is a **mean** forward-return
contrast, so one split-induced −89.8% moves it by roughly `0.9/n`. It could not be run on the
screen, and now it does not have to be:

- **Drop by AUTHORITY, not by screen.** 142 of the flagged events are real and 83 are genuine
  price moves — and M70's warning holds in the direction it was aimed: dropping all 225 would
  delete 83 of the most informative sessions in the block.
- **The screen's false negatives matter less for 3b than its false positives**, because a −9.1%
  bonus barely perturbs a mean while a −90% split dominates it. But they are now known rather
  than assumed.
- ⚠ **The authority set is not complete either.** 22 actions produced no detectable gap, of
  which 13 are not explained by size — most likely a missing bar on the ex-date. That is a data
  gap, not a CA gap, and it is recorded here rather than left to be rediscovered.

## Reproducing

```
cd backend && uv run python scripts/backfill_corporate_actions.py \
    --from 2023-07-03 --to 2026-09-19 --dry-run
```
Idempotent; the real run (no `--dry-run`) inserted 348 of 350 parsed records — 1 was a genuine
duplicate within the feed and 1 was for a symbol outside our universe.

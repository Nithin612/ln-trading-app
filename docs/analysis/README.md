# Daily trading-analysis reports

A per-day, evidence-based read of paper-trading performance — what the engine
predicted, what the alerts showed, what you actually traded, and *why* the
result came out the way it did — so each day's mistakes become the next day's
fine-tuning. Real later; paper now.

## Run it

```bash
make analysis                          # today (IST)
make analysis DATE=2026-08-05           # a specific IST day
make analysis DATE=2026-08-05 WEEK_OF=2026-08-05   # + Mon–Fri weekly roll-up
make analysis USER_ID=1                # a specific user (default 1)

# or the slash command (also narrates the result):
/daily-analysis 2026-08-05
/daily-analysis 2026-08-05 --week
```

Under the hood: `backend/scripts/daily_analysis.py` →
`app/services/daily_report.py`. Read-only against Postgres; writes only Markdown
here. Unit + integration tests in `backend/tests/test_daily_report.py`.

## What's in this folder

| File | What it is |
|---|---|
| `YYYY-MM-DD.md` | one day's full report (scorecard, per-trade tape read, risk, takeaways) |
| `WEEK-<monday>.md` | Mon–Fri roll-up + week-over-week realised-P&L comparison |
| `LEDGER.md` | one running line per day — the at-a-glance improvement log |
| `FIX_PLAN.md` | the prioritized code fixes this analysis surfaced (P0–P3) |

## How to read the numbers (definitions)

- **R** — one unit of risk = |entry − stop|. The report measures excursions and
  chase in R so trades of different prices compare directly.
- **Chase (R)** — how far your *fill* drifted from the *signal's* entry, in R,
  signed in the trade's direction. `> 0.33R` ⚠️ is past the "don't-chase"
  ceiling the AlertBell already shows (`alertPresentation.chaseGuidance`).
- **Risk vs 2%** — the rupee risk the position actually carries
  (`qty × |fill − SL|`) ÷ your intended per-trade budget (`capital × risk%`).
  `> 1` means you're risking more than your setting — silently, because the qty
  was sized on the signal's entry→SL distance but you filled somewhere else (or
  clicked Buy more than once, which averages-in and stacks risk).
- **MFE / MAE** — max favourable / adverse excursion over the holding window,
  from the stored 1-minute tape, with the *time* each occurred. "Reached ≥1R"
  is the profit-lock's arm threshold: below it the ratchet never engages and the
  stop stays at the original signal SL.
- **Given back** — peak profit reached minus the current/closing result. The
  core leak: profit made, then surrendered.
- **Exit-policy replay** — `profit_lock_shadow.compare_position`: what the fixed
  ladder / Layered Ratchet / a plain 33% giveback *would* have captured. Shadow
  evidence; it drives no real orders.

## Honesty caveats (what the report can and can't see)

- **Alerts are reconstructed, not replayed.** Raw AlertBell firings live in an
  ephemeral Redis stream (`alerts:live`, capped ~10k). The report rebuilds the
  "what price interacted with your levels" picture from the *durable* record —
  `signals` + `signal_outcomes` (entry-zone / SL / TP touch times). A future
  enhancement is a daily snapshot of the alert stream.
- **Marks are historically correct.** Open-position P&L for a past day is
  recomputed from that day's last 1-minute close — never the mutable
  `positions.unrealized_pnl` column — so re-running a past day reproduces.
- **Temporal bounding.** A report for day D never shows an exit that happened
  after D; a position opened D and closed D+1 reads as *open at D's close*.
- **Gross vs net.** Realised P&L is net of Zerodha charges; intraday MFE/MAE and
  give-back are gross price excursions (costs don't move within the day).
- **Order source isn't stored.** The DB doesn't record whether an entry came
  from the AlertBell, the dashboard, or a manual pick — only manual *exits*
  (`exit_reason`) are distinguishable. Attributing "alert vs manual" entries
  needs a new field (see FIX_PLAN.md).

## The daily discipline

1. After the session (or next morning), run `make analysis` for the trading day.
2. Skim `LEDGER.md` for the trend; open the dated file for the detail.
3. Anything the report surfaces that isn't yet actioned → add it to
   `FIX_PLAN.md` with a priority.
4. On Fridays, run with `WEEK_OF=` for the week-over-week.

The point is a stable measurement spine: the same metrics every day, so
"did the change help?" is answerable with evidence, not vibes.

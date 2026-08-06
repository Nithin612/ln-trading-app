---
description: Generate the daily trading-analysis report into docs/analysis/ and narrate it
argument-hint: "[YYYY-MM-DD] (default: today IST) [--week]"
allowed-tools: Bash(cd:*), Bash(make analysis:*), Bash(uv run:*), Read
---

Produce and explain the daily trading-analysis report.

The argument is: `$ARGUMENTS`

1. Parse the argument: the first token (if present) is an IST date `YYYY-MM-DD`; if
   absent, use today's IST date. If the argument contains `--week`, also emit the
   weekly roll-up for that date's week.
2. Run the generator (read-only against the DB):
   - `make analysis DATE=<date>` — omit `DATE=` entirely if no date was given.
   - add `WEEK_OF=<date>` when `--week` was requested.
   It writes `docs/analysis/<date>.md`, updates `docs/analysis/LEDGER.md`, and (with
   `--week`) `docs/analysis/WEEK-<monday>.md`.
3. Read the generated dated report (and the weekly file if produced).
4. Narrate it back tightly — do NOT recompute numbers, trust the report:
   - the scorecard line (entries/exits, realised, open MTM, given-back, heat, cap breaches);
   - the 2–3 worst trades by give-back or chase, with their numbers and the one-line verdict;
   - engine performance (reached ≥1R count, avg MFE);
   - the top 3 takeaways and a pointer to `docs/analysis/FIX_PLAN.md`.
5. If the report surfaces something new that isn't already in FIX_PLAN.md, say so explicitly.

Keep it concrete and scannable. The report file is the artifact; your message is the read.

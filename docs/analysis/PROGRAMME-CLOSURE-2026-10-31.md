# Programme closure — decided 2026-10-03, executes 2026-10-31

**Decision (the author, 2026-10-03):** end the successor programme cleanly at the sunset, **if the
data allows**. It does (§2). On 2026-10-31 the programme closes, the CAS thread closes with it, and
PR-2 is not run.

## 1. The rule this executes

Pre-committed in the record (PHASES, the round that added it): *"if zero Week-0 items ship by
2026-10-31 the programme CLOSES, ledger archived as the deliverable."* The date and the condition
were fixed before any of the results below existed. Closing is the rule firing, not a choice made
after seeing them.

## 2. Does the data allow it? — checked 2026-10-03

| check | finding | allows closure? |
|---|---|---|
| Has anything shipped? | **No.** PR-1 — the one item that could ship before the sunset — ran once on 2026-10-02 and returned **NULL** (CNC net +0.03 bps/session, NW t 0.017, DSR 0.027; `docs/analysis/pr1-report-2026-10-02.md`). | yes |
| Can anything ship before 2026-10-31? | **No.** PR-2's first read needs 126 valid auction-era sessions — at the measured 73% capture uptime (11 of 15 sessions since 2026-09-10), ≈ June 2027. | yes |
| Does any result argue for continuing? | **No decisive one.** PR-1's descriptives say the old-regime "reversal" was mostly the last print's bounce (G −64 bps; at the close −63.7 bps; s ending at P1525 −14.5 bps, t −9). They do not refute an auction-era effect (§10i) — but nothing measures one either: Stage 2's ρ −0.272 rests on 7 sessions whose data was lost, and the post-close capture has 0 sessions. | yes |
| Would closing destroy anything unrecoverable? | **No.** Every table, artefact and pre-registration is kept; the two holdouts stay sealed and unspent. | yes |

## 3. What closes, and what is kept

**Closes:** the successor programme as active research (no new hypotheses, builds or tuning) ·
the CAS thread · PR-2 (never run; its frozen pre-registration and §9a stay on record, and a revival
would be a NEW trial under a new pre-registration).

**Kept, untouched:** every table (`cas_daily`, `cas_postclose_daily`, `ohlcv_*`, `ledger_entries`,
…) · all pre-registrations, reports and run artefacts · **both holdouts, still SEALED** (holdout-1
2021-01-01 → 2023-07-02, holdout-2 2019-10-01 → 2020-12-31) — unread, so they remain the most
valuable thing any future programme can inherit · the platform itself (paper trading, ingestion),
which this decision does not touch.

## 4. The 2026-10-31 checklist (Claude raises it that day — `docs/PHASES.md` CONTINUE HERE)

1. Re-confirm §2: nothing shipped between 2026-10-03 and 2026-10-31.
2. **Archive the ledger as the deliverable:** export `ledger_entries` with `app.services.ledger.export_day`
   for every day that has rows, plus a tarball of the research record (`docs/analysis/` pre-registrations,
   reports, PR-1 run artefacts, `holdout-seals.json`, `RETIREMENT-2026-09-20.md`, `BUILD_QUEUE.md`),
   to the backup root `/home/nithin/code/back_ups/trading_platform/`, with a sha256 manifest.
   ⚠ That root is on this machine: copying the archive off-box is the author's step (RUNBOOK §8b).
3. **Stop the CAS capture** — with the worker STOPPED first (the mixed-version rule): remove the
   `capture-cas-window` beat entry (task code and tables stay), and remove the four `cas_watch.py`
   cron lines (an alarm for a closed thread is noise). Restart the worker only if the platform still
   needs it.
4. Final status: the PHASES top block becomes "PROGRAMME CLOSED 2026-10-31"; CLAUDE.md, CHANGELOG
   and memory follow.

## 5. Re-opening

Only as a NEW programme: a new pre-registration committed before any outcome is read, a trial count
that starts from this programme's ledger (N = 20 + PR-1's 2 = 22 trials spent), and the sealed
holdouts opened under their own rules, never as a convenience.

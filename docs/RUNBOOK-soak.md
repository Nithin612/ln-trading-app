# Runbook — quiet-box live-worker soak

The market-hours stability + latency measurement for the Phase-3 live
worker. This is the exact ritual; it supersedes the ad-hoc commands used
on 2026-07-13. Full incident history: `phases/phase-03-realtime.md`
§Second soak.

## TL;DR (what you actually type)

```bash
# ~08:00–09:10 IST, before the 09:15 open:
cd ~/code/agent/Claude/trading-platform
make status                                   # postgres(5433)+redis up? if not: make up
cd backend && uv run python scripts/kite_login.py && cd ..   # paste redirect URL back

# start before 09:15 and LEAVE IT RUNNING:
make soak
```

Then: **leave the box awake and idle until 15:30 IST** (no pytest, no
cargo/maturin builds, do NOT start `make backend`). At ~15:40 the worker
prints its stats line and exits on its own (`clean exit (session over)`).
Afterwards, open Claude and say **"continue here"** — it reads the log +
recording and produces the verdict.

That's it. `make soak` handles everything that was fumbled by hand on
07-13 (absolute record path, self-logging, clearing the stale broker
queue).

## What `make soak` does for you

- Creates `recordings/` and records ticks to an **absolute** path
  `recordings/soak-YYYY-MM-DD.jsonl` (07-13 bug: a relative path resolved
  under `backend/` because the supervisor `cd`s there).
- Tees the console to `recordings/soak-YYYY-MM-DD.log` with **append** so
  restarts never truncate the stats (07-13 bug: `tee` without `-a` wiped
  earlier runs' logs).
- `DEL`s the Redis `celery` broker list first — no consumer runs during a
  soak, and stale queued tasks otherwise sit in memory.
- Runs the worker under the restart supervisor (`make live-worker`).

## Supervisor exit contract

- **exit 0** — session over → supervisor stops (no restart). Normal at ~15:40.
- **exit 4** — no usable Kite token → waits 60 s, prompts for `kite_login`.
- **anything else** (e.g. 3 = WS died mid-session) → restarts after 5 s.
  A restart re-subscribes, appends a new recording header, and gap-fills;
  the recording + replay handle multi-header files natively.

## Watching it (optional — Option A is hands-off)

The worker now logs a **heartbeat every 30 s**:

```
live-worker heartbeat: in_q=0/10000 writer_q=0/10000 stats={...} lat_p50=7.5 lat_p99=20.0 n=1234
```

Healthy = `in_q` and `writer_q` near 0. If either climbs toward 10000 and
stays there, the consumer or writer is falling behind (paste it to Claude).
This heartbeat is the thing we were missing on 07-13 when a run degraded
silently for two hours.

## The stats line at close (the measurement)

```
live-worker stats: {...} latency: {p50_ms, p99_ms, max_ms} dwell: {...} processing: {...} avg_batch=...
```

- `latency` = end-to-end enqueue→published (the p99 < 10 ms phase target —
  though at ~2,055 instruments the target is under review; 07-13 run #4
  got p50 7.5 / p99 in (20,50]).
- `dwell` = queue wait (GIL); `processing` = pure compute. If p99 is huge
  (seconds), the WS died and a backlog wedged — that run's latency is void.

## Known-good state going in (as of 2026-07-13 night)

- Redis OOM fix shipped: per-candle Celery dispatch is OFF by default, so
  the broker list no longer grows during a soak. `make soak` clears any
  residue. maxmemory is 2 GB in compose (applies on next redis recreate;
  the running instance is already safe).
- Writer shutdown race + 36-min drain wedge fixed; WS-death now restarts
  promptly.
- **07-13 candle data was partially rebuilt** from Kite (morning solid;
  afternoon top-up ~92% of stocks; ~8% and all 1m still gappy). If a
  future walk-forward needs 07-13, re-run the throttled full-session
  rebuild with a fresh token first (see the ledger §Second soak / the
  rebuild scripts pattern). Not urgent — 1d/EOD candles are unaffected.

## If something looks wrong

Paste the terminal output to Claude and say "continue here". Every failure
mode from 07-13 is now either fixed or self-announcing in the heartbeat.
Trading days are not scarce — a soak that fails *observably* is still a
good experiment; we re-run.

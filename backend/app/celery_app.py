"""Celery application factory — Phase 6.

Two scheduled tasks:
  - nightly_signal_generation: runs at 18:00 IST (12:30 UTC) on weekdays,
    after bhavcopy is ingested and EOD data is settled.
  - poll_filings: runs every 60 seconds during market hours to ingest NSE/BSE
    corporate announcements.

Start worker:
    cd backend && celery -A app.celery_app worker -l info

Start beat scheduler:
    cd backend && celery -A app.celery_app beat -l info
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "trading_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.signal_tasks",
        "app.tasks.filing_tasks",
        "app.tasks.position_monitor",
        "app.tasks.fo_tasks",
        "app.tasks.expiry_tasks",
        "app.tasks.market_data_tasks",
        "app.tasks.profile_tasks",
        "app.tasks.pair_tasks",
        "app.tasks.circuit_tasks",
        "app.tasks.corporate_action_tasks",
        "app.tasks.cas_tasks",
        "app.tasks.health_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    # 19:15 IST = 13:45 UTC — AFTER FII/DII (18:30) and equities EOD (18:40)
    # so generation scores same-day candles + flows. (Was 18:00 IST, which
    # always consumed stale data — no EOD ingestion even existed then.)
    "nightly-signal-generation": {
        "task": "app.tasks.signal_tasks.nightly_signal_generation",
        "schedule": crontab(hour=13, minute=45, day_of_week="1-5"),
    },
    # Pair-trading shadow minter (Phase 6.5b) — 19:25 IST = 13:55 UTC, AFTER EOD bar
    # ingestion (18:40 IST) + nightly generation (19:15 IST), so it screens fresh daily
    # bars. Shadow-only (writes pair_signals, mints no order).
    "mint-pair-signals": {
        "task": "app.tasks.pair_tasks.mint_pair_signals",
        "schedule": crontab(hour=13, minute=55, day_of_week="1-5"),
    },
    # Poll filings every 60 seconds (Celery beat minimum granularity is seconds)
    "poll-filings": {
        "task": "app.tasks.filing_tasks.poll_filings",
        "schedule": 60.0,
    },
    # Monitor open paper positions every 60s during market hours (9:15–15:30 IST).
    # IST offsets: 9:15 IST = 3:45 UTC; 15:30 IST = 10:00 UTC. This crontab is a
    # COARSE gate (03:00–10:59 UTC = 08:30–16:29 IST, a superset); the task's
    # in-run `is_market_session` guard is authoritative and enforces the exact
    # 09:15–15:30 IST window (a crontab hour-range can't express :45-precision,
    # and hour="3-9" used to fire the 08:30 IST pre-open beat that auto-closed
    # positions on the previous session's stale close).
    "monitor-positions": {
        "task": "app.tasks.position_monitor.monitor_positions",
        "schedule": crontab(
            minute="*/1",
            hour="3-10",
            day_of_week="1-5",
        ),
    },
    # F&O EOD recorders: bhavcopy + India VIX after NSE publishes (~18:30 IST)
    # 18:45 IST = 13:15 UTC
    "fo-eod-ingestion": {
        "task": "app.tasks.fo_tasks.fo_eod_ingestion",
        "schedule": crontab(hour=13, minute=15, day_of_week="1-5"),
    },
    # CAS (Closing Auction Session) capture (Stage 1) — every minute over 09:00–10:59 UTC
    # (14:30–16:29 IST, a superset); the task self-guards to the exact CAS window 15:15–15:33 IST
    # (= 09:45–10:03 UTC, which a single crontab can't express). Research-only; no order path.
    "capture-cas-window": {
        "task": "app.tasks.cas_tasks.capture_cas_window",
        "schedule": crontab(minute="*/1", hour="9,10", day_of_week="1-5"),
    },
    # A40 — the ABSENCE alarm. 10:10 UTC = 15:40 IST, seven minutes after the window closes,
    # so a zero row-count is a MISS rather than "not finished yet". Runs a few times so a
    # worker that comes back late still reports; the notifier's throttle collapses repeats.
    "check-cas-coverage": {
        "task": "app.tasks.cas_tasks.check_cas_coverage",
        "schedule": crontab(minute="10,40", hour="10,11,12", day_of_week="1-5"),
    },
    # A40 — role heartbeat. Absence of the key IS the signal, so this only has to be more
    # frequent than HEARTBEAT_TTL_S; it is deliberately cheap.
    "worker-heartbeat": {
        "task": "app.tasks.health_tasks.worker_heartbeat",
        "schedule": crontab(minute="*/2"),
    },
    # ⭐ U1 — `kite_instruments` had no scheduled owner and stayed EMPTY for five
    # days after the 2026-09-07 DB loss, while live_worker logged `up: 0 instruments`
    # and ran dark. 02:30 UTC = 08:00 IST, before the 09:15 session so the worker's
    # subscription universe is fresh. Token-free by design — see the task's docstring.
    "sync-kite-instruments": {
        "task": "app.tasks.market_data_tasks.sync_kite_instruments",
        "schedule": crontab(hour=2, minute=30, day_of_week="1-5"),
    },
    # D2′a — materialise the universe rule's verdict. 03:05 UTC = 08:35 IST, AFTER
    # sync-kite-instruments (02:30 UTC) because the rule reads kite_instruments, and
    # before the 09:15 session. ⚠ SHADOW ONLY — it records an outcome and measures the
    # diff against `is_active`; it does not write the flag.
    "materialise-universe": {
        "task": "app.tasks.market_data_tasks.materialise_universe",
        "schedule": crontab(hour=3, minute=5, day_of_week="1-5"),
    },
    # A36 — calendar-coverage expiry alarm. Once per trading morning (4:00 UTC = 9:30 IST);
    # the horizon moves slowly, so a daily read with lead time is enough, and the notifier's
    # 15-min throttle collapses any repeat within a day.
    "check-calendar-coverage": {
        "task": "app.tasks.health_tasks.check_calendar_coverage",
        "schedule": crontab(hour=4, minute=0, day_of_week="1-5"),
    },
    # Option-chain snapshots every minute in the market window (task itself
    # re-checks 9:15–15:30 IST and idles without a Kite token)
    "record-option-chains": {
        "task": "app.tasks.fo_tasks.record_option_chains",
        "schedule": crontab(
            minute="*/1",
            hour="3-10",
            day_of_week="1-5",
        ),
    },
    # Circuit-band cache (Phase 6.8.3) — refresh lower/upper circuit limits for
    # the active universe every 15 min in the market window (bands are intraday-
    # static; the task re-checks hours/holiday/token and idles otherwise). TTL
    # (circuit_band_ttl_s=1800) exceeds the cadence, so a live band never expires
    # between refreshes; when the worker stops, bands go stale and the gate fails
    # open. First fire 3:45 UTC = 9:15 IST covers the market-open entry burst.
    "refresh-circuit-bands": {
        "task": "app.tasks.circuit_tasks.refresh_circuit_bands",
        "schedule": crontab(
            minute="*/15",
            hour="3-10",
            day_of_week="1-5",
        ),
    },
    # Corporate-action adjustment of OPEN paper positions (Phase 6.8.5). Pre-market
    # 08:15 IST = 02:45 UTC, AHEAD of the position monitor's 08:30 IST start, so a
    # held position is corrected for a split/bonus before the stock trades ex.
    # Idempotent (ledger) — a re-run is a no-op.
    "apply-corporate-actions": {
        "task": "app.tasks.corporate_action_tasks.apply_corporate_actions",
        "schedule": crontab(hour=2, minute=45, day_of_week="1-5"),
    },
    # Signal expiry sweeper (SIGNAL_ENGINE.md §5: every 5 minutes). Weekday
    # window covers intraday cutoffs through post-close swing expiries;
    # scalp signals minted off-hours expire on the next sweep.
    "sweep-expired-signals": {
        "task": "app.tasks.expiry_tasks.sweep_expired_signals",
        "schedule": crontab(minute="*/5", day_of_week="1-5"),
    },
    # FII/DII daily flows — NSE publishes EOD; 18:30 IST = 13:00 UTC.
    "ingest-fii-dii": {
        "task": "app.tasks.market_data_tasks.ingest_fii_dii",
        "schedule": crontab(hour=13, minute=0, day_of_week="1-5"),
    },
    # Equities bhavcopy → ohlcv_1d; 18:40 IST = 13:10 UTC (before nightly
    # generation at 19:15 IST).
    "ingest-equities-eod": {
        "task": "app.tasks.market_data_tasks.ingest_equities_eod",
        "schedule": crontab(hour=13, minute=10, day_of_week="1-5"),
    },
    # Per-profile suggestion pipelines — 19:25 IST = 13:55 UTC, after the
    # legacy nightly generation so both consume the same fresh EOD data.
    "nightly-profile-suggestions": {
        "task": "app.tasks.profile_tasks.nightly_suggestions",
        "schedule": crontab(hour=13, minute=55, day_of_week="1-5"),
    },
    # ── Intraday profile schedules ───────────────────────────────────────────
    # These had NO caller. `nightly_suggestions` only ever ran the 'eod'
    # schedule, and `on_close_suggestions` was a Phase-3 stub, so the
    # `intraday_15m` and `time_0925` profiles could never fire no matter what
    # their status said — the Intraday menu was structurally unable to populate.
    #
    # 15m bars close at :00/:15/:30/:45 past the hour. The task runs one minute
    # LATER so the bar it scores is complete: computing on a forming candle is a
    # look-ahead violation, and the whole point of the committed layer is that it
    # is not that.
    #
    # The window is 04:01–09:46 UTC = 09:31–15:16 IST, and both ends are
    # deliberate:
    #   - It does NOT start at 03:46 UTC (09:16 IST). That fire passes the
    #     session guard but no 15m bar of the day has closed yet (the first
    #     closes 09:30 IST), so it would score the PREVIOUS session's 15:15 bar
    #     at yesterday's price — and then hold the one-per-(stock, profile)
    #     dedup slot for the rest of the day, suppressing every genuine run.
    #   - 09:46 UTC (15:16 IST) is past the 15:15 IST intraday cutoff, so
    #     `_process_stock` refuses to mint there (a signal minted after the
    #     cutoff would roll its deadline to the next calendar day). It is kept
    #     in the window only so the session's 15:00–15:15 bar is still SCORED
    #     for evidence; nothing is minted from it.
    # The task's own `is_market_session` guard remains authoritative — a crontab
    # cannot express :15-minute precision across an hour range.
    "intraday-15m-suggestions": {
        "task": "app.tasks.profile_tasks.intraday_suggestions",
        "schedule": crontab(minute="1,16,31,46", hour="4-9", day_of_week="1-5"),
        "kwargs": {"schedule": "intraday_15m"},
    },
    # 09:25 IST = 03:55 UTC — the top-gainer screen fires ONCE, on the bar that
    # closes at 09:25, and the profile is built around that single decision point.
    "intraday-0925-suggestions": {
        "task": "app.tasks.profile_tasks.intraday_suggestions",
        "schedule": crontab(hour=3, minute=56, day_of_week="1-5"),
        "kwargs": {"schedule": "time_0925"},
    },
}

"""A15 — a scheduling window must be at least as wide as its scheduler's tick interval.

The reference incident: a 25-minute close window against a 30-minute timer missed the close on
two consecutive days, because a tick can land outside a window narrower than the interval. Our
CAS capture has the exact exposure — an 18-minute window (15:15–15:33 IST) whose miss is
**unrecoverable** (the closing auction cannot be replayed). It is safe today (a 1-minute beat),
but nothing stopped a future edit from coarsening the beat to `*/20` and silently never firing.

This pins two invariants that no other test covers:

  1. the CAS window width ≥ the CAS beat's tick interval (A15), and
  2. the coverage-check's close time equals the capture window's end — if they drift, the
     'window missed' alarm judges a different window than the one that captured.
"""

from __future__ import annotations

import importlib
from datetime import date, datetime

from app.celery_app import celery_app


def _entry_for(task_name: str):
    for entry in celery_app.conf.beat_schedule.values():
        if entry["task"] == task_name:
            return entry
    raise AssertionError(f"no beat entry for {task_name}")


def _min_tick_minutes(cron) -> int:
    """Smallest gap in minutes between consecutive fire times of a celery crontab whose hour
    set is contiguous. For `minute='*/1'` the minute set is {0..59} ⇒ 1; for `'10,40'` ⇒ 30."""
    minutes = sorted(int(m) for m in cron.minute)
    if len(minutes) <= 1:
        return 60  # once per hour
    gaps = [b - a for a, b in zip(minutes, minutes[1:], strict=False)]
    gaps.append(60 - minutes[-1] + minutes[0])  # wrap into the next hour
    return min(gaps)


def _cas_window_minutes() -> int:
    from app.tasks.cas_tasks import _CAS_END, _CAS_START

    d = date(2026, 1, 1)
    delta = datetime.combine(d, _CAS_END) - datetime.combine(d, _CAS_START)
    return int(delta.total_seconds() // 60)


def test_cas_window_is_at_least_the_beat_tick_interval() -> None:
    """A15 — a tick can fall outside a window narrower than the interval, and a missed CAS
    window cannot be back-filled."""
    tick = _min_tick_minutes(_entry_for("app.tasks.cas_tasks.capture_cas_window")["schedule"])
    window = _cas_window_minutes()
    assert window >= tick, (
        f"CAS window is {window} min but the beat ticks every {tick} min — a tick can miss it, "
        "and a missed closing auction is unrecoverable"
    )


def test_min_tick_minutes_reads_a_crontab_correctly() -> None:
    """Guards the helper itself, so the invariant above cannot pass vacuously."""
    from celery.schedules import crontab

    assert _min_tick_minutes(crontab(minute="*/1")) == 1
    assert _min_tick_minutes(crontab(minute="10,40")) == 30
    assert _min_tick_minutes(crontab(minute="0")) == 60


def test_coverage_close_matches_the_capture_window_end() -> None:
    """The 'window missed' alarm must judge the SAME window the capture task guards."""
    from app.services.worker_health import CAS_WINDOW_CLOSE
    from app.tasks.cas_tasks import _CAS_END

    assert CAS_WINDOW_CLOSE == (_CAS_END.hour, _CAS_END.minute)


# ── U1 (2026-09-13): the instruments table finally has a scheduled owner ──────


def test_kite_instruments_has_a_scheduled_owner() -> None:
    """REGRESSION. `kite_instruments` had exactly one writer — an admin HTTP
    endpoint — so nothing scheduled ever refreshed it. After the 2026-09-07
    dev-DB loss it stayed EMPTY for five days while `live_worker` logged
    `up: 0 instruments` and ran dark; tick/CAS/intraday capture is real-time
    only, so those sessions are gone. A beat entry must exist and must point at
    a task that is actually registered — a typo'd task name is a beat entry
    that silently never fires, which is the same failure wearing a hat."""
    # Celery registers a task when its module is imported; `include` is lazy, so
    # the test must import it the way the worker does. That is the point — a beat
    # entry naming a module absent from `include` would never fire.
    for mod in celery_app.conf.include:
        importlib.import_module(mod)

    entry = _entry_for("app.tasks.market_data_tasks.sync_kite_instruments")
    assert entry["task"] in celery_app.tasks


def test_instrument_sync_runs_before_the_session_opens() -> None:
    """The subscription universe must be fresh when the worker starts. The NSE
    session opens 09:15 IST (03:45 UTC); the sync is scheduled 02:30 UTC."""
    cron = _entry_for("app.tasks.market_data_tasks.sync_kite_instruments")["schedule"]
    hours = {int(h) for h in cron.hour}
    assert hours == {2}
    assert {int(m) for m in cron.minute} == {30}
    # 02:30 UTC = 08:00 IST, comfortably before the 03:45 UTC open.
    assert max(hours) < 3


def test_instrument_sync_is_weekdays_only() -> None:
    """NSE does not trade at the weekend; a dump fetched then is the Friday one."""
    cron = _entry_for("app.tasks.market_data_tasks.sync_kite_instruments")["schedule"]
    assert {int(d) for d in cron.day_of_week} == {1, 2, 3, 4, 5}


def test_the_universe_materialiser_runs_after_the_instrument_sync() -> None:
    """D2′a — the rule reads `kite_instruments`, so evaluating before the dump is
    refreshed would judge today's universe against yesterday's instruments. Pinned
    because the two beat entries are 35 minutes apart and nothing else enforces the
    order."""
    for mod in celery_app.conf.include:
        importlib.import_module(mod)

    sync = _entry_for("app.tasks.market_data_tasks.sync_kite_instruments")["schedule"]
    univ = _entry_for("app.tasks.market_data_tasks.materialise_universe")["schedule"]

    sync_min = min(int(h) for h in sync.hour) * 60 + min(int(m) for m in sync.minute)
    univ_min = min(int(h) for h in univ.hour) * 60 + min(int(m) for m in univ.minute)
    assert sync_min < univ_min
    # …and both still land before the 09:15 IST open (03:45 UTC).
    assert univ_min < 3 * 60 + 45


def test_the_universe_materialiser_is_registered() -> None:
    for mod in celery_app.conf.include:
        importlib.import_module(mod)
    entry = _entry_for("app.tasks.market_data_tasks.materialise_universe")
    assert entry["task"] in celery_app.tasks


def test_the_coverage_alarm_runs_after_both_eod_ingests_and_before_generation() -> None:
    """U4′ — the beat comment makes a checkable ordering claim and nothing enforced it.

    The alarm reads the LATEST session's breadth, so running it before the equity
    (13:10 UTC) or F&O (13:15) ingest would measure yesterday's feed and read healthy
    through a collapse. Running it after nightly generation (13:45) would flag a thin
    feed only once the scan had already consumed it. A future reschedule of any of the
    four silently breaks that, which is exactly what this pins — same shape as
    `test_the_universe_materialiser_runs_after_the_instrument_sync` above."""
    for mod in celery_app.conf.include:
        importlib.import_module(mod)

    def _minute_of_day(task: str) -> int:
        cron = _entry_for(task)["schedule"]
        return min(int(h) for h in cron.hour) * 60 + min(int(m) for m in cron.minute)

    equities = _minute_of_day("app.tasks.market_data_tasks.ingest_equities_eod")
    fo = _minute_of_day("app.tasks.fo_tasks.fo_eod_ingestion")
    coverage = _minute_of_day("app.tasks.health_tasks.check_feed_coverage")
    generation = _minute_of_day("app.tasks.signal_tasks.nightly_signal_generation")

    assert max(equities, fo) < coverage, "coverage would measure a pre-ingest feed"
    assert coverage < generation, "a thin feed must be flagged before the scan uses it"


def test_the_coverage_alarm_is_weekdays_only() -> None:
    """NSE does not trade at the weekend, so there is no new session to judge and the
    trailing median would be compared against a feed nobody wrote."""
    cron = _entry_for("app.tasks.health_tasks.check_feed_coverage")["schedule"]
    assert {int(d) for d in cron.day_of_week} == {1, 2, 3, 4, 5}

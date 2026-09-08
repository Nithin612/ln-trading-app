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

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
    # 18:00 IST = 12:30 UTC; runs Mon–Fri only
    "nightly-signal-generation": {
        "task": "app.tasks.signal_tasks.nightly_signal_generation",
        "schedule": crontab(hour=12, minute=30, day_of_week="1-5"),
    },
    # Poll filings every 60 seconds (Celery beat minimum granularity is seconds)
    "poll-filings": {
        "task": "app.tasks.filing_tasks.poll_filings",
        "schedule": 60.0,
    },
    # Monitor open paper positions every 60s during market hours (9:15–15:30 IST)
    # IST offsets: 9:15 IST = 3:45 UTC; 15:30 IST = 10:00 UTC
    "monitor-positions": {
        "task": "app.tasks.position_monitor.monitor_positions",
        "schedule": crontab(
            minute="*/1",
            hour="3-9",
            day_of_week="1-5",
        ),
    },
    # F&O EOD recorders: bhavcopy + India VIX after NSE publishes (~18:30 IST)
    # 18:45 IST = 13:15 UTC
    "fo-eod-ingestion": {
        "task": "app.tasks.fo_tasks.fo_eod_ingestion",
        "schedule": crontab(hour=13, minute=15, day_of_week="1-5"),
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
}

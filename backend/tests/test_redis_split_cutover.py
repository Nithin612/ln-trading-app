"""A41 cutover — the durable keys move WITH their state, or the split loses the thing it exists
to protect. The canary that matters: the outcome recorder's consumer-group offset and its
pending (delivered, not yet acked) entries must survive the copy, or every un-recorded outcome
in flight at cutover is silently skipped (the group would be recreated at `$`).

Source = the suite's db 15 (flushed per test by conftest); target = db 14, flushed here.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import redis as redis_sync
from app.core.config import settings
from scripts.redis_split_cutover import copy, fresh_heartbeats, plan, restore_ttl_ms

TARGET_URL = settings.redis_url.rsplit("/", 1)[0] + "/14"


@pytest.fixture
def pair() -> Iterator[tuple[redis_sync.Redis, redis_sync.Redis]]:
    assert settings.redis_url.endswith("/15")
    src = redis_sync.from_url(settings.redis_url, decode_responses=True)
    dst = redis_sync.from_url(TARGET_URL, decode_responses=True)
    src.flushdb()
    dst.flushdb()
    yield src, dst
    src.flushdb()
    dst.flushdb()


def test_stream_moves_with_its_consumer_group_and_pending_entries(pair) -> None:  # type: ignore[no-untyped-def]
    src, dst = pair
    stream = settings.live_alert_stream
    src.xadd(stream, {"sid": "1"})
    src.xadd(stream, {"sid": "2"})
    src.xgroup_create(stream, "outcome-recorder", id="0")
    src.xreadgroup("outcome-recorder", "worker-1", {stream: ">"}, count=1)  # 1 pending

    items = plan(src, dst)
    assert [p.key for p in items] == [stream]
    assert copy(src, dst, items, replace=False) == 1

    assert dst.xlen(stream) == 2
    groups = dst.xinfo_groups(stream)
    assert [(g["name"], g["pending"]) for g in groups] == [("outcome-recorder", 1)]
    # the undelivered entry is still deliverable from the copied offset
    rest = dst.xreadgroup("outcome-recorder", "worker-1", {stream: ">"})
    assert [f["sid"] for _, entries in rest for _, f in entries] == ["2"]


def test_ttl_is_carried_and_cache_keys_are_left_behind(pair) -> None:  # type: ignore[no-untyped-def]
    src, dst = pair
    src.hset("tickmode:health:2026-10-01", mapping={"degraded": 3})
    src.expire("tickmode:health:2026-10-01", 500_000)
    src.set("provisional:health:2026-10-01", "{}", ex=400_000)
    src.set("liveworker:universe:last", "2291", ex=2_000_000)
    src.set("ltp:42", "101.5", ex=600)  # cache-class — must NOT move

    items = plan(src, dst)
    assert sorted(p.key for p in items) == [
        "liveworker:universe:last",
        "provisional:health:2026-10-01",
        "tickmode:health:2026-10-01",
    ]
    copy(src, dst, items, replace=False)
    assert dst.hgetall("tickmode:health:2026-10-01") == {"degraded": "3"}
    assert 499_000 <= dst.ttl("tickmode:health:2026-10-01") <= 500_000
    assert dst.exists("ltp:42") == 0


def test_existing_target_key_is_not_overwritten_without_replace(pair) -> None:  # type: ignore[no-untyped-def]
    src, dst = pair
    src.set("liveworker:universe:last", "2291", ex=1000)
    dst.set("liveworker:universe:last", "9999", ex=1000)
    items = plan(src, dst)
    assert items[0].exists_on_target
    with pytest.raises(ValueError, match="exists on target"):
        copy(src, dst, items, replace=False)  # refuses — never a silent skip
    assert dst.get("liveworker:universe:last") == "9999"
    assert copy(src, dst, items, replace=True) == 1
    assert dst.get("liveworker:universe:last") == "2291"


def test_a_running_worker_is_detected(pair) -> None:  # type: ignore[no-untyped-def]
    src, _ = pair
    assert fresh_heartbeats(src) == []
    src.set("worker:heartbeat:celery", "2026-10-03T10:00:00+00:00", ex=600)
    assert fresh_heartbeats(src) == ["worker:heartbeat:celery"]


def test_restore_ttl_never_turns_an_expiring_record_permanent() -> None:
    """RESTORE's ttl 0 means NO EXPIRY — a PTTL of 0 (last millisecond) must skip, not
    become a permanent key on a noeviction instance."""
    assert restore_ttl_ms(-1) == 0  # persistent stays persistent
    assert restore_ttl_ms(1234) == 1234
    assert restore_ttl_ms(0) is None
    assert restore_ttl_ms(-2) is None

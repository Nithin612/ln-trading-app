"""U1 — the live worker's subscription-universe startup guard (2026-09-13).

REGRESSION. Between 2026-09-07 and 09-12 `kite_instruments` was empty, so
`_build_token_stock_map` returned {} and `live_worker` started five times
logging `up: 0 instruments` before running a whole session doing nothing.
A zero was indistinguishable from a quiet market because nothing asserted
the universe was non-empty, and tick/CAS/intraday capture is real-time-only
— those five sessions cannot be back-filled.

Every test below fails on the pre-guard code, which had no such check.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.broker.universe_guard import (
    UNIVERSE_KEY,
    UNIVERSE_TTL_S,
    assess_universe,
    check_and_record_universe,
)


class _FakeRedis:
    """Minimal sync-Redis stand-in; `boom` makes every call raise."""

    def __init__(self, initial: str | None = None, boom: bool = False) -> None:
        self.store: dict[str, Any] = {} if initial is None else {UNIVERSE_KEY: initial}
        self.boom = boom
        self.set_calls: list[tuple[str, Any, int | None]] = []
        self.expire_calls: list[tuple[str, int]] = []

    def get(self, key: str) -> Any:
        if self.boom:
            raise ConnectionError("redis down")
        return self.store.get(key)

    def set(self, key: str, value: Any, ex: int | None = None) -> None:
        if self.boom:
            raise ConnectionError("redis down")
        self.store[key] = str(value)
        self.set_calls.append((key, value, ex))

    def expire(self, key: str, ttl: int) -> None:
        if self.boom:
            raise ConnectionError("redis down")
        self.expire_calls.append((key, ttl))


# ── the pure predicate ────────────────────────────────────────────────────


def test_empty_universe_is_refused() -> None:
    """The exact 2026-09-07 state: a universe of 0 can never be correct."""
    reason = assess_universe(0, previous=1500, min_fraction=0.5)
    assert reason is not None
    assert "EMPTY" in reason


def test_empty_universe_refused_even_with_no_history() -> None:
    """The EMPTY arm must not depend on a recorded baseline — on 09-07 there
    was none, and that is precisely when the guard has to fire."""
    assert assess_universe(0, previous=None, min_fraction=0.5) is not None


def test_negative_count_is_refused() -> None:
    assert assess_universe(-1, previous=None, min_fraction=0.5) is not None


def test_healthy_universe_passes() -> None:
    assert assess_universe(1500, previous=1490, min_fraction=0.5) is None


def test_first_ever_run_passes_with_no_baseline() -> None:
    """No previous count recorded ⇒ the collapse arm cannot fire."""
    assert assess_universe(1500, previous=None, min_fraction=0.5) is None


def test_collapse_below_fraction_is_refused() -> None:
    reason = assess_universe(700, previous=1500, min_fraction=0.5)
    assert reason is not None
    assert "COLLAPSED" in reason
    assert "700" in reason and "1500" in reason


def test_collapse_boundary_is_inclusive_of_the_fraction() -> None:
    """Exactly at the fraction is allowed; a hair under is not."""
    assert assess_universe(750, previous=1500, min_fraction=0.5) is None
    assert assess_universe(749, previous=1500, min_fraction=0.5) is not None


def test_growth_never_refused() -> None:
    """The pending universe repair will roughly double this number — the guard
    must not block the fix it exists to protect."""
    assert assess_universe(2290, previous=1322, min_fraction=0.5) is None


def test_zero_fraction_disables_only_the_collapse_arm() -> None:
    assert assess_universe(1, previous=100_000, min_fraction=0.0) is None
    assert assess_universe(0, previous=100_000, min_fraction=0.0) is not None


# ── the Redis-backed wrapper ──────────────────────────────────────────────


def test_records_the_count_with_a_ttl_on_success() -> None:
    r = _FakeRedis()
    assert check_and_record_universe(r, 1500, 0.5) is None
    assert r.store[UNIVERSE_KEY] == "1500"
    # Every cache key gets a TTL (trading-domain.md Redis contract).
    assert r.set_calls[0][2] is not None and r.set_calls[0][2] > 0


def test_reads_the_previous_count_to_detect_a_collapse() -> None:
    r = _FakeRedis(initial="1500")
    assert check_and_record_universe(r, 700, 0.5) is not None


def test_a_refusal_does_not_overwrite_the_baseline() -> None:
    """Otherwise a second start would compare against the collapsed number and
    silently accept it — the guard would disarm itself after one bad morning."""
    r = _FakeRedis(initial="1500")
    assert check_and_record_universe(r, 700, 0.5) is not None
    assert r.store[UNIVERSE_KEY] == "1500"
    assert r.set_calls == []


def test_fails_open_when_redis_is_unreachable() -> None:
    """A guard must never be the reason a healthy worker cannot start."""
    r = _FakeRedis(boom=True)
    assert check_and_record_universe(r, 1500, 0.5) is None


def test_still_refuses_an_empty_universe_when_redis_is_unreachable() -> None:
    """Fail-open applies to the BASELINE, not to the zero — the arm that
    matters must survive an outage of the store that feeds the other arm."""
    r = _FakeRedis(boom=True)
    assert check_and_record_universe(r, 0, 0.5) is not None


def test_unparseable_baseline_is_treated_as_absent() -> None:
    r = _FakeRedis(initial="not-a-number")
    assert check_and_record_universe(r, 1500, 0.5) is None


# ── the absolute floor and the high-water ratchet (bug-hunter, 2026-09-13) ──


def test_absolute_floor_refuses_below_min_count() -> None:
    """A ratio test has nothing to compare against on a first run, and cannot
    see a collapse delivered in small steps. This arm can."""
    reason = assess_universe(300, previous=None, min_fraction=0.5, min_count=500)
    assert reason is not None
    assert "floor" in reason


def test_absolute_floor_is_off_when_min_count_is_zero() -> None:
    assert assess_universe(1, previous=None, min_fraction=0.5, min_count=0) is None


def test_floor_is_inclusive_at_min_count() -> None:
    assert assess_universe(500, previous=None, min_fraction=0.5, min_count=500) is None
    assert assess_universe(499, previous=None, min_fraction=0.5, min_count=500) is not None


def test_a_staged_collapse_cannot_walk_under_the_ratio_guard() -> None:
    """REGRESSION. The baseline used to be re-written on EVERY accepted start, so
    each morning was compared only against the morning before. From the
    post-repair 2,655, six consecutive 45% drops are each inside a 50% bar:

        2655 → 1460 → 803 → 441 → 242 → 133

    On the old code all six were accepted and each became the new bar — 95% of
    the universe gone with the guard silent. The baseline must ratchet UP only.
    """
    r = _FakeRedis()
    assert check_and_record_universe(r, 2655, 0.5) is None

    count = 2655
    accepted = [count]
    for _ in range(5):
        count = int(count * 0.55)
        if check_and_record_universe(r, count, 0.5) is None:
            accepted.append(count)
        else:
            break

    # Old code: all six accepted, ending at 133.
    assert accepted[-1] > 1000
    assert len(accepted) < 6


def test_an_accepted_smaller_universe_does_not_lower_the_baseline() -> None:
    r = _FakeRedis()
    check_and_record_universe(r, 2000, 0.5)
    assert check_and_record_universe(r, 1500, 0.5) is None
    assert r.store[UNIVERSE_KEY] == "2000"  # not 1500


def test_the_baseline_ttl_is_refreshed_even_when_not_raised() -> None:
    """The high-water mark must not silently expire on a run of smaller days —
    that would reset the guard to whatever the next start happens to see."""
    r = _FakeRedis()
    check_and_record_universe(r, 2000, 0.5)
    check_and_record_universe(r, 1500, 0.5)
    assert r.expire_calls == [(UNIVERSE_KEY, UNIVERSE_TTL_S)]


def test_growth_raises_the_baseline() -> None:
    r = _FakeRedis()
    check_and_record_universe(r, 1322, 0.5)
    check_and_record_universe(r, 2655, 0.5)
    assert r.store[UNIVERSE_KEY] == "2655"


def test_the_collapse_message_names_a_command_that_exists_here() -> None:
    """`redis-cli` is NOT installed on this machine, so the original remedy was
    an instruction the operator could not run — on the one path where the guard
    is deliberately wedged and the session is ticking away."""
    reason = assess_universe(700, previous=1500, min_fraction=0.5)
    assert reason is not None
    assert "redis-cli" not in reason
    assert "uv run python" in reason and UNIVERSE_KEY in reason


# ── U16: the per-connection ceiling ──────────────────────────────────────────


def test_a_universe_above_the_connection_cap_is_refused() -> None:
    """Kite carries at most 3,000 instruments per WebSocket and `live_worker`
    subscribes in ONE unchunked call; the SDK enforces nothing client-side
    (`kiteconnect/ticker.py:567` just sends the list), so the excess would be
    dropped server-side without telling us."""
    reason = assess_universe(3001, previous=2900, min_fraction=0.5, max_count=3000)
    assert reason is not None
    assert "EXCEEDS" in reason


def test_the_cap_is_inclusive() -> None:
    assert assess_universe(3000, previous=2900, min_fraction=0.5, max_count=3000) is None


def test_todays_and_the_post_repair_universe_both_fit() -> None:
    """Measured 2026-09-13: 1,178 today, 2,655 after the universe repair. The
    guard must not block the repair it exists alongside — but the headroom is
    only 345, which is why U16 exists at all."""
    for n in (1178, 2655):
        assert assess_universe(n, previous=None, min_fraction=0.5, max_count=3000) is None


def test_the_ceiling_is_off_when_max_count_is_zero() -> None:
    assert assess_universe(50_000, previous=None, min_fraction=0.5, max_count=0) is None


def test_the_ceiling_needs_no_baseline() -> None:
    """Like EMPTY and FLOOR, it must fire on a first run and survive a Redis
    outage — it is a fact about the transport, not about history."""
    r = _FakeRedis(boom=True)
    assert check_and_record_universe(r, 5000, 0.5, 0, 3000) is not None


def test_an_over_cap_universe_is_not_recorded_as_a_baseline() -> None:
    """Otherwise a refused start would raise the high-water mark to a size the
    connection cannot carry."""
    r = _FakeRedis()
    assert check_and_record_universe(r, 5000, 0.5, 0, 3000) is not None
    assert UNIVERSE_KEY not in r.store


# ── the worker refuses to start (the U1 acceptance criterion) ─────────────


class _RedisModule:
    @staticmethod
    def from_url(url: str, decode_responses: bool = False) -> _FakeRedis:
        return _FakeRedis()


def test_live_worker_preflight_exits_non_zero_on_an_empty_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ACCEPTANCE: `live_worker` must exit non-zero rather than run dark.

    `_bootstrap` now evaluates the check itself and hands back the refusal
    string; `_preflight` maps that to the exit code.
    """
    import app.broker.live_worker as lw

    def _fake_bootstrap(gap_fill: bool, universe_check: Any = None) -> Any:
        return _coro(universe_check(0))

    monkeypatch.setattr(lw, "_bootstrap", _fake_bootstrap)

    rc = lw._preflight(False, _RedisModule)
    assert rc == lw.EXIT_NO_UNIVERSE
    assert rc != 0


def test_live_worker_preflight_maps_a_missing_token_to_its_own_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two unrunnable conditions must stay DISTINGUISHABLE: the supervisor
    backs off differently for "log in" than for "the data layer is broken"."""
    import app.broker.live_worker as lw

    monkeypatch.setattr(lw, "_bootstrap", lambda gap_fill, universe_check=None: _coro(None))

    assert lw._preflight(False, _RedisModule) == lw.EXIT_NO_TOKEN
    assert lw.EXIT_NO_TOKEN != lw.EXIT_NO_UNIVERSE


def test_live_worker_preflight_returns_the_boot_tuple_when_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.broker.live_worker as lw

    token_map = {101: 1, 102: 2}
    monkeypatch.setattr(
        lw,
        "_bootstrap",
        lambda gap_fill, universe_check=None: _coro(("tok", token_map, object(), [])),
    )

    out = lw._preflight(False, _RedisModule)
    assert not isinstance(out, int)
    assert out[1] == token_map


async def test_bootstrap_refuses_before_running_the_gap_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REGRESSION (bug-hunter, 2026-09-13). The check used to run on
    `_bootstrap`'s RETURN value, so a COLLAPSE refusal first executed
    `startup_gap_fill` — a throttled Kite REST pass its own docstring budgets at
    ~35 minutes — and only then refused and exited. Under a restart loop that is
    an unbounded repeat of full gap-fill passes against a rate-limited broker
    API, every one of them discarded."""
    import app.broker.kite_client as kc
    import app.broker.live_worker as lw

    from tests.conftest import _SessionFactory

    called: list[str] = []

    class _Tok:
        access_token = "tok"

    async def _no_gap_fill(db: Any, token: str, token_map: dict[int, int]) -> None:
        called.append("gap_fill")

    monkeypatch.setattr(kc, "get_active_token", lambda db, user_id: _coro(_Tok()))
    monkeypatch.setattr("app.db.session.AsyncSessionFactory", _SessionFactory)
    monkeypatch.setattr(lw, "_build_token_stock_map", lambda db, tok: _coro({1: 1, 2: 2}))
    monkeypatch.setattr(lw, "startup_gap_fill", _no_gap_fill)
    monkeypatch.setattr(lw, "build_directory", lambda *a, **k: _coro(object()))

    out = await lw._bootstrap(True, universe_check=lambda n: "REFUSED: collapsed")

    assert out == "REFUSED: collapsed"
    assert called == []  # old code: ["gap_fill"] — a 35-minute pass, then refuse


async def _coro(value: Any) -> Any:
    """`_bootstrap` is awaited, so stubs must hand back an awaitable."""
    return value

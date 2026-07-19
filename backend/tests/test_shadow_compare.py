"""Shadow comparison — Rust vs frozen-Python decision double-check
(Phase 3, slice 3.7).

Verifies the harness the shadow week runs:
  - compare_pair on a REAL 1d window agrees (parity holds through the
    explicit impl= argument — proves both engines actually run and match);
  - an injected engine divergence is DETECTED and classified;
  - sweep_day compares the active universe, skips thin-history stocks,
    and reports clean on parity;
  - the as-of cutoff excludes future bars (a later day can re-compare
    faithfully);
  - non-1d timeframes are refused (Rust unpinned → a no-op comparison).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from app.services.shadow_compare import (
    ShadowDiff,
    _load_window,
    compare_pair,
    sweep_day,
)
from sqlalchemy import text

from tests.helpers import make_stock

DAY = date(2026, 7, 16)


def _frame(n: int = 120, start: float = 100.0) -> pd.DataFrame:
    """Deterministic 1d OHLCV (mild trend + pullbacks), 4dp so a DB
    round-trip is byte-exact. Scores None under both engines — exercises
    the no-signal parity branch."""
    times = [datetime(2026, 3, 1, tzinfo=UTC) + timedelta(days=i) for i in range(n)]
    closes, price = [], start
    for i in range(n):
        price *= 1 + (0.006 if i % 3 else -0.004)
        closes.append(round(price, 4))
    closes_a = np.array(closes)
    opens = np.concatenate([[start], closes_a[:-1]]).round(4)
    highs = (np.maximum(opens, closes_a) * 1.002).round(4)
    lows = (np.minimum(opens, closes_a) * 0.998).round(4)
    vols = np.linspace(10000, 30000, n).astype(int)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes_a,
         "volume": vols},
        index=pd.DatetimeIndex(times),
    )


def _firing_frame(n: int = 260, start: float = 300.0) -> pd.DataFrame:
    """Slow drift, short stall, then a big red marubozu on 4× volume in a
    strong-ADX regime → both engines emit (SELL, 66) EXACTLY. Pins live
    EMIT parity through tradecore, not just the no-signal branch."""
    times = [datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(n)]
    closes, price = [], start
    for i in range(n - 1):
        price *= 1 + (0.0012 if i < n - 4 else -0.003)
        closes.append(round(price, 4))
    closes.append(round(closes[-1] * 0.955, 4))
    closes_a = np.array(closes)
    opens = np.concatenate([[start], closes_a[:-1]]).round(4)
    highs = (np.maximum(opens, closes_a) * 1.0005).round(4)
    lows = (np.minimum(opens, closes_a) * 0.9995).round(4)
    highs[-1] = opens[-1]  # marubozu
    lows[-1] = closes_a[-1]
    vols = np.full(n, 12000)
    vols[-1] = 48000
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes_a,
         "volume": vols.astype(int)},
        index=pd.DatetimeIndex(times),
    )


async def _seed_1d(db, sid: int, frame: pd.DataFrame) -> None:
    for t, row in frame.iterrows():
        await db.execute(
            text(
                "INSERT INTO ohlcv_1d (time, stock_id, open, high, low, close,"
                " volume, is_complete) VALUES (:t, :sid, :o, :h, :l, :c, :v, true)"
            ),
            {"t": t, "sid": sid,
             "o": Decimal(f"{row['open']:.4f}"), "h": Decimal(f"{row['high']:.4f}"),
             "l": Decimal(f"{row['low']:.4f}"), "c": Decimal(f"{row['close']:.4f}"),
             "v": int(row["volume"])},
        )
    await db.commit()


# ── compare_pair ──────────────────────────────────────────────────────────────


class TestComparePair:
    def test_no_signal_window_matches_both_engines(self) -> None:
        """A real 1d window that scores None under both engines: no diff,
        and both emit flags False. Exercises tradecore + the toggle (not a
        silent skip) on the no-signal branch."""
        result = compare_pair(
            _frame(), stock_id=1, symbol="PARITY", timeframe="1d",
            as_of=DAY.isoformat(), min_confidence=70,
        )
        assert result.diff is None
        assert result.py_emitted is False and result.rust_emitted is False

    def test_emitted_signal_matches_both_engines_exactly(self) -> None:
        """THE parity claim on live data: a window that FIRES must fire
        identically under Rust and frozen-Python — same direction, same
        confidence integer — through the real tradecore path."""
        result = compare_pair(
            _firing_frame(), stock_id=2, symbol="FIRES", timeframe="1d",
            as_of=DAY.isoformat(), min_confidence=70,
        )
        assert result.py_emitted is True and result.rust_emitted is True
        assert result.diff is None  # exact agreement on a REAL emitted signal

    def test_injected_divergence_detected_and_classified(self, monkeypatch) -> None:
        """The comparison must FIRE when the engines disagree. Fake
        score_signal reads the impl= argument and returns different results
        per impl — proving compare_pair passes impl AND the diff logic."""
        from app.analysis.confluence import ConfluenceResult

        def fake_score(candles, timeframe="1d", min_confidence=70, **kw):
            if kw.get("impl") == "rust":
                return ConfluenceResult("SELL", 75, -0.75, [], [], [])
            return ConfluenceResult("BUY", 80, 0.80, [], [], [])

        monkeypatch.setattr(
            "app.services.signal_service.score_signal", fake_score
        )
        result = compare_pair(
            _frame(), stock_id=7, symbol="DIVERGE", timeframe="1d",
            as_of=DAY.isoformat(),
        )
        assert result.diff is not None
        assert result.diff.kind() == "direction"  # both emit, direction differs
        assert (result.diff.py_direction, result.diff.py_confidence) == ("BUY", 80)
        assert (result.diff.rust_direction, result.diff.rust_confidence) == ("SELL", 75)

    def test_decision_diff_classified_first(self, monkeypatch) -> None:
        def fake_score(candles, timeframe="1d", min_confidence=70, **kw):
            from app.analysis.confluence import ConfluenceResult
            if kw.get("impl") == "rust":
                return None  # rust: no signal
            return ConfluenceResult("BUY", 80, 0.80, [], [], [])

        monkeypatch.setattr("app.services.signal_service.score_signal", fake_score)
        result = compare_pair(
            _frame(), stock_id=7, symbol="DEC", timeframe="1d",
            as_of=DAY.isoformat(),
        )
        assert result.diff is not None
        assert result.diff.kind() == "decision"
        assert result.diff.py_decision is True and result.diff.rust_decision is False

    def test_compare_pair_does_not_mutate_global_impl(self, monkeypatch) -> None:
        """The comparison passes impl= explicitly — it must NEVER touch
        process-global settings.engine_impl (a peer thread, e.g. the
        provisional refresher, reads it concurrently)."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "engine_impl", "python")
        compare_pair(
            _firing_frame(), stock_id=3, symbol="NOGLOBAL", timeframe="1d",
            as_of=DAY.isoformat(),
        )
        assert settings.engine_impl == "python"  # untouched by the compare


# ── sweep_day ─────────────────────────────────────────────────────────────────


class TestSweepDay:
    @pytest.mark.asyncio
    async def test_sweeps_universe_skips_thin_history_and_is_clean(self, db) -> None:
        rich_a = await make_stock(db, symbol="SWEEPA")
        rich_b = await make_stock(db, symbol="SWEEPB")
        firing = await make_stock(db, symbol="SWEEPFIRE")
        thin = await make_stock(db, symbol="SWEEPTHIN")
        await _seed_1d(db, rich_a.id, _frame(120))
        await _seed_1d(db, rich_b.id, _frame(120, start=250.0))
        await _seed_1d(db, firing.id, _firing_frame())  # both engines emit
        await _seed_1d(db, thin.id, _frame(20))  # < 50 bars → skipped

        report = await sweep_day(db, DAY)

        assert report.compared == 3
        assert report.matched == 3
        assert report.skipped_no_data == 1
        assert report.clean is True
        # counters decompose "matched": one real emitted signal, agreed by both
        assert report.signals_emitted == 1
        assert report.both_emitted == 1
        assert report.errors == []
        assert report.summary()["diffs"] == 0

    @pytest.mark.asyncio
    async def test_report_stamps_excluded_flows(self, db) -> None:
        """The base comparison excludes §2.7 flows — the report must say so
        (a clean run with nonzero flows still can't claim committed parity)."""
        stock = await make_stock(db, symbol="SWEEPFLOW")
        await _seed_1d(db, stock.id, _frame(120))
        report = await sweep_day(db, DAY)
        assert set(report.flows_excluded) == {"fii_net_5d", "dii_net_5d"}
        assert report.summary()["flows_excluded"] == report.flows_excluded

    @pytest.mark.asyncio
    async def test_diff_surfaces_in_report(self, db, monkeypatch) -> None:
        stock = await make_stock(db, symbol="SWEEPDIFF")
        await _seed_1d(db, stock.id, _frame(120))

        def fake_score(candles, timeframe="1d", min_confidence=70, **kw):
            from app.analysis.confluence import ConfluenceResult
            if kw.get("impl") == "rust":
                return ConfluenceResult("SELL", 71, -0.71, [], [], [])
            return ConfluenceResult("BUY", 82, 0.82, [], [], [])

        monkeypatch.setattr("app.services.signal_service.score_signal", fake_score)
        report = await sweep_day(db, DAY)

        assert report.compared == 1
        assert report.clean is False
        assert len(report.diffs) == 1
        assert report.diffs[0].symbol == "SWEEPDIFF"
        assert report.diffs[0].kind() == "direction"

    @pytest.mark.asyncio
    async def test_as_of_cutoff_excludes_future_bars(self, db) -> None:
        stock = await make_stock(db, symbol="ASOF")
        frame = _frame(120)  # 2026-03-01 .. 2026-06-28
        await _seed_1d(db, stock.id, frame)
        cutoff = datetime(2026, 4, 1, 23, 59, 59, tzinfo=UTC)

        window = await _load_window(db, stock.id, "1d", cutoff)

        assert window.index.max() <= cutoff
        assert len(window) == 32  # Mar 1 .. Apr 1 inclusive

    @pytest.mark.asyncio
    async def test_non_pinned_timeframe_refused(self, db) -> None:
        with pytest.raises(ValueError, match="meaningful only for 1d"):
            await sweep_day(db, DAY, timeframe="5m")


# ── ShadowDiff serialization ──────────────────────────────────────────────────


class TestShadowDiff:
    def test_to_dict_shape(self) -> None:
        d = ShadowDiff(
            stock_id=1, symbol="X", timeframe="1d", as_of="2026-07-16",
            py_decision=True, rust_decision=True,
            py_direction="BUY", rust_direction="BUY",
            py_confidence=80, rust_confidence=79,
        )
        assert d.kind() == "confidence"
        out = d.to_dict()
        assert out["kind"] == "confidence"
        assert out["py"]["confidence"] == 80
        assert out["rust"]["confidence"] == 79

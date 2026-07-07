"""Unit tests for the walk-forward runner's pure core (slice 8b).

No database, no tradecore — the DB-bound golden replay lives in
tests/goldens/test_walkforward_goldens.py. These pin the calendar/gating/
digest semantics that the goldens stand on.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import ModuleType, SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from app.backtest.engine import BacktestResult, TradeRecord
from app.backtest.walkforward import (
    METRIC_FIELDS,
    MetricDelta,
    SymbolExclusion,
    WalkForwardError,
    WalkForwardReport,
    WalkForwardSpec,
    apply_setup_filter,
    bin_folds,
    build_golden,
    compare_against_existing,
    format_delta_table,
    map_tp_rule,
    metrics_dict,
    quarter_folds,
    quarter_key,
    run_walkforward,
    spec_from_golden,
    trades_digest,
    validate_profile,
)


def _tr(
    sym: str,
    day: str,
    qty: int = 10,
    pnl: float = 1.5,
    exited: bool = True,
) -> TradeRecord:
    entry = pd.Timestamp(day)
    return TradeRecord(
        stock=sym,
        direction="BUY",
        classification="",
        confidence_pct=75,
        entry_date=entry,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        qty=qty,
        exit_date=entry + pd.Timedelta(days=3) if exited else None,
        exit_price=100.0 * (1 + pnl / 100) if exited else None,
        pnl_pct=pnl if exited else None,
        hit_target=exited and pnl > 0,
        hit_sl=exited and pnl <= 0,
    )


class TestTpRuleMapping:
    def test_rr_maps_direct(self) -> None:
        assert map_tp_rule({"kind": "rr", "ratio": "2"}) == (("rr", "2"), False)

    def test_flat_pct_maps_direct(self) -> None:
        assert map_tp_rule({"kind": "flat_pct", "target_pct": "6"}) == (("flat_pct", "6"), False)

    def test_trailing_approximates_to_flat(self) -> None:
        rule, approx = map_tp_rule(
            {"kind": "flat_pct_trailing", "target_pct": "6", "book_fraction": "0.5"}
        )
        assert rule == ("flat_pct", "6") and approx is True

    def test_ema_trail_approximates_to_min_target(self) -> None:
        rule, approx = map_tp_rule(
            {"kind": "ema_trail", "ema_length": 20, "min_target_pct": "15"}
        )
        assert rule == ("flat_pct", "15") and approx is True

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(WalkForwardError, match="unknown risk_template kind"):
            map_tp_rule({"kind": "teleport"})


class TestQuarterFolds:
    def test_quarter_key_boundaries(self) -> None:
        assert quarter_key(date(2024, 10, 1)) == "2024Q4"
        assert quarter_key(date(2024, 12, 31)) == "2024Q4"
        assert quarter_key(date(2025, 1, 1)) == "2025Q1"
        assert quarter_key(date(2026, 6, 30)) == "2026Q2"

    def test_pinned_range_yields_seven_folds(self) -> None:
        assert quarter_folds(date(2024, 10, 1), date(2026, 6, 30)) == [
            "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2",
        ]

    def test_single_quarter_range(self) -> None:
        assert quarter_folds(date(2025, 2, 10), date(2025, 3, 1)) == ["2025Q1"]

    def test_inverted_range_rejected(self) -> None:
        with pytest.raises(WalkForwardError, match="before eval_start"):
            quarter_folds(date(2025, 3, 1), date(2025, 2, 1))

    def test_bin_folds_assigns_by_fill_date_and_keeps_empty_quarters(self) -> None:
        trades = [
            _tr("AAA", "2024-10-01"),  # eval_start boundary → first fold
            _tr("BBB", "2024-11-14"),
            _tr("CCC", "2025-06-30"),
        ]
        folds = dict(bin_folds(trades, date(2024, 10, 1), date(2025, 6, 30)))
        assert list(folds) == ["2024Q4", "2025Q1", "2025Q2"]
        assert folds["2024Q4"].total_trades == 2
        assert folds["2025Q1"].total_trades == 0  # empty quarter still present
        assert folds["2025Q2"].total_trades == 1


class TestTradesDigest:
    def test_order_invariant(self) -> None:
        trades = [_tr("BBB", "2024-10-02"), _tr("AAA", "2024-10-02"), _tr("AAA", "2024-10-01")]
        assert trades_digest(trades) == trades_digest(list(reversed(trades)))

    def test_sensitive_to_values(self) -> None:
        base = [_tr("AAA", "2024-10-01", qty=10)]
        assert trades_digest(base) != trades_digest([_tr("AAA", "2024-10-01", qty=11)])
        assert trades_digest(base) != trades_digest([_tr("AAA", "2024-10-01", pnl=1.6)])

    def test_open_trade_serializes_without_exit(self) -> None:
        open_trade = [_tr("AAA", "2024-10-01", exited=False)]
        assert trades_digest(open_trade) != trades_digest([_tr("AAA", "2024-10-01")])

    def test_intraday_timestamps_distinguish_same_session_trades(self) -> None:
        """8c: two trades of one stock in one session must not collide —
        the digest carries bar time off-midnight; 1d (midnight) lines are
        byte-identical to the pre-8c format."""
        a = _tr("AAA", "2024-10-01 09:30")
        b = _tr("AAA", "2024-10-01 14:15")
        assert trades_digest([a]) != trades_digest([b])
        assert trades_digest([a, b]) == trades_digest([b, a])  # order canon holds


class TestValidateProfile:
    def test_unpinned_timeframe_rejected(self) -> None:
        with pytest.raises(WalkForwardError, match="parity-pinned"):
            validate_profile("1h", [])

    def test_intraday_timeframes_accepted_since_8c(self) -> None:
        validate_profile("15m", [{"type": "orb_breakout", "params": {}}])
        validate_profile("5m", [{"type": "top_gainer_925", "params": {}}])

    def test_session_setups_still_rejected_on_1d(self) -> None:
        with pytest.raises(WalkForwardError, match="orb_breakout"):
            validate_profile("1d", [{"type": "orb_breakout", "params": {}}])

    def test_context_dependent_setups_rejected(self) -> None:
        with pytest.raises(WalkForwardError, match="relative_strength"):
            validate_profile("15m", [{"type": "relative_strength", "params": {}}])

    def test_supported_shape_passes(self) -> None:
        validate_profile("1d", [{"type": "dc1", "params": {}}, {"type": "dc2", "params": {}}])

    def test_bad_bounds_rejected_before_any_db_use(self) -> None:
        import asyncio

        stub = SimpleNamespace(timeframe="1d", setup_conditions=[], key="stub")
        spec = WalkForwardSpec(
            since=date(2025, 1, 1),
            eval_start=date(2024, 1, 1),
            eval_end=date(2026, 1, 1),
            capital=Decimal("500000"),
            risk_pct=Decimal("2"),
        )
        with pytest.raises(WalkForwardError, match="bounds"):
            asyncio.run(run_walkforward(None, stub, spec))  # type: ignore[arg-type]


def _base_df(n: int = 61) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.0] * n,
            "volume": [1000.0] * n,
        }
    )
    # Decision-window canary rows (fill at 60 ⇒ decision candle is 59):
    df.loc[57, "high"] = 200.0  # makes a one-short window fail pdh
    df.loc[58, ["high", "close"]] = [105.0, 104.0]
    df.loc[59, ["high", "close"]] = [110.0, 106.0]  # close 106 > pdh 105 ⇒ pass
    df.loc[60, ["high", "close"]] = [91.0, 90.0]  # fill candle would fail pdh
    return df


def _trade(fill_idx: int = 60, direction: str = "BUY", sr: float = 0.95) -> dict:
    return {
        "fill_idx": fill_idx,
        "direction": direction,
        "factors": {"SR_ZONE": (12.0, sr)},
    }


class TestSetupPostFilter:
    def test_empty_conditions_keep_everything(self) -> None:
        assert len(apply_setup_filter("X", _base_df(), [_trade()], [])) == 1

    def test_factor_score_gate_drops_below_threshold(self) -> None:
        cond = [{"type": "factor_score", "params": {"factor": "SR_ZONE", "min_score": 0.9}}]
        assert len(apply_setup_filter("X", _base_df(), [_trade(sr=0.95)], cond)) == 1
        assert len(apply_setup_filter("X", _base_df(), [_trade(sr=0.5)], cond)) == 0

    def test_factor_score_gate_is_direction_aware(self) -> None:
        cond = [{"type": "factor_score", "params": {"factor": "SR_ZONE", "min_score": 0.9}}]
        kept = apply_setup_filter(
            "X", _base_df(), [_trade(direction="SELL", sr=-0.95)], cond
        )
        assert len(kept) == 1
        assert not apply_setup_filter("X", _base_df(), [_trade(direction="SELL", sr=0.95)], cond)

    def test_window_ends_at_decision_candle_not_fill(self) -> None:
        """Off-by-one canary: pdh_breakout passes ONLY if the evaluation
        window ends exactly at the decision candle (fill_idx − 1). One
        candle later (fill included) or earlier both flip the verdict."""
        cond = [{"type": "pdh_breakout", "params": {}}]
        assert len(apply_setup_filter("X", _base_df(), [_trade()], cond)) == 1


class TestMetricTolerance:
    def test_within_five_percent_relative(self) -> None:
        assert MetricDelta("m", 100.0, 105.0).within_tolerance
        assert not MetricDelta("m", 100.0, 105.01).within_tolerance

    def test_absolute_floor_near_zero(self) -> None:
        assert MetricDelta("m", 0.0, 0.04).within_tolerance
        assert not MetricDelta("m", 0.0, 0.06).within_tolerance

    def test_delta_table_tags_approval_rows(self) -> None:
        table = format_delta_table(
            [MetricDelta("aggregate.total_pnl_pct", 10.0, 20.0),
             MetricDelta("aggregate.sharpe", 0.10, 0.11)]
        )
        assert "[§8 APPROVAL REQUIRED]" in table
        assert table.count("[§8 APPROVAL REQUIRED]") == 1

    def test_delta_table_no_moves_branch(self) -> None:
        assert format_delta_table([MetricDelta("m", 1.0, 1.0)]) == "  (no metric moves)"


# ── run_walkforward through a stubbed DB + stubbed tradecore ─────────────────
# (test-guardian finding: the FFI kwarg seam and the generation-side
# refusal/exclusion paths must not depend on the dev DB to be tested)

_IST = ZoneInfo("Asia/Kolkata")
_SPEC = WalkForwardSpec(
    since=date(2024, 1, 1), eval_start=date(2025, 3, 1), eval_end=date(2025, 6, 30)
)


def _candle_rows(symbol: str, n_pre: int, n_post: int) -> list[SimpleNamespace]:
    """n_pre daily rows strictly before eval_start, n_post from eval_start on."""
    rows = []
    for i in range(n_pre + n_post):
        d = _SPEC.eval_start + timedelta(days=i - n_pre)
        rows.append(
            SimpleNamespace(
                symbol=symbol,
                time=datetime.combine(d, time(15, 30), tzinfo=_IST),
                open=100.0, high=101.0, low=99.0, close=100.5, volume=1000,
            )
        )
    return rows


class _StubDb:
    """Duck-typed AsyncSession: every execute() returns the canned rows."""

    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    async def execute(self, *_args: object, **_kw: object) -> SimpleNamespace:
        rows = self._rows
        return SimpleNamespace(fetchall=lambda: rows)


def _profile_stub(**over: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "key": "stub",
        "version": 1,
        "name": "Stub",
        "style": "swing",
        "timeframe": "1d",
        "universe_spec": {"kind": "symbols", "value": ["AAA"]},
        "setup_conditions": [],
        "weight_multipliers": {},
        "min_confidence": 70,
        "risk_template": {"kind": "rr", "ratio": "2"},
        "validity_spec": None,
        "config_hash": "hash-stub",
    }
    base.update(over)
    return SimpleNamespace(**base)


def _stub_tradecore(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    stub = ModuleType("tradecore")

    def run_universe(stocks, timeframe, capital, risk_pct, min_confidence,
                     weight_multipliers=(), tp_rule=None,
                     session_last_bars=None):  # noqa: ANN001, ANN202
        captured.update(
            stocks=stocks, timeframe=timeframe, capital=capital, risk_pct=risk_pct,
            min_confidence=min_confidence, weight_multipliers=weight_multipliers,
            tp_rule=tp_rule, session_last_bars=session_last_bars,
        )
        return [(sym, []) for sym, *_ in stocks]

    stub.run_universe = run_universe  # type: ignore[attr-defined]
    stub.version = lambda: "stub-0.0"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tradecore", stub)


class TestFfiKwargSeam:
    def test_profile_knobs_reach_the_ffi_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Silent-mutation killer: hardcoding weight_multipliers=[] (or any
        other knob) at the run_universe call site must fail THIS test —
        every seeded profile carries {} so the goldens can't catch it."""
        captured: dict = {}
        _stub_tradecore(monkeypatch, captured)
        profile = _profile_stub(
            weight_multipliers={"trend": 0.8, "momentum": 1.2},
            risk_template={"kind": "flat_pct_trailing", "target_pct": "6"},
            min_confidence=75,
        )
        report = asyncio.run(
            run_walkforward(
                _StubDb(_candle_rows("AAA", n_pre=305, n_post=10)),  # type: ignore[arg-type]
                profile,  # type: ignore[arg-type]
                _SPEC,
                symbols=["AAA"],
            )
        )
        assert captured["weight_multipliers"] == [("momentum", 1.2), ("trend", 0.8)]
        assert captured["tp_rule"] == ("flat_pct", "6")
        assert captured["timeframe"] == "1d"
        assert captured["capital"] == "500000"
        assert captured["risk_pct"] == "2"
        assert captured["min_confidence"] == 75
        assert captured["session_last_bars"] is None  # 1d NEVER sends flags
        sym, o, h, lo, c, v = captured["stocks"][0]
        assert sym == "AAA" and len(o) == len(h) == len(lo) == len(c) == len(v) == 315
        assert report.tp_approximated is True
        assert report.row_counts == {"AAA": 315}

    def test_intraday_profile_sends_timeframe_and_session_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """8c seam: off-1d runs must reach the FFI with THEIR timeframe and
        aligned per-stock session flags (hardcoding '1d' or dropping flags
        must fail here)."""
        captured: dict = {}
        _stub_tradecore(monkeypatch, captured)
        profile = _profile_stub(
            timeframe="15m",
            setup_conditions=[{"type": "orb_breakout", "params": {"or_minutes": 15}}],
        )
        report = asyncio.run(
            run_walkforward(
                _StubDb(_candle_rows("AAA", n_pre=305, n_post=10)),  # type: ignore[arg-type]
                profile,  # type: ignore[arg-type]
                _SPEC,
                symbols=["AAA"],
            )
        )
        assert captured["timeframe"] == "15m"
        flags = captured["session_last_bars"]
        assert flags is not None and len(flags) == 1 and len(flags[0]) == 315
        assert flags[0][-1] is True  # final bar always session-last
        assert report.row_counts == {"AAA": 315}

    def test_exclusion_manifest_reasons_and_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AAA has 299 pre-eval bars (one short of canon), BBB has none,
        CCC qualifies — the manifest must record each exact reason."""
        captured: dict = {}
        _stub_tradecore(monkeypatch, captured)
        rows = _candle_rows("AAA", n_pre=299, n_post=5) + _candle_rows("CCC", 305, 5)
        report = asyncio.run(
            run_walkforward(
                _StubDb(rows),  # type: ignore[arg-type]
                _profile_stub(),  # type: ignore[arg-type]
                _SPEC,
                symbols=["AAA", "BBB", "CCC"],
            )
        )
        assert report.symbols == ["CCC"]
        assert report.exclusions == [
            SymbolExclusion("AAA", "<300 bars before eval_start", 299),
            SymbolExclusion("BBB", "no candles in range", 0),
        ]
        assert [s for s, *_ in captured["stocks"]] == ["CCC"]

    def test_all_symbols_excluded_is_a_hard_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_tradecore(monkeypatch, {})
        with pytest.raises(WalkForwardError, match="every symbol excluded"):
            asyncio.run(
                run_walkforward(
                    _StubDb(_candle_rows("AAA", n_pre=10, n_post=5)),  # type: ignore[arg-type]
                    _profile_stub(),  # type: ignore[arg-type]
                    _SPEC,
                    symbols=["AAA"],
                )
            )

    def test_empty_symbol_list_rejected(self) -> None:
        with pytest.raises(WalkForwardError, match="universe resolved empty"):
            asyncio.run(
                run_walkforward(None, _profile_stub(), _SPEC, symbols=[])  # type: ignore[arg-type]
            )

    def test_eval_start_equal_to_eval_end_is_legal(self) -> None:
        """Single-day replays must stay legal — prove the bounds check
        passes by failing LATER (on the empty symbol list)."""
        spec = WalkForwardSpec(
            since=date(2024, 1, 1), eval_start=date(2025, 3, 1), eval_end=date(2025, 3, 1)
        )
        with pytest.raises(WalkForwardError, match="universe resolved empty"):
            asyncio.run(
                run_walkforward(None, _profile_stub(), spec, symbols=[])  # type: ignore[arg-type]
            )


# ── Golden schema: one implementation, both directions (finding 4) ──────────


def _metrics(**over: float) -> dict[str, float]:
    base: dict[str, float] = {name: 0.0 for name in METRIC_FIELDS}
    base.update(total_trades=10, winning_trades=5, losing_trades=5, total_pnl_pct=12.0)
    base.update(over)
    return base


def _golden(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": "walkforward-golden-v1",
        "generated_at": "2026-07-06T10:00:00+00:00",
        "profile": {"key": "stub"},
        "config_hash": "hash-stub",
        "tradecore_version": "stub-0.0",
        "run": {
            "since": "2024-01-01", "eval_start": "2025-03-01", "eval_end": "2025-06-30",
            "capital": "500000", "risk_pct": "2", "tp_rule": ["rr", "2"],
            "tp_approximated": False,
        },
        "symbols": ["AAA"],
        "row_counts": {"AAA": 315},
        "exclusions": [],
        "pre_filter_trade_count": 12,
        "folds": [{"fold": "2025Q1", "metrics": _metrics()}],
        "aggregate": _metrics(),
        "trades_digest": "d0",
    }
    base.update(over)
    return base


class TestGoldenWriteGate:
    def test_identical_goldens_are_unchanged(self) -> None:
        assert compare_against_existing(_golden(), _golden()) == (
            False, False, "  (unchanged)"
        )

    def test_timestamp_only_diff_is_unchanged(self) -> None:
        changed, _, _ = compare_against_existing(
            _golden(), _golden(generated_at="2026-07-07T10:00:00+00:00")
        )
        assert changed is False

    def test_digest_only_change_needs_no_approval(self) -> None:
        changed, needs_approval, table = compare_against_existing(
            _golden(), _golden(trades_digest="d1")
        )
        assert changed is True and needs_approval is False
        assert "trades_digest" in table

    def test_metric_move_beyond_tolerance_needs_approval(self) -> None:
        changed, needs_approval, table = compare_against_existing(
            _golden(), _golden(aggregate=_metrics(total_pnl_pct=20.0), trades_digest="d1")
        )
        assert changed is True and needs_approval is True
        assert "[§8 APPROVAL REQUIRED]" in table

    def test_fold_set_change_is_reported(self) -> None:
        changed, _, table = compare_against_existing(_golden(), _golden(folds=[]))
        assert changed is True and "fold set changed" in table

    def test_config_hash_change_is_reported(self) -> None:
        _, _, table = compare_against_existing(_golden(), _golden(config_hash="h2"))
        assert "config_hash changed" in table


class TestGoldenSchemaRoundtrip:
    def test_build_golden_and_readers_agree(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The generator writes with build_golden; the harness reads with
        spec_from_golden + the folds/aggregate shape. One test pins both
        directions so a field rename can't slip past a skipping harness."""
        _stub_tradecore(monkeypatch, {})
        result = BacktestResult(total_trades=3, winning_trades=2, losing_trades=1)
        report = WalkForwardReport(
            profile_key="stub",
            config_hash="hash-stub",
            tp_rule=("rr", "2"),
            tp_approximated=False,
            symbols=["AAA"],
            row_counts={"AAA": 315},
            exclusions=[SymbolExclusion("BBB", "no candles in range", 0)],
            folds=[("2025Q1", result), ("2025Q2", BacktestResult())],
            aggregate=result,
            trades=[],
            pre_filter_trade_count=5,
            trades_digest="d0",
        )
        golden = build_golden(_profile_stub(), _SPEC, report)  # type: ignore[arg-type]

        assert spec_from_golden(golden) == _SPEC
        assert {f["fold"] for f in golden["folds"]} == {"2025Q1", "2025Q2"}
        assert golden["folds"][0]["metrics"] == metrics_dict(result)
        assert golden["aggregate"]["total_trades"] == 3
        assert golden["exclusions"] == [
            {"symbol": "BBB", "reason": "no candles in range", "bars_before_eval": 0}
        ]
        assert set(golden) == {
            "schema", "generated_at", "profile", "config_hash", "tradecore_version",
            "run", "symbols", "row_counts", "exclusions", "pre_filter_trade_count",
            "folds", "aggregate", "trades_digest",
        }
        # And the write gate sees a freshly-rebuilt golden as unchanged.
        golden2 = build_golden(_profile_stub(), _SPEC, report)  # type: ignore[arg-type]
        changed, needs_approval, _ = compare_against_existing(golden, golden2)
        assert (changed, needs_approval) == (False, False)

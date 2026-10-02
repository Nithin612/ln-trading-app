"""PR-1 study — the frozen clauses, each pinned on a constructed session (no DB, no market data).

The text is `docs/analysis/pr1-preregistration-v3.1-2026-10-02.md` (frozen at 6f61c9e); clause
numbers below are its §4. Every expected value is computed by hand from the construction, so a
test fails if the code drifts from the clause, not merely if it raises.
"""

from __future__ import annotations

import math
import statistics
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from scripts import pr1_study as st
from scripts.pr1_study import Bars, PairInput, SessionRecord

T, T1, TM1 = date(2024, 3, 5), date(2024, 3, 6), date(2024, 3, 4)


def _bars(p1515: float = 100.0, late: float = 0.0, o915: float | None = 100.0,
          p1510: float | None = 100.0, first_open: float | None = None) -> Bars:
    return Bars(75, o915, first_open if first_open is not None else o915, p1510, p1515,
                p1515 * (1 + late), p1515 * (1 + late))


def _pair(lates: list[float], next_open: list[float | None] | None = None,
          close: list[str] | None = None, drop_t1: set[int] | None = None,
          symbols: list[str] | None = None) -> PairInput:
    """n names; name i has late move lates[i] into P1530 = 100·(1 + late); its t+1 09:15 open
    is next_open[i] (default 100 ⇒ R_on = 1/(1+late) − 1)."""
    n = len(lates)
    bars_t = {i: _bars(late=lates[i]) for i in range(n)}
    nxt = next_open or [100.0] * n
    bars_t1 = {i: _bars(o915=nxt[i], p1510=nxt[i]) for i in range(n)
               if i not in (drop_t1 or set())}
    return PairInput(
        T, T1, tuple(range(n)), {i: (symbols[i] if symbols else f"N{i:02d}") for i in range(n)},
        {i: Decimal(close[i] if close else "500") for i in range(n)}, bars_t, bars_t1,
        {i: _bars() for i in range(n)},
    )


@pytest.fixture
def no_fee(monkeypatch: Any) -> list[tuple[str, date, date]]:
    calls: list[tuple[str, date, date]] = []

    def fake(price: Decimal, qty: int, product: str, entry_on: date, exit_on: date) -> float:
        calls.append((product, entry_on, exit_on))
        return 0.0

    monkeypatch.setattr(st, "_fee_frac", fake)
    return calls


class TestBookAndCuts:
    def test_book_is_the_five_most_negative_s_ties_by_ascending_symbol(self) -> None:
        """cl. 6: ties at the fifth place go to the ascending symbol."""
        lates = [-0.05, -0.04, -0.03, -0.02, -0.01, -0.01, 0.0, 0.01, 0.02, 0.03]
        p = _pair(lates, symbols=["A", "B", "C", "D", "Z", "E", "F", "G", "H", "I"])
        c, s = st._late_move(p)
        order = st._order(c, s, p.symbol)
        assert order[:5] == [0, 1, 2, 3, 5]  # "E" (5) beats "Z" (4) at the tie

    def test_cut_points_are_zero_based_half_open(self) -> None:
        """cl. 3: bottom quintile [0, ⌊n/5⌋), middle tercile [⌊n/3⌋, ⌊2n/3⌋)."""
        n = 17
        order = list(range(n))
        assert order[: n // 5] == [0, 1, 2]
        assert order[n // 3 : 2 * n // 3] == [5, 6, 7, 8, 9, 10]


class TestOutcomesAndCosts:
    def test_net_is_raw_minus_middle_tercile_mean_minus_fee_minus_two_half_spreads(
        self, no_fee: list[Any]
    ) -> None:
        """cl. 5, 7: the decision series is demeaned on the MIDDLE TERCILE (decision #1)."""
        lates = [-0.02 + 0.004 * i for i in range(10)]
        nxt: list[float | None] = [101.0 + 0.1 * i for i in range(10)]
        rec = st.evaluate_session(_pair(lates, next_open=nxt))
        r_on = {i: nxt[i] / (100 * (1 + lates[i])) - 1 for i in range(10)}  # type: ignore[operator]
        mid = statistics.fmean(r_on[i] for i in range(3, 6))  # ⌊10/3⌋ = 3 … ⌊20/3⌋ = 6
        want = statistics.fmean(r_on[i] - mid for i in range(5)) - 2 * 2.68 / 1e4
        assert rec.net["cnc"][2.68] == pytest.approx(want, abs=1e-12)
        whole = statistics.fmean(r_on.values())
        assert rec.net_whole["cnc"] == pytest.approx(
            statistics.fmean(r_on[i] - whole for i in range(5)) - 2 * 2.68 / 1e4, abs=1e-12)

    def test_fee_legs_are_dated_per_product(self, no_fee: list[Any]) -> None:
        """cl. 7: CNC enters on t and exits on t+1; MIS enters and exits on t+1."""
        st.evaluate_session(_pair([-0.01 * i for i in range(10)]))
        assert ("delivery", T, T1) in no_fee and ("intraday", T1, T1) in no_fee
        assert {c[0] for c in no_fee} == {"delivery", "intraday"}

    def test_real_fee_is_about_thirty_bps_for_delivery_at_twenty_thousand(self) -> None:
        """§5: ₹500 × 40 shares round trip = ₹59.78 = 29.89 bps (the text's own number)."""
        assert st._fee_frac(Decimal("500"), 40, "delivery", T, T1) * 1e4 == pytest.approx(
            29.89, abs=0.01)

    def test_qty_zero_is_skipped_and_not_replaced(self, no_fee: list[Any]) -> None:
        """cl. 6: a name priced above ₹20,000 cannot be bought; k_t drops, nobody steps in."""
        close = ["25000"] + ["500"] * 9
        rec = st.evaluate_session(_pair([-0.05 + 0.01 * i for i in range(10)], close=close))
        assert rec.counts["qty0"] == 2  # once per branch
        assert [k for _, _, k in rec.slot_net["cnc"]] == [4, 4, 4, 4]
        assert 0 not in {i for i, _, _ in rec.slot_net["cnc"]}

    def test_suspended_book_name_carries_zero_for_cnc_and_is_never_entered_for_mis(
        self, no_fee: list[Any]
    ) -> None:
        """test_suspended_slot_dropped (cl. 3, 7): dropping it would select on t+1. CNC carries
        R_on = 0 minus the base and pays the round trip; MIS never enters."""
        rec = st.evaluate_session(_pair([-0.05 + 0.01 * i for i in range(10)], drop_t1={0}))
        assert rec.counts["cnc_carried_suspended"] == 1
        assert rec.counts["mis_not_entered"] == 1
        assert 0 in {i for i, _, _ in rec.slot_net["cnc"]}
        assert 0 not in {i for i, _, _ in rec.slot_net["mis"]}

    def test_missing_0915_bar_carries_the_first_bar_open(self, no_fee: list[Any]) -> None:
        p = _pair([-0.05 + 0.01 * i for i in range(10)])
        p.bars_t1[0] = Bars(70, None, 99.0, 99.5, 99.5, 99.5, 99.5)
        rec = st.evaluate_session(p)
        assert rec.counts["cnc_carried_open"] == 1 and rec.counts["mis_carried_open"] == 1
        raw = 99.0 / (100 * 0.95) - 1
        net0 = next(v for i, v, _ in rec.slot_net["cnc"] if i == 0)
        r_on = {i: 100 / (100 * (1 - 0.05 + 0.01 * i)) - 1 for i in range(1, 10)}
        mid = statistics.fmean(r_on[i] for i in range(3, 6))
        assert net0 == pytest.approx(raw - mid - 2 * 2.68 / 1e4, abs=1e-12)


def _rec(t: date, net: float, ic_q: float = -0.1, slots: list[tuple[int, float, int]] | None = None,
         branch_net: dict[str, float] | None = None) -> SessionRecord:
    nets = branch_net or {"cnc": net, "mis": net - 1.0}
    return SessionRecord(
        t, 200, {b: {2.68: v, 1.76: v + 0.0002} for b, v in nets.items()},
        dict(nets), dict(nets), {"cnc": ic_q, "mis": ic_q}, {"cnc": ic_q, "mis": ic_q},
        {"cnc": None, "mis": None},
        {"cnc": slots if slots is not None else [(int(t.toordinal()) % 200, net, 1)], "mis": []},
    )


def _dates(n: int, start: date = date(2023, 7, 3)) -> list[date]:
    return [date.fromordinal(start.toordinal() + k) for k in range(n)]


def _strong(n: int = 748, mean: float = 0.002, sd: float = 0.004) -> list[float]:
    """A deterministic series with a known mean and spread (alternating ±sd)."""
    return [mean + (sd if k % 2 else -sd) * (1 + 0.1 * math.sin(k)) for k in range(n)]


class TestDecision:
    def test_a_strong_broad_edge_passes(self) -> None:
        recs = [_rec(d, v) for d, v in zip(_dates(748), _strong(), strict=True)]
        d = st.decide(recs)
        assert d.branch == "cnc" and d.verdict == "PASS", d.reasons

    def test_k2_kills_a_pass_when_the_bottom_quintile_ic_is_not_negative(self) -> None:
        recs = [_rec(d, v, ic_q=0.01) for d, v in zip(_dates(748), _strong(), strict=True)]
        d = st.decide(recs)
        assert d.verdict == "KILL" and any("K2" in r for r in d.reasons)

    def test_cost_kill_on_a_clearly_negative_series(self) -> None:
        recs = [_rec(d, v) for d, v in zip(_dates(748), _strong(mean=-0.003), strict=True)]
        d = st.decide(recs)
        assert d.verdict == "KILL" and any("cost KILL" in r for r in d.reasons)

    def test_a_weak_series_is_null_not_kill(self) -> None:
        recs = [_rec(d, v) for d, v in zip(_dates(748), _strong(mean=0.0002), strict=True)]
        d = st.decide(recs)
        assert d.verdict == "NULL" and not d.reasons

    def test_k4_kills_when_the_dated_halves_disagree(self) -> None:
        days = _dates(748)
        vals = [0.006 + (0.002 if k % 2 else -0.002) if d < st.K4_SPLIT
                else -0.0004 + (0.002 if k % 2 else -0.002) for k, d in enumerate(days)]
        d = st.decide([_rec(day, v) for day, v in zip(days, vals, strict=True)])
        assert d.stats["would_pass"] and d.stats["k4"] and d.verdict == "KILL"

    def test_k6_kills_when_three_names_carry_the_book(self) -> None:
        recs = []
        for k, (day, v) in enumerate(zip(_dates(748), _strong(), strict=True)):
            winner = k % 3  # names 0–2 carry everything, the rest lose a little
            recs.append(_rec(day, v, slots=[(winner, 5 * v, 5)] + [(10 + k % 50, -0.0001, 5)] * 4))
        d = st.decide(recs)
        assert d.stats["would_pass"] and d.stats["k6"] and d.verdict == "KILL"

    def test_robustness_kills_are_not_checked_when_there_is_no_pass(self) -> None:
        """cl. 12: they turn a PASS into a KILL, never a NULL into a KILL."""
        recs = [_rec(d, v) for d, v in zip(_dates(748), _strong(mean=0.0002), strict=True)]
        d = st.decide(recs)
        assert d.stats["k3"] is False and d.stats["k4"] is False and d.stats["k6"] is False

    def test_the_branch_with_the_higher_net_t_decides(self) -> None:
        # same spread, lower mean: scaling by a constant would leave t unchanged (a tie)
        recs = [_rec(d, 0.0, branch_net={"cnc": v - 0.0015, "mis": v})
                for d, v in zip(_dates(748), _strong(), strict=True)]
        assert st.decide(recs).branch == "mis"


class TestEndToEndSynthetic:
    def test_no_edge_does_not_pass_and_a_planted_reversal_does(self) -> None:
        null = [st.evaluate_session(p) for p in st.synthetic_pairs(3, n_pairs=300)]
        planted = [st.evaluate_session(p)
                   for p in st.synthetic_pairs(3, n_pairs=748, edge_bps=80.0)]
        assert st.decide(null).verdict != "PASS"
        d = st.decide(planted)
        assert d.verdict == "PASS" and d.branch == "cnc"
        assert st.mechanism_label(planted, "cnc")["label"] in ("close-specific",
                                                               "generic reversal")


class TestGuards:
    def test_the_loader_refuses_a_window_touching_a_holdout(self) -> None:
        with pytest.raises(SystemExit, match="sealed block holdout-1"):
            st._assert_outside_holdouts(date(2023, 6, 1), date(2024, 1, 1))
        st._assert_outside_holdouts(st.WINDOW_LO, st.WINDOW_HI)  # the test block is allowed

    def test_run_once_is_refused_while_descriptives_are_pending(self) -> None:
        assert any("descriptives" in p for p in st.run_once_preflight())

    def test_run_once_is_refused_when_a_receipt_exists(
        self, monkeypatch: Any, tmp_path: Any
    ) -> None:
        receipt = tmp_path / "receipt.json"
        receipt.write_text("{}")
        monkeypatch.setattr(st, "RECEIPT", receipt)
        assert any("runs ONCE" in p for p in st.run_once_preflight())

    def test_the_frozen_text_is_the_frozen_text(self) -> None:
        assert st._sha(st.FROZEN_TEXT) == st.FROZEN_SHA256

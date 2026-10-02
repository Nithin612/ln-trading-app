"""PR-1 study — the frozen clauses, each pinned on a constructed session (no DB, no market data).

The text is `docs/analysis/pr1-preregistration-v3.1-2026-10-02.md` (frozen at 6f61c9e); clause
numbers below are its §4. Every expected value is computed by hand from the construction, so a
test fails if the code drifts from the clause, not merely if it raises.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import replace
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
                p1515 * (1 + late), p1515 * (1 + late), p1505_exact=p1510)


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

    def fake(price: Decimal, qty: int, product: str, entry_on: date, exit_on: date,
             side: str = "LONG") -> float:
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

    def test_the_middle_tercile_base_uses_ranks_n3_to_2n3_through_evaluate_session(
        self, no_fee: list[Any]
    ) -> None:
        """cl. 3, 5: with n = 17 the middle tercile is ranks [5, 11); ranks 0–4 are the book.
        Moving a NON-book name outside [5, 11) — ranks 11, 16 — must leave the book's net
        unchanged; moving rank 5 or 10 must move it."""
        lates = [-0.05 + 0.005 * i for i in range(17)]
        nxt: list[float | None] = [100.0] * 17
        base = st.evaluate_session(_pair(lates, next_open=nxt)).net["cnc"][2.68]
        for rank, moves in ((5, True), (10, True), (11, False), (16, False)):
            bumped = list(nxt)
            bumped[rank] = 103.0
            got = st.evaluate_session(_pair(lates, next_open=bumped)).net["cnc"][2.68]
            assert (got != pytest.approx(base, abs=1e-12)) is moves, rank


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
        assert rec.counts["qty0"] == 1  # once per SLOT, not once per branch
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
        p.bars_t1[0] = Bars(70, None, 99.0, 99.5, 99.5, 99.5, 99.5, p1505_exact=99.5)
        rec = st.evaluate_session(p)
        assert rec.counts["cnc_carried_open"] == 1 and rec.counts["mis_carried_open"] == 1
        raw = 99.0 / (100 * 0.95) - 1
        net0 = next(v for i, v, _ in rec.slot_net["cnc"] if i == 0)
        r_on = {i: 100 / (100 * (1 - 0.05 + 0.01 * i)) - 1 for i in range(1, 10)}
        mid = statistics.fmean(r_on[i] for i in range(3, 6))
        assert net0 == pytest.approx(raw - mid - 2 * 2.68 / 1e4, abs=1e-12)


class TestNonBookOutcomes:
    def test_a_non_book_name_without_its_own_1505_bar_is_out_of_the_mis_base(
        self, no_fee: list[Any]
    ) -> None:
        """test_non_book_name_carried_into_the_base (quant-verifier HIGH, 2026-10-02): the carry
        rules are for BOOK slots (cl. 3); a middle-tercile name with no 15:05 bar must not enter
        the base through a carried 'latest earlier bar'."""
        lates = [-0.05 + 0.005 * i for i in range(20)]
        p = _pair(lates)
        before = st.evaluate_session(p).net["mis"][2.68]
        # n = 20: the book is ranks 0–4, the middle tercile [6, 13); name 8 is in the middle
        # tercile and NOT in the book. Give it only an earlier bar, far away.
        p.bars_t1[8] = Bars(60, 100.0, 100.0, 140.0, 140.0, 140.0, 140.0, p1505_exact=None)
        after = st.evaluate_session(p).net["mis"][2.68]
        p.bars_t1[8] = Bars(60, 100.0, 100.0, 140.0, 140.0, 140.0, 140.0, p1505_exact=140.0)
        with_bar = st.evaluate_session(p).net["mis"][2.68]
        assert after != pytest.approx(with_bar, abs=1e-9)  # canary: a real bar WOULD move it
        # without its own 15:05 bar, name 8 has no defined R_day and leaves the base; every other
        # middle name has R_day = 0, so the base is 0 — exactly as before name 8 changed
        assert after == pytest.approx(before, abs=1e-12)

    def test_a_book_slot_carrying_the_latest_earlier_bar_is_counted(
        self, no_fee: list[Any]
    ) -> None:
        p = _pair([-0.05 + 0.01 * i for i in range(10)])
        p.bars_t1[0] = Bars(60, 100.0, 100.0, 99.0, 99.0, 99.0, 99.0, p1505_exact=None)
        rec = st.evaluate_session(p)
        assert rec.counts["mis_carried_1505"] == 1
        assert 0 in {i for i, _, _ in rec.slot_net["mis"]}


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

    def test_k3_kills_when_fifteen_sessions_carry_everything(self) -> None:
        """cl. 12 K3: removing the 15 best sessions leaves the mean ≤ 0."""
        days = _dates(748)
        # t passes only near √15 ≈ 3.87 (the outliers' own variance caps it): 15 sessions at
        # +100 bps, every other session −0.05 bps ⇒ NW t ≈ 4.24, DSR ≈ 0.9998, yet the mean
        # without the 15 is negative
        vals = [0.01 if k % 50 == 0 else -5e-6 + (1e-7 if k % 2 else -1e-7)
                for k in range(748)]
        assert sum(1 for v in vals if v >= 0.01) == 15
        d = st.decide([_rec(day, v) for day, v in zip(days, vals, strict=True)])
        assert d.stats["would_pass"] and d.stats["k3"] and d.verdict == "KILL"

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


class TestMechanismLabel:
    @staticmethod
    def _labelled(slopes: list[tuple[float, float, float]]) -> list[SessionRecord]:
        recs = [_rec(d, 0.001) for d in _dates(len(slopes))]
        for r, sl in zip(recs, slopes, strict=True):
            r.label["cnc"] = sl
        return recs

    def test_close_specific_needs_beta_s_and_beta_s_minus_pre_both_negative(self) -> None:
        sl = [(-0.5 + 0.01 * math.sin(k), -0.1 + 0.01 * math.cos(k), 0.0) for k in range(400)]
        assert st.mechanism_label(self._labelled(sl), "cnc")["label"] == "close-specific"

    def test_generic_reversal_when_pre_is_as_negative_as_s(self) -> None:
        sl = [(-0.5 + 0.01 * math.sin(k), -0.5 + 0.01 * math.cos(k), 0.0) for k in range(400)]
        assert st.mechanism_label(self._labelled(sl), "cnc")["label"] == "generic reversal"

    def test_none_when_beta_s_is_not_negative(self) -> None:
        sl = [(0.01 * math.sin(k), -0.5, 0.0) for k in range(400)]
        assert st.mechanism_label(self._labelled(sl), "cnc")["label"] == "none"

    def test_the_first_session_has_no_label_row(self, no_fee: list[Any]) -> None:
        """cl. 13: the first session's t−1 lies in a sealed block, so it is skipped."""
        p = replace(_pair([-0.05 + 0.01 * i for i in range(10)]), bars_tm1=None)
        assert st.evaluate_session(p).label == {"cnc": None, "mis": None}


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

    def test_run_once_is_refused_until_the_freeze_is_on_a_remote(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(st, "_git", lambda *a: "")
        assert any("not on any remote" in p for p in st.run_once_preflight())

    def test_run_once_is_refused_when_a_receipt_exists(
        self, monkeypatch: Any, tmp_path: Any
    ) -> None:
        receipt = tmp_path / "receipt.json"
        receipt.write_text("{}")
        monkeypatch.setattr(st, "RECEIPT", receipt)
        assert any("runs ONCE" in p for p in st.run_once_preflight())

    def test_run_once_is_refused_on_a_dirty_tree(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(st, "_git", lambda *a: " M backend/app/trading/fees.py"
                            if a[0] == "status" else "origin/x")
        assert any("uncommitted" in p for p in st.run_once_preflight())

    def test_run_once_is_refused_when_the_frozen_text_changed(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(st, "_sha", lambda p: "0" * 64)
        assert any("sha256" in p for p in st.run_once_preflight())

    def test_the_receipt_hashes_every_guarded_file(
        self, monkeypatch: Any, tmp_path: Any
    ) -> None:
        monkeypatch.setattr(st, "RECEIPT", tmp_path / "r.json")
        st._write_receipt()
        import json

        got = json.loads((tmp_path / "r.json").read_text())["guarded_sha256"]
        assert len(got) == len(st.GUARDED) and any("fees.py" in k for k in got)

    def test_the_frozen_text_is_the_frozen_text(self) -> None:
        assert st._sha(st.FROZEN_TEXT) == st.FROZEN_SHA256


class TestDescriptives:
    def test_expiry_calendar_follows_the_texts_weekday_switch_and_holiday_rule(self) -> None:
        """I8 / §2 (NSE/FAOP/68747): Thursday before 2025-09-01, Tuesday after; the last one of
        a month is 'monthly'; a holiday moves an expiry to the previous session."""
        start = date(2025, 8, 1)
        cal = [date.fromordinal(start.toordinal() + k) for k in range(61)]
        cal = [d for d in cal if d.weekday() < 5 and d != date(2025, 8, 14)]  # a Thu holiday
        exp = st.expiry_types(cal)
        assert exp[date(2025, 8, 7)] == "weekly"
        assert exp[date(2025, 8, 13)] == "weekly"  # the 14th is a holiday → Wednesday
        assert date(2025, 8, 14) not in exp
        assert exp[date(2025, 8, 28)] == "monthly"  # the last Thursday of August
        assert exp[date(2025, 9, 2)] == "weekly"  # Tuesday regime
        assert exp[date(2025, 9, 30)] == "monthly"  # the last Tuesday of September
        assert date(2025, 9, 4) not in exp  # Thursdays are no longer expiries

    def test_a_short_slot_earns_the_negative_of_the_demeaned_return(
        self, no_fee: list[Any]
    ) -> None:
        p = _pair([0.0] * 10)
        long_ = st._variant_net(p, [0], 0.001, {0: 0.004}, "intraday")
        short = st._variant_net(p, [0], 0.001, {0: 0.004}, "intraday", side="SHORT")
        assert long_[0] + 2 * 2.68 / 1e4 == pytest.approx(0.003, abs=1e-12)
        assert short[0] < long_[0]

    def test_g_uses_only_slots_whose_bases_agree_exactly(self) -> None:
        """I7: G mixes the tables, so a name whose bases differ on t is left out."""
        p = _pair([-0.05 + 0.01 * i for i in range(10)], close=["94"] * 10)
        e = st.session_extras(replace(p, basis_exact=frozenset({0, 1})))
        assert len(e.g_bps) == 2
        assert e.g_bps[0] == pytest.approx((95.0 / 94.0 - 1) * 1e4, abs=1e-6)

    def test_executable_variant_reads_the_daily_open_not_the_bar(
        self, no_fee: list[Any]
    ) -> None:
        p = _pair([-0.05 + 0.01 * i for i in range(10)])
        e_same = st.session_extras(replace(p, open1_daily={i: Decimal("500") for i in range(10)}))
        e_up = st.session_extras(replace(
            p, open1_daily={i: Decimal("510" if i == 0 else "500") for i in range(10)}))
        assert e_up.exec_net is not None and e_same.exec_net is not None
        assert e_up.exec_net > e_same.exec_net  # only the daily open moved

    def test_describe_runs_every_descriptive_on_a_synthetic_window(
        self, capsys: Any
    ) -> None:
        pairs = st.synthetic_pairs(5, n_pairs=120, n_names=60, edge_bps=40.0)
        recs = [st.evaluate_session(p) for p in pairs]
        ctx = st.synthetic_context(5, pairs)
        st.describe(pairs, recs, st.decide(recs), ctx.vix, ctx.calendar)
        out = capsys.readouterr().out
        for needle in ("weekday × expiry", "VIX tercile", "late-volume tercile", "long-short",
                       "executable R_on", "G = P1530", "P1525", "concentration",
                       "balanced subsample", "transient", "equal-weight cohort", "unavailable"):
            assert needle in out, needle

    def test_no_descriptive_is_pending_and_unavailable_ones_carry_a_reason(self) -> None:
        assert st.DESCRIPTIVES_PENDING == ()
        assert all(len(u) > 40 for u in st.DESCRIPTIVES_UNAVAILABLE)

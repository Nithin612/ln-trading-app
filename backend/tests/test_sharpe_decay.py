"""H7 — shadow-gate decay alarm.

The regime gate ran seven NOT-READY report days before it was reverted; the signal was on
disk every day but nothing alarmed. H7 is a second reader of those readiness banners that
fires on a REGRESSION (a gate that was READY / is ACTIVE decaying to NOT READY), NOT on a gate
that is merely still accruing — else it would alarm on every shadow gate, forever. These tests
pin that distinction, the banner parsing, the file scan, and the notification/render.
"""

from datetime import date, timedelta

from app.services import sharpe_decay as sd
from app.services.notifier import Level


def _hist(*flags: bool, end: date = date(2026, 9, 8)) -> list[sd.DayReadiness]:
    """Build an oldest-first history ending at `end`, one entry per prior day."""
    n = len(flags)
    return [sd.DayReadiness(end - timedelta(days=n - 1 - i), f) for i, f in enumerate(flags)]


class TestExtractReadiness:
    def test_ready_banner(self) -> None:
        assert sd.extract_readiness("**Flip readiness:** ✅ READY — enough trades") is True

    def test_not_ready_banner(self) -> None:
        assert sd.extract_readiness("[forward evidence] ⏳ NOT READY — keep accruing") is False

    def test_not_ready_wins_over_the_word_ready_in_prose(self) -> None:
        text = "The setup looks ready.\n**Flip readiness:** ⏳ NOT READY — 3/20 resolved\n"
        assert sd.extract_readiness(text) is False

    def test_no_banner_is_none(self) -> None:
        assert sd.extract_readiness("# Some report\n\njust a table\n") is None


class TestAnalyze:
    def test_perpetual_not_ready_is_accrual_not_decay(self) -> None:
        """The load-bearing case: every shadow gate is NOT READY now; that is not a decay."""
        d = sd.analyze("g", _hist(False, False, False, False, False, False), is_active=False)
        assert d.not_ready_streak == 6 and d.was_ready is False and d.decaying is False

    def test_was_ready_then_a_long_not_ready_run_is_a_decay(self) -> None:
        d = sd.analyze("g", _hist(True, True, False, False, False, False, False), is_active=False)
        assert d.was_ready is True and d.not_ready_streak == 5 and d.decaying is True

    def test_a_short_not_ready_run_after_ready_is_not_yet_a_decay(self) -> None:
        d = sd.analyze("g", _hist(True, True, False, False, False), is_active=False)
        assert d.not_ready_streak == 3 and d.decaying is False

    def test_an_active_gate_going_not_ready_is_a_decay_without_prior_ready(self) -> None:
        """A gate promoted before the window shows no in-window READY, so adoption comes from
        the register — the regime-gate-after-promotion shape."""
        d = sd.analyze("g", _hist(False, False, False, False, False), is_active=True)
        assert d.was_ready is False and d.decaying is True

    def test_a_recovered_gate_breaks_the_streak(self) -> None:
        d = sd.analyze("g", _hist(True, False, False, False, False, True), is_active=True)
        assert d.latest_ready is True and d.not_ready_streak == 0 and d.decaying is False

    def test_empty_history(self) -> None:
        d = sd.analyze("g", [], is_active=True)
        assert d.latest_ready is None and d.decaying is False and d.days_observed == 0


class TestScanFiles:
    def _write(self, d: date, stem: str, day: date, ready: bool, tmp) -> None:
        verdict = "✅ READY" if ready else "⏳ NOT READY"
        (tmp / f"{stem}-{day.isoformat()}.md").write_text(f"**Flip readiness:** {verdict} — x\n")

    def test_read_history_picks_up_dated_files_and_skips_gaps(self, tmp_path) -> None:
        today = date(2026, 9, 8)
        # two READY days, a gap, then a NOT-READY day
        self._write(today, "regime-gate-shadow", today - timedelta(days=5), True, tmp_path)
        self._write(today, "regime-gate-shadow", today - timedelta(days=4), True, tmp_path)
        self._write(today, "regime-gate-shadow", today, False, tmp_path)
        hist = sd.read_history(tmp_path, "regime-gate-shadow", today=today)
        assert [h.ready for h in hist] == [True, True, False]

    def test_scan_flags_a_decayed_gate_from_files(self, tmp_path) -> None:
        today = date(2026, 9, 8)
        # regime gate: 2 READY then 5 NOT-READY → decay via was_ready
        for i, r in enumerate([True, True, False, False, False, False, False]):
            self._write(today, "regime-gate-shadow", today - timedelta(days=6 - i), r, tmp_path)
        decays = {d.gate: d for d in sd.scan(tmp_path, today=today)}
        assert decays["regime gate (ADX)"].decaying is True
        # a gate with no files is present but not decaying
        assert decays["liquidity"].latest_ready is None and decays["liquidity"].decaying is False


class TestNotificationAndRender:
    def test_no_decay_no_notification(self) -> None:
        decays = [sd.analyze("g", _hist(False, False), is_active=False)]
        assert sd.to_notification(decays) is None
        assert sd.render_lines(decays) == []

    def test_decay_pushes_a_warning_naming_the_gate(self) -> None:
        h = _hist(True, False, False, False, False, False)
        decays = [sd.analyze("regime", h, is_active=False)]
        n = sd.to_notification(decays)
        assert n is not None and n.level is Level.WARNING and n.event == "gate_decay"
        assert "regime" in "\n".join(n.lines)

    def test_markdown_always_has_a_status_table(self) -> None:
        decays = [sd.analyze("g", _hist(False), is_active=False)]
        md = sd.render_markdown(decays, date(2026, 9, 8))
        assert "| gate | state |" in md and "H7" in md

    def test_markdown_shows_the_loud_block_when_decaying(self) -> None:
        h = _hist(True, False, False, False, False, False)
        decays = [sd.analyze("regime", h, is_active=False)]
        md = sd.render_markdown(decays, date(2026, 9, 8))
        assert "DECAY ALARM" in md and "DECAYING" in md

"""Session notifier with a noise policy — A11.

We have standing manual daily human checks that exist only because nothing pushes: CAS
capture (the worker must be up 15:15–15:33 IST and **a missed window cannot be
back-filled**) and provisional health (no scheduler at all). Both are caught today by
someone remembering.

The policy is the valuable part and the part that decides what a quiet channel MEANS, so it
is pure and tested separately from delivery. The load-bearing rules: routine success is
silent, repeats are throttled *with the suppressed count reported*, and **any exception
always notifies, bypassing everything** — including the throttle.
"""

import logging

import pytest
from app.services import notifier as nf
from app.services.notifier import Level, Notification


@pytest.fixture(autouse=True)
def _clean_throttle():
    nf.reset_throttle()
    yield
    nf.reset_throttle()


def _n(level: Level = Level.WARNING, *, event: str = "e", exc: str | None = None):
    return Notification(event=event, level=level, title="t", exception=exc)


class TestPolicy:
    def test_routine_success_is_silent(self) -> None:
        """The CAS task returns `skipped: outside CAS window` ~1,400 times a day. A
        notifier that said so is a notifier nobody reads."""
        assert nf.should_notify(_n(Level.INFO)) is False

    def test_warning_and_error_speak(self) -> None:
        assert nf.should_notify(_n(Level.WARNING)) is True
        assert nf.should_notify(_n(Level.ERROR)) is True

    def test_an_exception_notifies_even_at_info(self) -> None:
        """⭐ The rule that exists so no future noise rule can silence a crash."""
        assert nf.should_notify(_n(Level.INFO, exc="ValueError: boom")) is True


class TestThrottle:
    def test_repeats_inside_the_window_are_suppressed(self) -> None:
        clock = [1000.0]
        t = nf._Throttle(window_s=900.0, clock=lambda: clock[0])
        assert t.admit(_n())[0] is True
        clock[0] += 60
        assert t.admit(_n())[0] is False

    def test_the_suppressed_count_rides_the_next_message(self) -> None:
        """⭐ Suppression is reported, never silent — a growing count IS the signal that
        something is getting worse while being throttled."""
        clock = [1000.0]
        t = nf._Throttle(window_s=900.0, clock=lambda: clock[0])
        t.admit(_n())
        for _ in range(37):
            clock[0] += 1
            t.admit(_n())
        clock[0] += 1000
        send, suppressed = t.admit(_n())
        assert send is True
        assert suppressed == 37

    def test_a_different_event_is_not_throttled_by_its_neighbour(self) -> None:
        t = nf._Throttle(window_s=900.0, clock=lambda: 1000.0)
        assert t.admit(_n(event="cas"))[0] is True
        assert t.admit(_n(event="provisional"))[0] is True

    def test_an_exception_bypasses_the_throttle(self) -> None:
        """A crash every minute is a crash every minute. The throttle is written for
        routine traffic and must not apply to the one thing that always speaks."""
        clock = [1000.0]
        t = nf._Throttle(window_s=900.0, clock=lambda: clock[0])
        assert t.admit(_n(exc="E: 1"))[0] is True
        clock[0] += 1
        assert t.admit(_n(exc="E: 2"))[0] is True

    def test_the_count_is_reported_on_the_message_that_sends(self, caplog) -> None:
        nf.reset_throttle()
        with caplog.at_level(logging.WARNING, logger="app.services.notifier"):
            assert nf.notify(_n()) is True
            assert nf.notify(_n()) is False  # throttled
            # An exception breaks through AND carries what was suppressed.
            assert nf.notify(_n(exc="ValueError: boom")) is True
        assert "suppressed since the last message" in caplog.text


class TestNeverRaises:
    """It is called from `finally` blocks. An exception here would replace the error the
    caller was already handling — the failure mode that makes people delete notifiers."""

    def test_a_broken_notification_does_not_raise(self, monkeypatch) -> None:
        def _boom(*_a, **_k):
            raise RuntimeError("render exploded")

        monkeypatch.setattr(nf.Notification, "render", _boom)
        assert nf.notify(_n()) is False

    def test_a_webhook_failure_is_swallowed(self, monkeypatch) -> None:
        """'A Telegram outage must never affect trading.'"""
        monkeypatch.setattr(nf.settings, "notifier_webhook_url", "http://127.0.0.1:1/nope")
        assert nf.notify(_n()) is True  # logged, delivery failed, still reports sent

    def test_no_webhook_configured_is_a_silent_no_op_not_an_error(
        self, monkeypatch
    ) -> None:
        """Unset is the DEFAULT and not a degraded mode — the policy still ran and logged."""
        monkeypatch.setattr(nf.settings, "notifier_webhook_url", None)
        assert nf.notify(_n()) is True

    def test_an_exception_whose_str_raises_still_notifies_with_its_type(
        self, caplog
    ) -> None:
        """⭐ Found by this test: building the message is caller-supplied work (`str(exc)`)
        and can raise BEFORE `notify` is reached, so the guard had to be in the wrapper too.
        It escaped straight through a `finally` and would have masked the original error.

        And the right degradation is not silence — the TYPE is always available and is the
        half that tells you 'bug' vs 'outage', so it still sends.
        """

        class NastyError(Exception):
            def __str__(self) -> str:
                raise RuntimeError("even __str__ is broken")

        with caplog.at_level(logging.ERROR, logger="app.services.notifier"):
            assert nf.notify_exception("e", "t", NastyError()) is True
        assert "NastyError" in caplog.text
        assert "<unprintable>" in caplog.text

    def test_an_unprintable_extra_value_does_not_lose_the_notification(self) -> None:
        class NoStr:
            def __str__(self) -> str:
                raise RuntimeError("nope")

        assert nf.notify_exception("e", "t", ValueError("real"), ctx=NoStr()) is True


class TestRendering:
    def test_the_exception_type_comes_first(self) -> None:
        """The type is what tells you 'bug' vs 'outage' before you open the log."""
        assert nf.describe_exception(ValueError("bad input")).startswith("ValueError: ")

    def test_a_long_exception_is_truncated(self) -> None:
        got = nf.describe_exception(ValueError("x" * 5000))
        assert len(got) == nf.MAX_EXC_CHARS

    def test_the_message_carries_level_title_and_lines(self) -> None:
        text = Notification(
            event="cas_capture", level=Level.ERROR, title="CAS capture failed",
            lines=["written=0", "universe=208"], exception="TimeoutError: kite",
        ).render()
        assert "[ERROR] CAS capture failed" in text
        assert "written=0" in text
        assert "exception: TimeoutError: kite" in text


class TestTaskResultPolicy:
    def test_ok_is_silent_because_the_rows_are_the_confirmation(self) -> None:
        got = nf.notify_task_result("cas_capture", "CAS", {"status": "ok", "written": 208})
        assert got is False

    def test_skipped_is_silent_because_our_tasks_self_guard_constantly(self) -> None:
        assert (
            nf.notify_task_result(
                "cas_capture", "CAS", {"status": "skipped", "message": "outside CAS window"}
            )
            is False
        )

    def test_an_unanticipated_status_speaks(self) -> None:
        """A status we did not plan for is exactly the thing worth looking at."""
        assert nf.notify_task_result("cas_capture", "CAS", {"status": "degraded"}) is True

    def test_a_missing_status_is_treated_as_unanticipated(self) -> None:
        assert nf.notify_task_result("cas_capture", "CAS", {"written": 0}) is True

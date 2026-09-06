"""Session notifier with a noise policy — A11.

## Why this exists

We have standing **manual daily human checks** that exist only because nothing pushes:

  1. **CAS capture** — `make worker` must be up 15:15–15:33 IST, and **a missed window
     cannot be back-filled**. The protocol is "check the row count each morning."
  2. **Provisional health** — the forward watch has no scheduler at all; the protocol is
     "run `scripts/provisional_health.py --days 7` yourself each session."

Both are unrecoverable-or-degrading failures whose detection depends on a human
remembering. That is exactly the job this module does instead.

## The noise policy, and why each rule is here

A notifier that reports everything is a notifier nobody reads, and one that reports nothing
is a log. The rules:

  - **Silence is the default for routine success.** The CAS task fires every minute of the
    market day and returns `skipped: outside CAS window` ~1,400 times; a notifier that said
    so would be pure noise. `INFO` never sends.
  - **The artifact is the confirmation.** When `make analysis` writes its report, the report
    *is* the evidence it ran. A "completed successfully" push adds nothing, so only failure
    and skip speak.
  - **Any exception ALWAYS notifies, bypassing the entire policy** — including the throttle.
    A crash is the one thing that must never be suppressed by a rule written for routine
    traffic, and it carries the exception type plus a truncated message.
  - **Repeats are throttled, and the suppressed count rides the next message.** A worker
    flapping every minute would otherwise send hundreds of identical pushes and train you to
    mute the channel. Suppression is reported, never silent — "(+37 suppressed)" — so a
    throttle can never hide a worsening problem.
  - **A missing channel is a silent no-op, and delivery failure is swallowed.** Callers do
    not branch on whether notification worked. A notifier outage must never affect trading:
    every public entry point here is wrapped so that nothing it does can raise into a
    `finally` block and mask the original error.

⚠ **What this cannot see: an ABSENCE.** Wiring into `finally` reports what ran. The CAS
alarm we actually want — *the window passed and nothing was written* — is a thing that did
NOT happen, and no `finally` fires for it. That needs a scheduled end-of-window check
(A40's worker-liveness territory). Do not read a quiet channel as "the capture worked".

## Transport

One generic webhook (`notifier_webhook_url`), POSTing JSON. Deliberately vendor-neutral —
the policy is the valuable part and it should not be entangled with anyone's message
format. Slack and Discord accept this shape directly; Telegram and ntfy want a five-line
relay. Unset ⇒ log-only, which is the default and is not a degraded mode: the log line is
always emitted at the level the policy chose.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)

#: Longest exception message we forward. A stack-trace-sized push is unreadable on a phone
#: and the log has the full detail anyway.
MAX_EXC_CHARS = 400

#: Identical (event, level) pairs inside this window are counted, not sent.
DEFAULT_THROTTLE_S = 900.0

#: Seconds to wait on the webhook. Short on purpose: this runs inside a `finally`, and a
#: hung notifier delaying a task is a worse outcome than a dropped message.
WEBHOOK_TIMEOUT_S = 5.0


class Level(StrEnum):
    """How loud, and — via the policy — whether it sends at all."""

    INFO = "info"  # routine; never sends. The artifact is the confirmation.
    WARNING = "warning"  # a human may want to act, eventually
    ERROR = "error"  # a human must act


@dataclass(frozen=True)
class Notification:
    event: str  # stable key, e.g. "cas_capture" — the throttle groups on it
    level: Level
    title: str
    lines: list[str] = field(default_factory=list)
    #: `"TypeError: ..."` when the session died. Set this and the policy is bypassed.
    exception: str | None = None

    def render(self) -> str:
        head = f"[{self.level.value.upper()}] {self.title}"
        body = [head, *self.lines]
        if self.exception is not None:
            body.append(f"exception: {self.exception[:MAX_EXC_CHARS]}")
        return "\n".join(body)


def describe_exception(exc: BaseException) -> str:
    """`TypeError: cannot unpack …`, truncated. Type first, because the type is what tells
    you whether this is a bug or an outage before you open the log.

    ⚠ `str(exc)` can itself raise — a `__str__` that blows up is rare but real, and this
    runs while something is already going wrong. The TYPE is always available, so degrade to
    it rather than losing the whole notification.
    """
    try:
        return f"{type(exc).__name__}: {exc}"[:MAX_EXC_CHARS]
    except Exception:
        return f"{type(exc).__name__}: <unprintable>"


class _Throttle:
    """Per-(event, level) suppression with a reported count.

    Deliberately in-process: a worker restart resets it, which is the safe direction — a
    fresh process re-announcing a live problem is better than one inheriting a stale
    suppression and staying quiet about it.
    """

    def __init__(self, window_s: float = DEFAULT_THROTTLE_S, clock: Any = time.monotonic):
        self._window_s = window_s
        self._clock = clock
        self._last: dict[tuple[str, str], float] = {}
        self._suppressed: dict[tuple[str, str], int] = {}

    def admit(self, n: Notification) -> tuple[bool, int]:
        """`(send?, suppressed_since_last)`. An exception always admits and resets."""
        key = (n.event, n.level.value)
        now = self._clock()
        if n.exception is not None:
            self._last[key] = now
            return True, self._suppressed.pop(key, 0)
        last = self._last.get(key)
        if last is not None and now - last < self._window_s:
            self._suppressed[key] = self._suppressed.get(key, 0) + 1
            return False, 0
        self._last[key] = now
        return True, self._suppressed.pop(key, 0)


_throttle = _Throttle()


def should_notify(n: Notification) -> bool:
    """The policy, without the throttle: does this deserve a human's attention at all?

    Pure and separately testable, because it is the part that decides what a quiet channel
    means. An exception bypasses everything — that rule exists so no future noise rule can
    accidentally silence a crash.
    """
    if n.exception is not None:
        return True
    return n.level is not Level.INFO


def notify(n: Notification) -> bool:
    """Deliver if the policy and throttle allow. Returns whether anything was sent.

    NEVER raises. This is called from `finally` blocks, where an exception would replace
    the error the caller was already handling — the failure mode that makes people remove
    notifiers.
    """
    try:
        if not should_notify(n):
            log.debug("notifier: suppressed by policy event=%s level=%s", n.event, n.level)
            return False
        send, suppressed = _throttle.admit(n)
        if not send:
            return False
        text = n.render()
        if suppressed:
            # Never a silent throttle: a growing count IS the signal that something is
            # getting worse while being suppressed.
            text += f"\n(+{suppressed} suppressed since the last message)"
        _log_it(n, text)
        _post_webhook(n, text)
        return True
    except Exception:
        # Including the logging and the POST. Nothing here is worth failing a task over.
        log.debug("notifier failed (non-fatal)", exc_info=True)
        return False


def _log_it(n: Notification, text: str) -> None:
    level = logging.ERROR if n.level is Level.ERROR or n.exception else logging.WARNING
    log.log(level, "notify[%s]: %s", n.event, text.replace("\n", " | "))


def _post_webhook(n: Notification, text: str) -> None:
    url = settings.notifier_webhook_url
    if not url:
        return  # unset ⇒ silent no-op, and callers never branch on it
    try:
        import httpx

        httpx.post(
            url,
            json={
                "event": n.event,
                "level": n.level.value,
                "title": n.title,
                # `text` for Slack-shaped receivers, `content` for Discord-shaped ones.
                "text": text,
                "content": text,
            },
            timeout=WEBHOOK_TIMEOUT_S,
        )
    except Exception:
        # "A Telegram outage must never affect trading" — the rule that made the reference
        # implementation trustworthy enough to wire into a `finally`.
        log.debug("notifier webhook delivery failed (non-fatal)", exc_info=True)


def notify_exception(event: str, title: str, exc: BaseException, **extra: object) -> bool:
    """The always-notifies path, for a `finally`/`except`. Never raises.

    ⚠ The guard has to be HERE, not only inside `notify` — building the message is itself
    caller-supplied work (`str(exc)`, `str(value)`) and it can raise before `notify` is ever
    reached. Found by test: an exception whose `__str__` raises escaped straight through a
    `finally` and would have masked the original error, which is precisely the failure mode
    that gets notifiers deleted.
    """
    try:
        lines = [f"{k}={_safe(v)}" for k, v in extra.items()]
        return notify(
            Notification(
                event=event,
                level=Level.ERROR,
                title=title,
                lines=lines,
                exception=describe_exception(exc),
            )
        )
    except Exception:
        log.debug("notify_exception failed (non-fatal)", exc_info=True)
        return False


def _safe(value: object) -> str:
    """`str(value)` that cannot raise — same reasoning as `describe_exception`."""
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def notify_task_result(event: str, title: str, result: dict[str, object]) -> bool:
    """Report a Celery task's `{"status": ..., ...}` under the policy.

    `ok` is INFO and therefore silent — the rows it wrote are the confirmation. `skipped`
    is INFO too: our tasks self-guard and skip constantly by design (the CAS task returns
    `outside CAS window` roughly 1,400 times a day). Anything else is a WARNING, because a
    status we did not anticipate is exactly the thing worth looking at.
    """
    try:
        status = _safe(result.get("status", "unknown"))
        level = Level.INFO if status in ("ok", "skipped") else Level.WARNING
        lines = [f"{k}={_safe(v)}" for k, v in result.items() if k != "status"]
        return notify(
            Notification(event=event, level=level, title=f"{title}: {status}", lines=lines)
        )
    except Exception:
        log.debug("notify_task_result failed (non-fatal)", exc_info=True)
        return False


def reset_throttle() -> None:
    """Test seam — the module-level throttle is process state."""
    global _throttle
    _throttle = _Throttle()

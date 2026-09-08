"""H7 — a decay alarm on the shadow gates' readiness banners.

## The incident this exists for

The regime gate was promoted ACTIVE on 2026-08-14. Its forward-evidence banner turned
`⏳ NOT READY` on 08-21 and **stayed so for seven consecutive report days** before it was
reverted on 09-02 (the suppressed set had gone net-positive live — the gate was subtracting
~8R). Every one of those seven days the signal was *visible* in `docs/analysis/
regime-gate-shadow-<date>.md`; nothing turned the visible into the alarmed. That is the whole
of H7: **detection existed, alarming did not.**

## What is and is NOT a decay

The naive reading — "alarm on any gate that has been NOT READY for N days" — is wrong and
would be pure noise: every shadow gate is NOT READY right now and will be for weeks, because
none has reached its resolved-trade bar (the leak is upstream of gating). "Still accruing" is
not decay.

A decay worth a PUSH is a regression of a gate we ADOPTED: an **ACTIVE** gate whose readiness
has deteriorated to NOT READY, sustained. That is exactly the regime-gate shape — a gate on
the money path losing its edge — and it is the only thing that pushes:

    decaying  ⟺  trailing NOT-READY run ≥ DECAY_STREAK_DAYS  AND  the gate is ACTIVE

⚠ **A SHADOW gate flipping READY→NOT-READY is NOT a push.** (Caught in review, 2026-09-09: an
earlier version pushed on any in-window READY→NOT-READY flip and would have cried wolf daily
for sector-RS and market-regime — whose banners oscillate on shifting relative P&L, or flip
because a *readiness criterion* was tightened, not because an edge decayed.) A shadow
regression is real information but not actionable in the notifier sense, so it is RECORDED in
the durable table (`shadow_regressed`) and never pushed — the notifier's "never train a human
to mute the channel" rule.

ACTIVE-ness is read from H4's `gate_register` (the finding says H7 is "partly subsumed by
H4"): a gate promoted before the scan window shows no in-window READY→NOT-READY transition, so
its adoption is read from the register rather than inferred from the files.

## Why read the sidecar files rather than re-plumb every gate

Each `make analysis` already writes `docs/analysis/<gate>-shadow-<date>.md` with a readiness
banner. H7 is a **second reader** of that existing daily record — no gate has to learn about
it, adding a gate is one row in `GATES`, and the artifacts are the durable history. A missing
file (analysis not run that day) is simply a day with no observation; it never fabricates one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from app.services import gate_register

if TYPE_CHECKING:  # pragma: no cover
    from app.services.notifier import Notification

log = logging.getLogger(__name__)

#: Trailing NOT-READY report days that make a *regressed/active* gate a decay. Deliberately
#: fewer than the SEVEN the regime gate ran unremedied, so the alarm fires before a human
#: would have caught it by eye.
DECAY_STREAK_DAYS = 5

#: How many calendar days back to look for dated sidecar files. Comfortably longer than the
#: streak so a regression's earlier READY days are still in view.
LOOKBACK_DAYS = 21

#: (human label, sidecar filename stem, gate_register key or None). One row per shadow gate
#: that writes a readiness banner from `scripts/daily_analysis.py`.
GATES: tuple[tuple[str, str, str | None], ...] = (
    ("regime gate (ADX)", "regime-gate-shadow", "regime_adx"),
    ("circuit band", "circuit-gate-shadow", "circuit"),
    ("entry quality (sl_atr)", "entry-quality-shadow", "entry_sl_atr"),
    ("sector RS", "sector-rs-shadow", "sector_rs"),
    ("market regime", "market-regime-shadow", "market_regime"),
    ("liquidity", "liquidity-shadow", "liquidity"),
    ("anti-chase", "chase-shadow", "chase"),
)


@dataclass(frozen=True)
class DayReadiness:
    day: date
    ready: bool


@dataclass(frozen=True)
class GateDecay:
    gate: str
    latest_ready: bool | None  # None ⇒ no observation at all
    not_ready_streak: int  # trailing consecutive NOT-READY report days
    was_ready: bool  # a READY observation earlier in the window (before the streak)
    is_active: bool  # adopted on the money path per the register
    days_observed: int

    @property
    def decaying(self) -> bool:
        """The PUSH-worthy alarm: an ACTIVE gate (adopted on the money path) that has
        regressed to NOT READY for the streak — the regime-gate incident exactly. A SHADOW
        gate flipping READY→NOT-READY is NOT this (see `shadow_regressed`)."""
        return self.not_ready_streak >= DECAY_STREAK_DAYS and self.is_active

    @property
    def shadow_regressed(self) -> bool:
        """A SHADOW gate that was READY and has gone NOT READY for the streak. Worth RECORDING
        (it may be a real change, a tightened readiness criterion, or small-sample noise) but
        NOT worth a push — recorded in the table, never alarmed."""
        return (
            self.not_ready_streak >= DECAY_STREAK_DAYS
            and self.was_ready
            and not self.is_active
        )


def extract_readiness(text: str) -> bool | None:
    """The banner's verdict: True (✅ READY), False (⏳ NOT READY), or None (no banner).

    Reads the authoritative banner line first — the one mentioning "readiness" or "forward
    evidence" — because the body can mention "ready" in prose. "NOT READY" is tested before
    "READY" since it contains it.
    """
    for line in text.splitlines():
        low = line.lower()
        if "readiness" in low or "forward evidence" in low:
            if "not ready" in low:
                return False
            if "ready" in low:
                return True
    # Fallback: whole-document scan, same precedence.
    if "NOT READY" in text:
        return False
    if "READY" in text:
        return True
    return None


def read_history(
    analysis_dir: Path, stem: str, *, today: date, lookback_days: int = LOOKBACK_DAYS
) -> list[DayReadiness]:
    """Readiness for each of the last `lookback_days` dates that has a parseable file,
    oldest-first. Days with no file (weekend, holiday, analysis not run) are simply absent —
    never guessed."""
    hist: list[DayReadiness] = []
    for i in range(lookback_days, -1, -1):
        d = today - timedelta(days=i)
        p = analysis_dir / f"{stem}-{d.isoformat()}.md"
        if not p.exists():
            continue
        try:
            verdict = extract_readiness(p.read_text())
        except Exception:  # noqa: BLE001 — a corrupt sidecar must not break the scan
            log.debug("could not read sidecar %s", p, exc_info=True)
            continue
        if verdict is not None:
            hist.append(DayReadiness(d, verdict))
    return hist


def analyze(gate: str, history: list[DayReadiness], *, is_active: bool) -> GateDecay:
    """Turn a readiness history into a decay verdict."""
    if not history:
        return GateDecay(gate, None, 0, False, is_active, 0)
    streak = 0
    for dr in reversed(history):
        if dr.ready is False:
            streak += 1
        else:
            break
    prefix = history[: len(history) - streak]
    was_ready = any(dr.ready for dr in prefix)
    return GateDecay(
        gate=gate,
        latest_ready=history[-1].ready,
        not_ready_streak=streak,
        was_ready=was_ready,
        is_active=is_active,
        days_observed=len(history),
    )


def scan(analysis_dir: Path, *, today: date, lookback_days: int = LOOKBACK_DAYS) -> list[GateDecay]:
    """Every gate's decay verdict, in `GATES` order. Read-only; never raises."""
    out: list[GateDecay] = []
    for label, stem, reg_key in GATES:
        hist = read_history(analysis_dir, stem, today=today, lookback_days=lookback_days)
        is_active = False
        if reg_key is not None:
            h = gate_register.get(reg_key)
            is_active = h is not None and h.status is gate_register.Status.ACTIVE
        out.append(analyze(label, hist, is_active=is_active))
    return out


def _why(d: GateDecay) -> str:
    reason = (
        "ACTIVE gate was READY and has decayed"
        if d.was_ready
        else "ACTIVE gate losing its edge (adopted before this window)"
    )
    return (
        f"**{d.gate}** — {d.not_ready_streak} consecutive NOT-READY report days "
        f"({reason}; {d.days_observed} days observed)"
    )


def to_notification(decays: list[GateDecay]) -> Notification | None:
    """A single push naming every decaying gate, or None when none is. Deferred notifier
    import keeps this module usable in isolation."""
    from app.services.notifier import Level, Notification

    hits = [d for d in decays if d.decaying]
    if not hits:
        return None
    return Notification(
        event="gate_decay",
        level=Level.WARNING,
        title=f"Shadow-gate decay: {len(hits)} gate(s) regressed to NOT READY",
        lines=[
            *[_why(d) for d in hits],
            "a gate that was READY/ACTIVE and has decayed is the regime-gate shape "
            "(reverted 2026-09-02 after 7 unremedied days) — read the sidecar before acting",
        ],
    )


def render_lines(decays: list[GateDecay]) -> list[str]:
    """The loud block: a header only when a gate is decaying, else empty — a green line for
    'no gate is decaying' would be indistinguishable from 'nothing was scanned'."""
    hits = [d for d in decays if d.decaying]
    if not hits:
        return []
    out = [
        "> ## ⚠️ SHADOW-GATE DECAY ALARM (H7)",
        ">",
        f"> {len(hits)} gate(s) that were READY or are ACTIVE have regressed to NOT READY for",
        f"> ≥{DECAY_STREAK_DAYS} report days — the exact shape that cost ~8R before the regime",
        "> gate was reverted. This is a regression, not mere accrual.",
        ">",
    ]
    out += [f"> - {_why(d)}" for d in hits]
    out.append("")
    return out


def _state(d: GateDecay) -> str:
    if d.latest_ready is None:
        return "— no observations"
    if d.decaying:
        return "⚠️ DECAYING (active)"
    if d.shadow_regressed:
        return "· regressed (shadow, not alarmed)"
    if d.latest_ready:
        return "✅ ready"
    return "⏳ accruing"


def render_markdown(decays: list[GateDecay], day: date) -> str:
    """The dated sidecar: the loud alarm (if any) plus a full status table, so the scan leaves
    a durable record every day whether or not anything fired."""
    out = [f"# Shadow-gate decay scan (H7) — {day.isoformat()}", ""]
    out += render_lines(decays)
    out += [
        "| gate | state | latest | NOT-READY streak | was ready | active | days |",
        "|---|---|---|---:|---|---|---:|",
    ]
    for d in decays:
        latest = "—" if d.latest_ready is None else ("ready" if d.latest_ready else "not ready")
        out.append(
            f"| {d.gate} | {_state(d)} | {latest} | {d.not_ready_streak} | "
            f"{'yes' if d.was_ready else 'no'} | {'yes' if d.is_active else 'no'} | "
            f"{d.days_observed} |"
        )
    out += [
        "",
        f"_Decay = trailing NOT-READY run ≥ {DECAY_STREAK_DAYS} days AND (was READY in-window "
        "OR ACTIVE). A perpetually-accruing shadow gate is not a decay._",
        "",
    ]
    return "\n".join(out)

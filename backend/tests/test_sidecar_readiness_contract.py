"""Completeness contract: every sidecar that prints a readiness verdict must also run the
shared guards AND record its evidence.

**Why this test exists.** The guards and the evidence block were added to four sidecars and
I reported it as "every readiness banner". It was four of seven — and the worst omission
was `entry_quality_shadow`, the one carrying `sl_atr`, the gate closest to a decision. A
second pass then found `circuit_gate_shadow` had the evidence block but NOT the veto, so
its banner could still print READY without the guards running. Both slipped through because
nothing checked the set.

This test AUTO-DISCOVERS `app/services/*_shadow.py`, so a sidecar added later is covered
without anyone remembering to update a list. Exemptions must be declared here WITH A
REASON, which makes every gap visible and argued rather than silent.

**What it proves and does not prove.** It is a static wiring check: it proves the calls
exist in the module, not that they are reached on every code path. Behaviour is covered by
`test_flip_readiness.py` (the guards themselves) and each sidecar's own render tests.
"""

import pathlib
import re

SERVICES = pathlib.Path(__file__).resolve().parent.parent / "app" / "services"

#: A readiness verdict is printed by one of these.
_READINESS_DEF = re.compile(
    r"^def (readiness_line|forward_evidence_ready|[a-z_]*flip_ready)\(", re.M
)

#: Sidecars allowed to skip the shared wiring, each with the reason it is justified.
#: Adding an entry is a deliberate, reviewable act — never a way to silence this test.
EXEMPT: dict[str, str] = {
    "regime_gate_shadow.py": (
        "keeps only aggregate GateMetrics (baseline/gated/killed), no per-trade rows, so "
        "fr.Row cannot be built without restructuring measure(). It already prints a "
        "RICHER record than the shared block — three variants x eight §8 metrics "
        "(trades/decided/win%/Sharpe/maxDD/total-R/expR/reach1R) — and its own logic "
        "already refuses correctly (suppressed set net-POSITIVE => do not flip)."
    ),
}


def _sidecars() -> list[pathlib.Path]:
    return sorted(SERVICES.glob("*_shadow.py"))


def _prints_readiness(src: str) -> bool:
    return bool(_READINESS_DEF.search(src))


class TestSidecarReadinessContract:
    def test_discovery_finds_the_known_sidecars(self) -> None:
        """Guard the guard: if the glob silently matched nothing, every assertion below
        would vacuously pass."""
        names = {p.name for p in _sidecars()}
        assert len(names) >= 7, f"discovery looks broken, found only {names}"
        for expected in (
            "chase_shadow.py", "circuit_gate_shadow.py", "entry_quality_shadow.py",
            "liquidity_shadow.py", "market_regime_shadow.py", "regime_gate_shadow.py",
            "sector_rs_shadow.py",
        ):
            assert expected in names

    def test_every_readiness_sidecar_runs_the_shared_veto(self) -> None:
        missing = [
            p.name
            for p in _sidecars()
            if _prints_readiness(p.read_text())
            and p.name not in EXEMPT
            and "fr.veto" not in p.read_text()
        ]
        assert not missing, (
            "these sidecars print a readiness verdict without running the shared guards, "
            f"so they can still say READY on bad evidence: {missing}. Wire fr.veto() as the "
            "FIRST thing in the readiness function, or add a reasoned EXEMPT entry."
        )

    def test_every_readiness_sidecar_records_its_evidence(self) -> None:
        """The user's rule: a verdict must ship the data behind it, or it cannot be
        re-judged later."""
        missing = [
            p.name
            for p in _sidecars()
            if _prints_readiness(p.read_text())
            and p.name not in EXEMPT
            and "evidence_lines" not in p.read_text()
        ]
        assert not missing, (
            f"these sidecars print a verdict with no evidence-of-record block: {missing}. "
            "Append fr.evidence_lines(...) in render_markdown, or add a reasoned EXEMPT entry."
        )

    def test_a_sidecar_without_a_readiness_verdict_is_not_required_to_wire_anything(
        self,
    ) -> None:
        """`profit_lock_shadow` compares exit policies and prints no READY verdict, so the
        contract must not drag it in — otherwise the rule would be noise."""
        pl = SERVICES / "profit_lock_shadow.py"
        assert pl.exists()
        assert not _prints_readiness(pl.read_text())

    def test_exemptions_are_current_and_reasoned(self) -> None:
        """Stale or bare exemptions are how a contract rots."""
        for name, reason in EXEMPT.items():
            assert (SERVICES / name).exists(), (
                f"EXEMPT names a module that no longer exists: {name}"
            )
            assert _prints_readiness((SERVICES / name).read_text()), (
                f"{name} no longer prints a readiness verdict — drop the stale exemption"
            )
            assert len(reason) > 80, f"{name}'s exemption needs a real reason, not a note"

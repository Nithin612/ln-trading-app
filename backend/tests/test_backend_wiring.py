"""Queue item 2 (second half) — the BUILT-NOT-WIRED lint, for the backend.

⭐ **Why this exists.** It is one of this project's two recurring defect shapes: a capability is
written, reviewed, migrated and merged, and nothing ever calls it. `app/services/ledger.py` is the
case it is named after — built, tested, and imported by `tests/test_ledger.py` **only**, so
`ledger_entries` held 0 rows and no production path could ever add one. Every check the repository
owned was green the whole time, because the module typechecks, lints, and is covered by tests that
assert what it DOES rather than that it is REACHED.

This is the backend half of `frontend/src/test/apiWiring.test.ts`, and it carries the same
contract: a **shrink-only ratchet**. A newly unwired function fails the suite, and so does wiring
one up without deleting its line here.

## ⛔⛔ Reachability is judged from the AST, and that took three attempts

This lint was wrong twice before it was right, each time in the same direction — reporting a debt
as PAID:

1. `\\bname\\b` — matched the *words* "correct" and "chain" in English prose under `app/`.
2. `\\bname\\s*\\(` — still matched, because prose writes *"the option chain (CE+PE legs)"*.
3. `\\bname\\(` — matched the comment `` `record()` refuses a blank one `` in `ledger_wiring.py`,
   so deleting both real call sites would have left this suite green (bug-hunter, 2026-09-18).

So it now collects `ast.Call` nodes instead of searching text. Comments and docstrings cannot
vote, and `test_the_lint_notices_when_the_call_sites_vanish` proves it by removing them.

⛔ **SCOPE.** It still cannot see a call assembled dynamically (`getattr(mod, name)()`), and a
method of the same name on an unrelated class counts as a call. A tripwire for the obvious case,
not proof of reachability.

⚠ `scripts/` and `tests/` are NOT production. A function called only from a script is a tool; a
function called only from a test is the exact failure this lint exists to catch.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_APP = _BACKEND / "app"

#: Modules whose wiring is load-bearing enough to police. Deliberately short and explicit: a
#: blanket scan would be mostly noise, and noise is what turns a ratchet into an approval.
WATCHED = ("app/services/ledger.py",)

#: ⚠ NOT approved — debts with a name against them. The list may only get shorter.
KNOWN_UNWIRED: dict[str, str] = {
    "correct": (
        "ledger.py — corrections are made by hand today; nothing in app/ supersedes a row "
        "automatically. Wire when an automated correction path exists."
    ),
    "chain": (
        "ledger.py — reading a whole chain back is a reconstruction/debug affordance; no "
        "production surface renders one yet."
    ),
    "export_day": (
        "ledger.py — ⛔ THE OFF-BOX EXPORT, and the one that matters most: a ledger on the same "
        "disk as the database it describes protects against nothing, and the 2026-09-07 loss "
        "would have taken both. Queue item 26 (off-box backup) is where this gets a caller."
    ),
}

#: ⭐ Public but reached only from INSIDE their own module — NOT debts. A separate category
#: because the lint judges CROSS-module reachability (it excludes the module under test), so an
#: internal helper would otherwise be filed as dead when it is reached on every call.
INTERNAL_HELPERS: dict[str, str] = {
    "current_commit": (
        "ledger.py — called by `record()` itself, so it is reached in production through every "
        "ledger write. Public because the tests assert the commit is stamped, and because a "
        "future manifest writer will want it directly."
    ),
}


def _public_functions(rel: str) -> set[str]:
    """Top-level `def`/`async def` names that do not start with an underscore."""
    tree = ast.parse((_BACKEND / rel).read_text())
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    }


def _calls_in(source: str) -> set[str]:
    """Every name appearing as the target of a CALL. `f()` and `mod.f()` both count."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _production_calls(
    exclude: str, *, transform: Callable[[str], str] | None = None
) -> set[str]:
    """Calls made anywhere under `app/`, minus the module being judged.

    `transform` lets a test rewrite the sources in memory, which is how the lint's own canary
    removes the ledger call sites without touching the repository.
    """
    excluded = (_BACKEND / exclude).resolve()
    names: set[str] = set()
    for path in sorted(_APP.rglob("*.py")):
        if path.resolve() == excluded:
            continue
        src = path.read_text()
        if transform is not None:
            src = transform(src)
        names |= _calls_in(src)
    return names


def test_the_scan_actually_parsed_something() -> None:
    """The canary. An empty function set or an empty corpus would make every assertion below
    vacuously true — which is how the frontend version of this lint first shipped broken."""
    assert len(list(_APP.rglob("*.py"))) > 100
    for rel in WATCHED:
        assert len(_public_functions(rel)) >= 4, f"{rel}: parsed suspiciously few functions"
    assert len(_production_calls(WATCHED[0])) > 500


def test_no_unwired_function_beyond_the_recorded_debts() -> None:
    unwired: set[str] = set()
    for rel in WATCHED:
        called = _production_calls(rel)
        unwired |= {name for name in _public_functions(rel) if name not in called}

    assert unwired == set(KNOWN_UNWIRED) | set(INTERNAL_HELPERS), (
        f"unwired now: {sorted(unwired)} — recorded: "
        f"{sorted(set(KNOWN_UNWIRED) | set(INTERNAL_HELPERS))}. A capability with no production "
        "caller is the ledger defect repeating; record it here with a reason, or wire it."
    )


def test_every_debt_has_a_reason_and_is_still_a_debt() -> None:
    """The other half of the ratchet: a name left here after it HAS been wired rots into an
    approval, so wiring one up must force its line to be deleted."""
    called = _production_calls(WATCHED[0])
    declared = _public_functions(WATCHED[0])

    for name, reason in KNOWN_UNWIRED.items():
        assert name in declared, f"{name} is no longer a public function — drop it from the list"
        assert name not in called, f"{name} is wired now — delete its line from KNOWN_UNWIRED"
        assert len(reason) > 40, f"{name}: give a real reason, not a placeholder"


def test_an_internal_helper_really_is_called_inside_its_own_module() -> None:
    """The guard on the escape hatch. `INTERNAL_HELPERS` must not become a place to file a
    genuinely dead function: each name has to be called somewhere in its own module."""
    for rel in WATCHED:
        own = _calls_in((_BACKEND / rel).read_text())
        for name in INTERNAL_HELPERS:
            if name in _public_functions(rel):
                assert name in own, (
                    f"{name} is listed as an internal helper but nothing in {rel} calls it — "
                    "it is simply dead, and belongs in KNOWN_UNWIRED or should be deleted"
                )


def test_record_is_wired_which_is_the_whole_point_of_item_2() -> None:
    """The positive assertion. `record` is the function whose absence from production meant
    `ledger_entries` could never gain a row."""
    assert "record" not in KNOWN_UNWIRED
    assert "record" in _production_calls(WATCHED[0])


def test_the_lint_notices_when_the_call_sites_vanish() -> None:
    """⭐⭐ THE LINT'S OWN CANARY, and it is not hypothetical.

    The previous version searched for the TEXT `record(` and was satisfied by the comment
    `` `record()` refuses a blank one `` in `ledger_wiring.py` — so deleting both real call sites
    would have left the item-2 regression green. Here the call sites are rewritten away in memory
    and `record` must then read as unwired. If this ever passes trivially, the lint has stopped
    measuring reachability again.
    """
    without = _production_calls(
        WATCHED[0], transform=lambda src: src.replace("ledger.record(", "ledger.NOTHING(")
    )

    assert "record" not in without, (
        "removing every `ledger.record(` call site left `record` reading as WIRED — the lint is "
        "matching something that is not a call (a comment, a docstring, or an unrelated name)"
    )

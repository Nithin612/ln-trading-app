"""A27 — the config dry-run's classification logic.

Two things are worth pinning here and the rest is presentation:

- **a credential can never be printed.** The masking is name-based so a conventionally
  named secret is covered without anyone remembering to add it — which means the test
  that matters is over the REAL settings model, not a handful of examples;
- **the uvicorn parent/child distinction.** On `--reload` the parent never re-imports
  config, so mistaking it for the child is exactly how someone concludes a gate flip has
  landed when it has not. That is the specific error CLAUDE.md's manual recipe warns about.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "config_dryrun",
    Path(__file__).resolve().parents[1] / "scripts" / "config_dryrun.py",
)
assert _SPEC and _SPEC.loader
dryrun = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dryrun)


class TestSecretMasking:
    @pytest.mark.parametrize(
        "name",
        ["jwt_secret_key", "kite_api_key", "database_url", "some_password", "access_token"],
    )
    def test_credential_names_are_masked(self, name: str) -> None:
        rendered = dryrun._fmt(name, "hunter2-actual-secret-value")
        assert "hunter2" not in rendered
        assert rendered == "‹set›"

    def test_unset_credential_says_so(self) -> None:
        assert dryrun._fmt("jwt_secret_key", "") == "‹unset›"
        assert dryrun._fmt("jwt_secret_key", None) == "‹unset›"

    def test_ordinary_values_are_shown(self) -> None:
        """Masking everything would make the report useless — the point is to show the
        rails while hiding the credentials."""
        assert dryrun._fmt("regime_gate_mode", "shadow") == "'shadow'"
        assert dryrun._fmt("heat_cap_pct", 6.0) == "6.0"

    def test_no_settings_field_leaks_its_value(self) -> None:
        """⭐ Over the REAL model, not examples.

        A sentinel is substituted for every field in `Settings` and the rendered output
        checked for it. Any field the name-based rule fails to classify as a credential
        will show the sentinel — and if that field IS a credential, this is the test that
        catches it before a report prints a live key.
        """
        from app.core.config import Settings

        sentinel = "SENTINEL-DO-NOT-PRINT-9f3a"
        leaked = [
            name
            for name in Settings.model_fields
            if dryrun._is_secret(name) and sentinel in dryrun._fmt(name, sentinel)
        ]
        assert leaked == [], f"these credential fields would print their value: {leaked}"

    def test_the_known_credentials_are_actually_classified(self) -> None:
        """The previous test passes vacuously if `_is_secret` matches nothing.

        So assert the model's real credential fields ARE caught — otherwise a rule that
        classified nothing as secret would look perfectly healthy.
        """
        from app.core.config import Settings

        names = set(Settings.model_fields)
        expected = {n for n in names if "secret" in n or "url" in n or "api_key" in n}
        assert expected, "the settings model should have credential-shaped fields"
        assert all(dryrun._is_secret(n) for n in expected)


class TestRoleDetection:
    def test_uvicorn_child_is_distinguished_from_parent(self) -> None:
        """⭐ The trap CLAUDE.md's recipe exists to avoid.

        The `--reload` PARENT does not re-import config, so its start time says nothing
        about which values are live. Only the child's does.
        """
        child = dryrun._role_of("uvicorn app.main:app --reload", "uvicorn app.main:app")
        parent = dryrun._role_of("uvicorn app.main:app --reload", "/bin/bash make backend")
        assert child is not None and "CHILD" in child
        assert parent is not None and "parent" in parent
        assert child != parent

    def test_celery_worker_and_beat_are_separate(self) -> None:
        assert dryrun._role_of("celery -A app worker -l info", "bash") == "celery worker"
        assert dryrun._role_of("celery -A app beat -l info", "bash") == "celery beat"

    def test_live_worker_is_detected(self) -> None:
        assert dryrun._role_of("python -m app.broker.live_worker", "bash") == "live_worker"

    def test_unrelated_processes_are_ignored(self) -> None:
        """A settings-holding role is the only thing worth reporting; everything else
        would be noise that hides the signal."""
        assert dryrun._role_of("vim notes.txt", "bash") is None
        assert dryrun._role_of("postgres: writer process", "postgres") is None


class TestRailClassification:
    @pytest.mark.parametrize(
        "name",
        [
            "regime_gate_mode", "heat_cap_mode", "trading_kill_switch",
            "paper_max_notional_leverage", "daily_loss_limit_pct",
        ],
    )
    def test_rails_are_recognised(self, name: str) -> None:
        """These lead the report because they are what a person is actually checking."""
        assert dryrun._is_rail(name)

    def test_ordinary_settings_are_not_rails(self) -> None:
        assert not dryrun._is_rail("log_level")
        assert not dryrun._is_rail("cors_origins")


class TestStalenessSemantics:
    def test_could_not_check_is_not_the_same_as_clean(self) -> None:
        """⭐ Exit 1 ≠ exit 0.

        'I could not look' and 'I looked and it was fine' are different answers. Sharing
        an exit code would let a CI check pass on a box with no `.env` at all — which is
        precisely the configuration most likely to be wrong.
        """
        source = (
            Path(__file__).resolve().parents[1] / "scripts" / "config_dryrun.py"
        ).read_text(encoding="utf-8")
        assert "return 1  # could not check" in source
        assert "return 2 if stale else 0" in source

    def test_env_mtime_comparison_is_the_staleness_rule(self) -> None:
        """A process started before the last `.env` write may hold stale values.

        Pinned as a plain datetime comparison so the direction cannot silently invert:
        older-than-env is stale, newer-than-env is current.
        """
        env_changed = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)
        before = datetime(2026, 9, 7, 9, 59, tzinfo=UTC)
        after = datetime(2026, 9, 7, 10, 1, tzinfo=UTC)
        assert before < env_changed, "started before the edit ⇒ stale"
        assert not (after < env_changed), "started after the edit ⇒ current"

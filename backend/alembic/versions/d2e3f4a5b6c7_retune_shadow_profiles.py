"""retune_shadow_profiles — the 6.4 weight-retune A/B, shadow.

Two 1d/eod SHADOW profiles over Nifty50, no setup gating (pure base engine +
group weight multipliers): `retune_base` (no multipliers — the control) and
`retune_momentum_x15` (momentum group ×1.5 — the 6.4 experiment's lead
candidate). Both run on the same nightly `eod` path as the live profiles
(`run_scheduled_profiles` runs active OR shadow) and mint `is_shadow` signals —
measured to outcome by 6.1/6.2 attribution, never tradeable (the order path
admits `status == 'active'` only). This turns the in-sample corpus finding
(`weight-retune-*.md`) into FORWARD out-of-sample evidence; promotion to an
active retune stays a separate sign-off step.

Both arms use the SAME risk_template (rr 2), so the A/B isolates the ENTRY
selection the weights drive (the exit is held constant — this differs from the
corpus experiment's classification-canon TP, but the entry SET is identical).

Config dicts + hashes were generated ONCE by StrategyProfileConfig +
compute_config_hash and frozen here as literals (import-free replay; this file
must never import app code). Test: tests/test_strategy_profiles.py pins them.

Revision ID: d2e3f4a5b6c7
Revises: c5d6e7f8a9b0
Create Date: 2026-08-14
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None

# (config, sha256(config), status) — config is the canonical
# StrategyProfileConfig.model_dump(mode="json") snapshot; both ship SHADOW.
SEEDS: list[tuple[dict, str, str]] = [
    (
        {
            "key": "retune_base",
            "name": "Retune baseline (shadow)",
            "description": (
                "6.4 weight-retune A/B control: base weights via the profile "
                "pipeline, shadow. Pairs with retune_momentum_x15."
            ),
            "style": "swing",
            "timeframe": "1d",
            "schedule": "eod",
            "universe_spec": {"kind": "index", "value": "NIFTY50"},
            "setup_conditions": [],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {"kind": "rr", "ratio": "2"},
            "validity_spec": None,
        },
        "46af6dc8dcf78062fe2fe51d559ac9d11e4ba763a1889f68148950facd241cf1",
        "shadow",
    ),
    (
        {
            "key": "retune_momentum_x15",
            "name": "Retune momentum x1.5 (shadow)",
            "description": (
                "6.4 weight-retune candidate: momentum group x1.5, shadow. "
                "A/B vs retune_base."
            ),
            "style": "swing",
            "timeframe": "1d",
            "schedule": "eod",
            "universe_spec": {"kind": "index", "value": "NIFTY50"},
            "setup_conditions": [],
            "weight_multipliers": {"momentum": 1.5},
            "min_confidence": 70,
            "risk_template": {"kind": "rr", "ratio": "2"},
            "validity_spec": None,
        },
        "f5b74d275c134f1248f97662b40de2644df43ead1b8c3612024ebaeee10c0383",
        "shadow",
    ),
]

_INSERT = sa.text(
    "INSERT INTO strategy_profiles"
    " (key, version, name, description, style, timeframe, schedule,"
    "  universe_spec, setup_conditions, weight_multipliers, min_confidence,"
    "  risk_template, validity_spec, status, config_hash, notes)"
    " VALUES"
    " (:key, 1, :name, :description, :style, :timeframe, :schedule,"
    "  CAST(:universe_spec AS jsonb), CAST(:setup_conditions AS jsonb),"
    "  CAST(:weight_multipliers AS jsonb), :min_confidence,"
    "  CAST(:risk_template AS jsonb), CAST(:validity_spec AS jsonb),"
    "  :status, :config_hash, '6.4 weight-retune shadow A/B')"
)


def upgrade() -> None:
    conn = op.get_bind()
    for config, config_hash, status in SEEDS:
        conn.execute(
            _INSERT,
            {
                "key": config["key"],
                "name": config["name"],
                "description": config["description"],
                "style": config["style"],
                "timeframe": config["timeframe"],
                "schedule": config["schedule"],
                "universe_spec": json.dumps(config["universe_spec"]),
                "setup_conditions": json.dumps(config["setup_conditions"]),
                "weight_multipliers": json.dumps(config["weight_multipliers"]),
                "min_confidence": config["min_confidence"],
                "risk_template": json.dumps(config["risk_template"]),
                "validity_spec": json.dumps(config["validity_spec"]),
                "status": status,
                "config_hash": config_hash,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [config["key"] for config, _, _ in SEEDS]
    conn.execute(
        sa.text("DELETE FROM strategy_profiles WHERE key = ANY(:keys) AND version = 1"),
        {"keys": keys},
    )

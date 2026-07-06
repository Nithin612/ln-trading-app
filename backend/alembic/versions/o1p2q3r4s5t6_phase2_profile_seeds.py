"""phase2_profile_seeds — the eight v1 strategy profiles.

Config dicts and hashes were generated ONCE by StrategyProfileConfig +
compute_config_hash and frozen here as literals (import-free replay: this
file must never import app code). Five EOD profiles ship active; the three
intraday profiles are defined-but-inactive until Phase-3 realtime (they are
walk-forwardable meanwhile). Landed after the slice-5 evaluators so every
seeded setup type has a registered implementation.

Revision ID: o1p2q3r4s5t6
Revises: n0p1q2r3s4t5
Create Date: 2026-07-06
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "o1p2q3r4s5t6"
down_revision = "n0p1q2r3s4t5"
branch_labels = None
depends_on = None

# (config, sha256(config), status) — config is the canonical
# StrategyProfileConfig.model_dump(mode="json") snapshot.
SEEDS: list[tuple[dict, str, str]] = [
    (
        {
            "key": "dc1",
            "name": "Double Confirmation 1",
            "description": "Demand/supply-zone reversal (DC1) on Nifty50 dailies; §6 RR 1:2.",
            "style": "swing",
            "timeframe": "1d",
            "schedule": "eod",
            "universe_spec": {"kind": "index", "value": "NIFTY50"},
            "setup_conditions": [{"type": "dc1", "params": {}}],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {"kind": "rr", "ratio": "2"},
            "validity_spec": None,
        },
        "8e11bbe11db19d8ca9849b6cb9b8b2cd84c06cb7ee70e6cefb772da2326905cd",
        "active",
    ),
    (
        {
            "key": "dc2",
            "name": "Double Confirmation 2",
            "description": "DC1 on the prior candle + confirmation candle now; §6 RR 1:2.",
            "style": "swing",
            "timeframe": "1d",
            "schedule": "eod",
            "universe_spec": {"kind": "index", "value": "NIFTY50"},
            "setup_conditions": [{"type": "dc2", "params": {}}],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {"kind": "rr", "ratio": "2"},
            "validity_spec": None,
        },
        "77528b53851a9f4b975e841a3f6f26cb93630c1c978b70b2fc99fc7fb7bf1aed",
        "active",
    ),
    (
        {
            "key": "rrbo_basic",
            "name": "RRBO (basic)",
            "description": "Resistance breakout with volume (SR_ZONE ≥ 0.9); flat 6% target.",
            "style": "swing",
            "timeframe": "1d",
            "schedule": "eod",
            "universe_spec": {"kind": "index", "value": "NIFTY50"},
            "setup_conditions": [
                {"type": "factor_score", "params": {"factor": "SR_ZONE", "min_score": 0.9}}
            ],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {"kind": "flat_pct", "target_pct": "6"},
            "validity_spec": None,
        },
        "003e53254292c75b32530368814bd8f77d8da7f78599301cf8510f5dd629e3bc",
        "active",
    ),
    (
        {
            "key": "rrbo_trailing",
            "name": "RRBO (trailing)",
            "description": (
                "RRBO with 6% first booking then trail (positions trail_state machinery)."
            ),
            "style": "swing",
            "timeframe": "1d",
            "schedule": "eod",
            "universe_spec": {"kind": "index", "value": "NIFTY50"},
            "setup_conditions": [
                {"type": "factor_score", "params": {"factor": "SR_ZONE", "min_score": 0.9}}
            ],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {
                "kind": "flat_pct_trailing",
                "target_pct": "6",
                "book_fraction": "0.5",
            },
            "validity_spec": None,
        },
        "cad8896626ea94e8314d56cdb9ebf7ce599551e02b712bf9fe924effc5677acf",
        "active",
    ),
    (
        {
            "key": "multibagger",
            "name": "Multibagger EMA setup",
            "description": (
                "20EMA within 2% of 200EMA + breakout (MULTIBAGGER_EMA ≥ 0.9); "
                "15% min target, 20EMA trail."
            ),
            "style": "investment",
            "timeframe": "1d",
            "schedule": "eod",
            "universe_spec": {"kind": "all_active"},
            "setup_conditions": [
                {
                    "type": "factor_score",
                    "params": {"factor": "MULTIBAGGER_EMA", "min_score": 0.9},
                }
            ],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {
                "kind": "ema_trail",
                "min_target_pct": "15",
                "ema_length": 20,
                "ema_timeframe": "1d",
            },
            "validity_spec": None,
        },
        "32920d878bd6f962fb43e476b6f39ccacbe6be77f82f69be9713eed7918330bd",
        "active",
    ),
    (
        {
            "key": "pdh_pdl",
            "name": "PDH/PDL momentum",
            "description": (
                "Previous-day-extreme momentum (BUY above PDH / SELL below PDL); "
                "§6 RR 1:2. Live in Phase 3."
            ),
            "style": "intraday",
            "timeframe": "15m",
            "schedule": "intraday_15m",
            "universe_spec": {"kind": "flag", "value": "fno"},
            "setup_conditions": [{"type": "pdh_breakout", "params": {}}],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {"kind": "rr", "ratio": "2"},
            "validity_spec": None,
        },
        "0ed385a1eef265d4d641a89033f119e7434863880ba8a36a987fc8ad94adcff6",
        "inactive",
    ),
    (
        {
            "key": "orb_15m",
            "name": "Opening range breakout (15m)",
            "description": "First-15-minute range breakout; §6 RR 1:2. Live in Phase 3.",
            "style": "intraday",
            "timeframe": "15m",
            "schedule": "intraday_15m",
            "universe_spec": {"kind": "flag", "value": "fno"},
            "setup_conditions": [{"type": "orb_breakout", "params": {"or_minutes": 15}}],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {"kind": "rr", "ratio": "2"},
            "validity_spec": None,
        },
        "34718a1d37d54cca2f778968111ab0de95c14e369806249735f434d8936d8234",
        "inactive",
    ),
    (
        {
            "key": "gainer_925",
            "name": "9:25 top gainer/loser",
            "description": "9:25 cross-sectional momentum screen; §6 RR 1:1.5. Live in Phase 3.",
            "style": "intraday",
            "timeframe": "5m",
            "schedule": "time_0925",
            "universe_spec": {"kind": "flag", "value": "fno"},
            "setup_conditions": [{"type": "top_gainer_925", "params": {"top_n": 10}}],
            "weight_multipliers": {},
            "min_confidence": 70,
            "risk_template": {"kind": "rr", "ratio": "1.5"},
            "validity_spec": None,
        },
        "244a312206c86f57be4977327622deacc79b217a179c47f7560fcd5446985f95",
        "inactive",
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
    "  :status, :config_hash, 'phase-2 seed (v1)')"
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

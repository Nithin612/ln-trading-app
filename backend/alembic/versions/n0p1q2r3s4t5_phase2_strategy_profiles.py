"""phase2_strategy_profiles — versioned profile rows + signal linkage.

strategy_profiles: immutable version rows; partial unique index enforces
one non-superseded row per key. signals gains profile linkage
(profile_id → exact version, profile_key for dedup across version bumps,
setup_trigger evidence, volatility_reduced attribution — Phase-1 verifier
carry-over) plus the partial unique idempotency index.

Revision ID: n0p1q2r3s4t5
Revises: l8m9n0p1q2r3
Create Date: 2026-07-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "n0p1q2r3s4t5"
down_revision = "l8m9n0p1q2r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("style", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("schedule", sa.String(16), nullable=False),
        sa.Column("universe_spec", JSONB(), nullable=False),
        sa.Column("setup_conditions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("weight_multipliers", JSONB(), nullable=False, server_default="{}"),
        sa.Column("min_confidence", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("risk_template", JSONB(), nullable=False),
        sa.Column("validity_spec", JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="inactive"),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("created_from_version", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("key", "version", name="uq_strategy_profiles_key_version"),
        sa.CheckConstraint(
            "style IN ('intraday','swing','fno','investment')",
            name="ck_strategy_profiles_style",
        ),
        sa.CheckConstraint(
            "schedule IN ('eod','intraday_15m','intraday_5m','time_0925')",
            name="ck_strategy_profiles_schedule",
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive','superseded')",
            name="ck_strategy_profiles_status",
        ),
        sa.CheckConstraint("min_confidence >= 70", name="ck_strategy_profiles_min_conf"),
    )
    op.create_index(
        "uq_strategy_profiles_current",
        "strategy_profiles",
        ["key"],
        unique=True,
        postgresql_where=sa.text("status <> 'superseded'"),
    )
    op.create_index(
        "idx_strategy_profiles_dispatch", "strategy_profiles", ["status", "schedule"]
    )

    op.add_column(
        "signals",
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("strategy_profiles.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("signals", sa.Column("profile_key", sa.String(64), nullable=True))
    op.add_column("signals", sa.Column("setup_trigger", JSONB(), nullable=True))
    op.add_column("signals", sa.Column("volatility_reduced", sa.Boolean(), nullable=True))
    # Idempotency: one ACTIVE suggestion per (stock, profile family) —
    # spans version bumps via profile_key. Legacy rows (NULL key) unaffected.
    op.create_index(
        "uq_signals_active_per_profile",
        "signals",
        ["stock_id", "profile_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND profile_key IS NOT NULL"),
    )
    op.create_index("idx_signals_profile_id", "signals", ["profile_id"])


def downgrade() -> None:
    op.drop_index("idx_signals_profile_id", table_name="signals")
    op.drop_index("uq_signals_active_per_profile", table_name="signals")
    op.drop_column("signals", "volatility_reduced")
    op.drop_column("signals", "setup_trigger")
    op.drop_column("signals", "profile_key")
    op.drop_column("signals", "profile_id")
    op.drop_index("idx_strategy_profiles_dispatch", table_name="strategy_profiles")
    op.drop_index("uq_strategy_profiles_current", table_name="strategy_profiles")
    op.drop_table("strategy_profiles")

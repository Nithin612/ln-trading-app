"""Shadow profiles + shadow signals — run a profile without trading it.

The intraday trio (pdh_pdl, orb_15m, gainer_925) is inactive because
walk-forward returned NEGATIVE risk-adjusted returns for all three
(-1.06 / -0.60 / -0.86 Sharpe). Activating them would fill the Intraday menu
with negative-expectancy suggestions carrying a Buy button, which is worse than
an empty menu. But leaving them switched off produces no evidence either — a
backtest verdict is not a forward one, and nothing was ever going to change it.

`status='shadow'` is the third state that resolves this: the profile RUNS on the
live schedule and its suggestions are scored, recorded and measured to outcome,
but they are never tradeable and never appear on the suggestions table. The
order path already rejects any signal whose status is not exactly 'active'
(app/api/v1/trading.py), so untradeability is enforced by existing code rather
than by a new flag someone has to remember.

Two changes:
  1. strategy_profiles.status gains 'shadow' (the CHECK previously allowed only
     active/inactive/superseded).
  2. A partial unique index mirroring uq_signals_active_per_profile for shadow
     signals — without it, the one-live-suggestion-per-(stock, profile) rule
     that the active path relies on simply would not exist in shadow, and every
     15-minute run would stack duplicates.

signals.status itself needs no DDL: it carries no CHECK constraint.

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
"""

from alembic import op

revision = "z2a3b4c5d6e7"
down_revision = "y1z2a3b4c5d6"
branch_labels = None
depends_on = None

_CK = "ck_strategy_profiles_ck_strategy_profiles_status"
_OLD = "'active'::character varying, 'inactive'::character varying, 'superseded'::character varying"
_NEW = _OLD + ", 'shadow'::character varying"
_IDX = "uq_signals_shadow_per_profile"


def upgrade() -> None:
    op.execute(f"ALTER TABLE strategy_profiles DROP CONSTRAINT {_CK}")
    op.execute(
        f"ALTER TABLE strategy_profiles ADD CONSTRAINT {_CK} "
        f"CHECK ((status)::text = ANY ((ARRAY[{_NEW}])::text[]))"
    )
    # Mirrors uq_signals_active_per_profile, scoped to the shadow layer.
    op.execute(
        f"CREATE UNIQUE INDEX {_IDX} ON signals (stock_id, profile_key) "
        "WHERE status = 'shadow' AND profile_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_IDX}")
    # Rows must stop violating the constraint BEFORE it is re-tightened, or the
    # downgrade fails on any shadow profile that exists. Parking them as
    # 'inactive' is the pre-shadow equivalent: not running, not trading.
    op.execute("UPDATE strategy_profiles SET status = 'inactive' WHERE status = 'shadow'")
    # Shadow signals were never tradeable and never resolved into P&L; expiring
    # them is closer to the truth than promoting them to 'active', which would
    # make untradeable suggestions suddenly orderable.
    op.execute(
        "UPDATE signals SET status = 'expired', expired_at = COALESCE(expired_at, now()) "
        "WHERE status = 'shadow'"
    )
    op.execute(f"ALTER TABLE strategy_profiles DROP CONSTRAINT {_CK}")
    op.execute(
        f"ALTER TABLE strategy_profiles ADD CONSTRAINT {_CK} "
        f"CHECK ((status)::text = ANY ((ARRAY[{_OLD}])::text[]))"
    )

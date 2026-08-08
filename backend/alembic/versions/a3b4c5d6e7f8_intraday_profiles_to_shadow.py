"""Put the three intraday profiles into shadow.

They have been `inactive` since Phase 2, and nothing scheduled them anyway, so
the Intraday menu could never populate. Walk-forward says they should NOT be
activated — all three are negative risk-adjusted (pdh_pdl -1.06 Sharpe,
orb_15m -0.60, gainer_925 -0.86 with a 32% max drawdown; gainer_925's headline
+56.2% is +0.004% per trade over 12,935 trades, i.e. noise before costs). So the
choice is not active-vs-inactive: it is "gather forward evidence" vs "keep
guessing from a backtest".

Shadow runs them on their real schedules and measures every suggestion to
outcome, while the order path (which admits `status='active'` only) keeps them
untradeable. Activation, if it ever happens, is then a decision made on forward
numbers.

Reversible: downgrade returns them to 'inactive', the state they were in.

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
"""

from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "z2a3b4c5d6e7"
branch_labels = None
depends_on = None

_KEYS = "('pdh_pdl', 'orb_15m', 'gainer_925')"


def upgrade() -> None:
    op.execute(
        "UPDATE strategy_profiles SET status = 'shadow'"
        f" WHERE key IN {_KEYS} AND status = 'inactive'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE strategy_profiles SET status = 'inactive'"
        f" WHERE key IN {_KEYS} AND status = 'shadow'"
    )

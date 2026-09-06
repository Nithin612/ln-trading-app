"""add order_events — the append-only order state stream (Phase 7.3, A33).

Purely ADDITIVE: one new table. Nothing reads it yet on the live order path — `place_order`
still calls `place_paper_order` directly — so applying this changes no behaviour and no
recorded number.

**Why a table rather than an audit log beside `orders`.** Today a refused order is not a row
at all: every refusal on the order path raises an exception, and `Order.status` carries
exactly two values in the codebase (the `"pending"` column default and `"filled"`). So the
orders table records only successes, and "what did the risk layer refuse last Tuesday, and
under which thresholds" is not answerable from data. Writing the intent BEFORE the gates run
turns that from a logging gap into a structural guarantee — the row exists before the
decision is made, so a decision cannot fail to be recorded.

Two writers to the same truth drift, and the drift surfaces during reconciliation, which is
the one moment the record has to be trustworthy. So this stream is the source of truth and
`orders` becomes its projection — not the other way round, and not both.

⚠ **No foreign key to `orders`.** A `submitted` (or `denied`) event exists for orders that
never become an `orders` row, which is the entire point. An FK would forbid exactly the case
this table was added for.

Reversible (drop the table).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        # OUR id, gateway-namespaced: "paper:<uuid>" / "kite:<broker_order_id>". The
        # namespace is what lets reconciliation tell "an order we do not know about" from
        # "an order belonging to another gateway" — without it those look identical and
        # the correct response to each is the opposite.
        sa.Column("client_order_id", sa.String(length=64), nullable=False),
        # Per-order and monotonic from 1, so replay is deterministic AND A GAP IS
        # DETECTABLE. The unique constraint below is what makes that a guarantee rather
        # than a convention.
        sa.Column("seq", sa.Integer(), nullable=False),
        # EventKind.value — submitted | denied | accepted | rejected | partially_filled |
        # filled | cancel_requested | cancelled | expired. Deliberately a string, not a
        # PG enum: adding a kind must not require a migration lock on a live table, and
        # the vocabulary is already pinned in code by an exhaustiveness test.
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # Scoped here rather than joined through `orders`, because the row may exist
        # before any order does.
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=False), nullable=True),
        # Kind-specific facts: the deny reason and rule, the broker order id, fill qty and
        # price, the restriction stamps. JSONB so a new kind needs no migration.
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # The integrity rule: one seq per order, once. A duplicate is a bug and a gap is
        # visible, which together are what make the projection trustworthy.
        sa.UniqueConstraint("client_order_id", "seq", name="uq_order_events_order_seq"),
    )
    # Replay one order's stream in order — the projection's hot path.
    op.create_index(
        "ix_order_events_order_seq", "order_events", ["client_order_id", "seq"]
    )
    # "What did we refuse today, and why" — the query this table exists to make possible.
    op.create_index("ix_order_events_user_at", "order_events", ["user_id", "at"])
    op.create_index("ix_order_events_kind_at", "order_events", ["kind", "at"])


def downgrade() -> None:
    op.drop_index("ix_order_events_kind_at", table_name="order_events")
    op.drop_index("ix_order_events_user_at", table_name="order_events")
    op.drop_index("ix_order_events_order_seq", table_name="order_events")
    op.drop_table("order_events")

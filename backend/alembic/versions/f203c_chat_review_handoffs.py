"""Persist research audits and consented AI-legal-assistant handoffs."""

from alembic import op
import sqlalchemy as sa

revision = "f203c"
down_revision = "ead9697ae1c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automated_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "generation_id", sa.Uuid(), sa.ForeignKey("generations.id"), nullable=True
        ),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_automated_reviews_generation_id", "automated_reviews", ["generation_id"]
    )
    op.create_index(
        "ix_automated_reviews_request_hash", "automated_reviews", ["request_hash"]
    )
    op.create_table(
        "legal_handoffs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("consent_processing", sa.Boolean(), nullable=False),
        sa.Column("consent_share_context", sa.Boolean(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("busy_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("legal_handoffs")
    op.drop_index("ix_automated_reviews_request_hash", table_name="automated_reviews")
    op.drop_index("ix_automated_reviews_generation_id", table_name="automated_reviews")
    op.drop_table("automated_reviews")

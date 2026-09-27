"""Durable webhook deliveries."""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(100), nullable=True),
    )
    op.create_index("ix_webhook_deliveries_available_at", "webhook_deliveries", ["available_at"])

def downgrade():
    op.drop_table("webhook_deliveries")

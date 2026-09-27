"""Weekly PDF report settings and delivery history."""
from alembic import op
import sqlalchemy as sa
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('weekly_report_config',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('first_send_date', sa.Date(), nullable=False), sa.Column('to_emails', sa.JSON(), nullable=False), sa.Column('cc_emails', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True))
    op.create_table('weekly_report_runs',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('scheduled_date', sa.Date(), nullable=False, unique=True),
        sa.Column('period_start', sa.Date(), nullable=False), sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('to_emails', sa.JSON(), nullable=False), sa.Column('cc_emails', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(25), nullable=False), sa.Column('pdf', sa.LargeBinary(), nullable=False),
        sa.Column('filename', sa.String(100), nullable=False), sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False), sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True), sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(500), nullable=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('weekly_report_runs')
    op.drop_table('weekly_report_config')

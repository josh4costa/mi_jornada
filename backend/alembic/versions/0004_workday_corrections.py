"""Reversible workday annulments and optimistic revisions."""
from alembic import op
import sqlalchemy as sa
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('workdays', sa.Column('is_void', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('workdays', sa.Column('revision', sa.Integer(), nullable=False, server_default='0'))
    op.drop_index('uq_workday_open_per_technician', table_name='workdays')
    op.create_index('uq_workday_open_per_technician', 'workdays', ['technician_id'], unique=True,
        postgresql_where=sa.text("status='OPEN' AND is_void = false"), sqlite_where=sa.text("status='OPEN' AND is_void = false"))


def downgrade():
    op.drop_index('uq_workday_open_per_technician', table_name='workdays')
    op.drop_column('workdays', 'revision')
    op.drop_column('workdays', 'is_void')
    op.create_index('uq_workday_open_per_technician', 'workdays', ['technician_id'], unique=True,
        postgresql_where=sa.text("status='OPEN'"), sqlite_where=sa.text("status='OPEN'"))

"""Read-only panel access and explicit night shifts."""
from alembic import op
import sqlalchemy as sa
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'READ_ONLY'")
    op.create_table('night_plans',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('technician_id', sa.Uuid(), sa.ForeignKey('technicians.id'), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('reminder_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('replaces_day', sa.Boolean(), nullable=False),
        sa.Column('rest_next_day', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('requested_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reviewed_by', sa.Uuid(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_night_plans_technician_id', 'night_plans', ['technician_id'])
    op.create_index('uq_night_plan_active', 'night_plans', ['technician_id', 'work_date'], unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'APPROVED')"), sqlite_where=sa.text("status IN ('PENDING', 'APPROVED')"))
    op.add_column('workdays', sa.Column('shift_kind', sa.String(10), nullable=False, server_default='DAY'))
    op.add_column('workdays', sa.Column('night_plan_id', sa.Uuid(), nullable=True))
    if op.get_bind().dialect.name == 'postgresql':
        op.create_foreign_key('fk_workday_night_plan', 'workdays', 'night_plans', ['night_plan_id'], ['id'])
    op.create_index('uq_workday_date_shift', 'workdays', ['technician_id', 'work_date', 'shift_kind'], unique=True,
        postgresql_where=sa.text('is_void = false'), sqlite_where=sa.text('is_void = false'))


def downgrade():
    raise RuntimeError('La reversión requiere revisar las jornadas nocturnas; no se elimina su historial automáticamente.')

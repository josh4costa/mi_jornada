"""Schedules, leave requests, incidents and durable reminder log."""
from alembic import op
import sqlalchemy as sa
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('technicians', sa.Column('reminders_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('uq_technician_reminder_phone', 'technicians', ['phone'], unique=True,
                    postgresql_where=sa.text('reminders_enabled = true'), sqlite_where=sa.text('reminders_enabled = 1'))
    op.create_table('attendance_scan', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('last_day', sa.Date(), nullable=True))
    common = lambda: [sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('technician_id', sa.Uuid(), sa.ForeignKey('technicians.id'), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)]
    review = lambda: [sa.Column('status', sa.String(20), nullable=False), sa.Column('reviewed_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True), sa.Column('review_note', sa.String(1000), nullable=True), sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True)]
    op.create_table('leave_requests', *common(), *review(),
        sa.Column('kind', sa.String(20), nullable=False), sa.Column('start_date', sa.Date(), nullable=False), sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False), sa.Column('requested_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False))
    op.create_table('attendance_incidents', *common(), *review(),
        sa.Column('workday_id', sa.Uuid(), sa.ForeignKey('workdays.id'), nullable=True), sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('kind', sa.String(30), nullable=False), sa.Column('reason', sa.String(1000), nullable=False),
        sa.UniqueConstraint('technician_id', 'work_date', 'kind', name='uq_attendance_incident'))
    op.create_table('attendance_events', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True), sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(40), nullable=False), sa.Column('details', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('reminder_deliveries', *common(), sa.Column('work_date', sa.Date(), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('provider_id', sa.String(100), nullable=True), sa.Column('error', sa.String(100), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True), sa.UniqueConstraint('technician_id', 'work_date', 'kind', name='uq_reminder_day'))
    for table in ['leave_requests', 'attendance_incidents', 'reminder_deliveries']:
        op.create_index('ix_' + table + '_technician_id', table, ['technician_id'])


def downgrade():
    for table in ['attendance_scan', 'reminder_deliveries', 'attendance_events', 'attendance_incidents', 'leave_requests']:
        op.drop_table(table)
    op.drop_index('uq_technician_reminder_phone', table_name='technicians')
    op.drop_column('technicians', 'reminders_enabled')

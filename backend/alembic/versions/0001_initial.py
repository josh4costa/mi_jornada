"""initial

Revision ID: 0001
Revises: 
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Handle SQLite for testing where enums and JSONB might be tricky
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == 'sqlite'

    # Enums
    user_role = sa.Enum('ADMIN', 'TECHNICIAN', name='userrole')
    workday_status = sa.Enum('OPEN', 'CLOSED', name='workdaystatus')
    task_status = sa.Enum('PENDING', 'COMPLETED', 'CANCELLED', name='taskstatus')
    task_priority = sa.Enum('NORMAL', 'HIGH', name='taskpriority')
    created_by_type = sa.Enum('ADMIN', 'TECHNICIAN', name='createdbytype')
    audit_action = sa.Enum('LOGIN', 'CHECK_IN', 'CHECK_OUT', 'TASK_CREATED', 'TASK_COMPLETED', 'TASK_CANCELLED', 'USER_CREATED', 'USER_DISABLED', name='auditaction')

    # Users Table
    op.create_table('users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('role', user_role, nullable=False, server_default='TECHNICIAN'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1' if is_sqlite else 'true'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Technicians Table
    op.create_table('technicians',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('employee_number', sa.String(length=30), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1' if is_sqlite else 'true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_number'),
        sa.UniqueConstraint('user_id')
    )

    # Workdays Table
    op.create_table('workdays',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('technician_id', sa.Uuid(), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('check_in_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('check_in_latitude', sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column('check_in_longitude', sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column('check_in_accuracy', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('check_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('check_out_latitude', sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column('check_out_longitude', sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column('check_out_accuracy', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('status', workday_status, nullable=False, server_default='OPEN'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['technician_id'], ['technicians.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workdays_work_date'), 'workdays', ['work_date'], unique=False)
    
    # Tasks Table
    op.create_table('tasks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('technician_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_date', sa.Date(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location_name', sa.String(length=150), nullable=True),
        sa.Column('scheduled_time', sa.Time(), nullable=True),
        sa.Column('priority', task_priority, nullable=False, server_default='NORMAL'),
        sa.Column('status', task_status, nullable=False, server_default='PENDING'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_by_type', created_by_type, nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completion_comment', sa.Text(), nullable=True),
        sa.Column('external_service_order_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['technician_id'], ['technicians.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_assigned_date'), 'tasks', ['assigned_date'], unique=False)
    op.create_index(op.f('ix_tasks_technician_id'), 'tasks', ['technician_id'], unique=False)

    # RefreshTokens Table
    op.create_table('refresh_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='0' if is_sqlite else 'false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # AuditLog Table
    json_type = sa.JSON() if is_sqlite else postgresql.JSONB(astext_type=sa.Text())
    op.create_table('audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('action', audit_action, nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('metadata_json', json_type, nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_timestamp'), 'audit_log', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_log_user_id'), 'audit_log', ['user_id'], unique=False)

    # Indexes
    op.create_index('ix_workdays_technician_date', 'workdays', ['technician_id', 'work_date'])
    
    if not is_sqlite:
        op.execute("CREATE UNIQUE INDEX uq_workday_open_per_technician ON workdays (technician_id) WHERE status='OPEN'")
    else:
        # SQLite partial index syntax
        op.execute("CREATE UNIQUE INDEX uq_workday_open_per_technician ON workdays (technician_id) WHERE status='OPEN'")


def downgrade() -> None:
    pass

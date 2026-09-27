"""Personal passwords, single-use recovery and task locations."""
from alembic import op
import sqlalchemy as sa
import uuid
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('credential_version', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('password_resets',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True), sa.Column('credential_version', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False), sa.Column('used_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_password_resets_user_id', 'password_resets', ['user_id'])
    locations = op.create_table('task_locations',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('group_name', sa.String(30), nullable=False),
        sa.Column('name', sa.String(100), nullable=False), sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.UniqueConstraint('group_name', 'name'))
    groups = {
        'EL POLLO LOCO': ['Expo', 'Juárez', 'Cadereyta', 'Linares', 'Montemorelos', 'Allende', 'Santiago', 'Las Quintas', 'Eloy Cavazos', 'Pablo Livas', 'Guerrero', 'Carrizo', 'Aeropuerto', 'San Roque'],
        'TACO PALENQUE': ['Santiago', 'Contry', 'Centrito'], 'Otras ubicaciones': ['TP Cocina', 'Oficinas Centrales']}
    op.bulk_insert(locations, [dict(id=uuid.uuid5(uuid.NAMESPACE_URL, 'mi-jornada/location/' + g + '/' + n), group_name=g, name=n, is_active=True, revision=0) for g, names in groups.items() for n in names])
    with op.batch_alter_table('tasks') as batch:
        batch.add_column(sa.Column('location_id', sa.Uuid(), sa.ForeignKey('task_locations.id', name='fk_tasks_location_id'), nullable=True))


def downgrade():
    op.drop_column('tasks', 'location_id')
    op.drop_table('task_locations')
    op.drop_table('password_resets')
    op.drop_column('users', 'credential_version')
    op.drop_column('users', 'must_change_password')

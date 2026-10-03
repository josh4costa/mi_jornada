"""Recoverable removal of technicians; preserve attendance history."""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    raise RuntimeError('Conservar el estado de eliminación; no revertir automáticamente.')

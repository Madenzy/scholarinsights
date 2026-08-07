"""initial schema

Revision ID: c3825d72fd27
Revises: 
Create Date: 2026-06-02 11:40:17.905970

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3825d72fd27'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Add is_active to schools only if the column doesn't already exist
    cols = [row[1] for row in conn.execute(sa.text("PRAGMA table_info(schools)"))]
    if 'is_active' not in cols:
        with op.batch_alter_table('schools', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))

    # Add is_active to users only if the column doesn't already exist
    cols = [row[1] for row in conn.execute(sa.text("PRAGMA table_info(users)"))]
    if 'is_active' not in cols:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_active')

    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.drop_column('is_active')

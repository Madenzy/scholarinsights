"""add unique constraint on students.user_id

Revision ID: a9c2df6080f1
Revises: 7e8d137f7152
Create Date: 2026-10-01 11:22:13.148088

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9c2df6080f1'
down_revision = '7e8d137f7152'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_students_user_id', ['user_id'])


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_constraint('uq_students_user_id', type_='unique')

"""add grade bands and per-grade pass/remark

Revision ID: d5df2a1c72b1
Revises: a9c2df6080f1
Create Date: 2026-10-01 12:35:49.146559

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5df2a1c72b1'
down_revision = 'a9c2df6080f1'
branch_labels = None
depends_on = None

# Mirrors models.DEFAULT_GRADE_BANDS / the old GRADE_REMARKS mapping. Kept as
# literal data here (not imported from models) so this migration still does
# the right thing even if those constants change or disappear later.
DEFAULT_BANDS = [
    ('A', 80, 'Excellent', True),
    ('B', 65, 'Well done', True),
    ('C', 50, 'Satisfactory', True),
    ('D', 40, 'Needs improvement', True),
    ('F', 0, 'Work harder', False),
]
OLD_REMARKS = {letter: remark for letter, _, remark, _ in DEFAULT_BANDS}


def upgrade():
    op.create_table(
        'grade_bands',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('letter', sa.String(length=4), nullable=False),
        sa.Column('min_score', sa.Float(), nullable=False),
        sa.Column('remark', sa.String(length=50), nullable=True),
        sa.Column('is_pass', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.UniqueConstraint('school_id', 'letter', name='uq_gradeband_school_letter'),
    )

    with op.batch_alter_table('grades', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_pass', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('auto_remark', sa.String(length=50), nullable=True))
        batch_op.alter_column(
            'grade_letter',
            existing_type=sa.VARCHAR(length=2),
            type_=sa.String(length=4),
            existing_nullable=True,
        )

    # --- data backfill -----------------------------------------------
    bind = op.get_bind()

    schools = sa.table('schools', sa.column('id', sa.Integer))
    grade_bands = sa.table(
        'grade_bands',
        sa.column('school_id', sa.Integer), sa.column('letter', sa.String),
        sa.column('min_score', sa.Float), sa.column('remark', sa.String),
        sa.column('is_pass', sa.Boolean), sa.column('sort_order', sa.Integer),
    )
    grades = sa.table(
        'grades',
        sa.column('id', sa.Integer), sa.column('grade_letter', sa.String),
        sa.column('is_pass', sa.Boolean), sa.column('auto_remark', sa.String),
    )

    school_ids = [row[0] for row in bind.execute(sa.select(schools.c.id))]
    for sid in school_ids:
        bind.execute(grade_bands.insert(), [
            {
                'school_id': sid, 'letter': letter, 'min_score': min_score,
                'remark': remark, 'is_pass': is_pass, 'sort_order': i,
            }
            for i, (letter, min_score, remark, is_pass) in enumerate(DEFAULT_BANDS)
        ])

    for row in bind.execute(sa.select(grades.c.id, grades.c.grade_letter)):
        letter = row.grade_letter
        bind.execute(
            grades.update().where(grades.c.id == row.id).values(
                is_pass=(letter != 'F'),
                auto_remark=OLD_REMARKS.get(letter),
            )
        )


def downgrade():
    with op.batch_alter_table('grades', schema=None) as batch_op:
        batch_op.alter_column(
            'grade_letter',
            existing_type=sa.String(length=4),
            type_=sa.VARCHAR(length=2),
            existing_nullable=True,
        )
        batch_op.drop_column('auto_remark')
        batch_op.drop_column('is_pass')

    op.drop_table('grade_bands')

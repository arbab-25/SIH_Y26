"""Add violations.rule_ref for exact rule deep-links

Revision ID: a1f2c3d4e5f6
Revises: fe827f381c05
Create Date: 2026-09-19 14:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'a1f2c3d4e5f6'
down_revision: Union[str, None] = 'fe827f381c05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'violations',
        sa.Column('rule_ref', sa.String(length=100), nullable=True)
    )
    op.create_index('ix_violations_rule_ref', 'violations', ['rule_ref'])


def downgrade() -> None:
    op.drop_index('ix_violations_rule_ref', table_name='violations')
    op.drop_column('violations', 'rule_ref')

"""add scans.scan_meta JSON column

Revision ID: b4d1c7a9e3f2
Revises: 91a7d4e2d9ca
Create Date: 2026-09-23

Nullable JSON column carrying non-gating scan telemetry (barcode cross-check
results, preprocessing notes). Nullable, so existing rows are untouched.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = 'b4d1c7a9e3f2'
down_revision: Union[str, None] = '91a7d4e2d9ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'scans',
        sa.Column(
            'scan_meta',
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('scans', 'scan_meta')

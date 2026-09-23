"""phase3: refresh_tokens, rule_versions, scans.rule_version

Revision ID: c7e2f8a4b9d1
Revises: b4d1c7a9e3f2
Create Date: 2026-09-23

New tables + one nullable column on scans. Existing data is untouched.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = 'c7e2f8a4b9d1'
down_revision: Union[str, None] = 'b4d1c7a9e3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('replaced_by_id', sa.Uuid(), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        # sa.false() renders as FALSE on Postgres and 0 on SQLite — a literal
        # '0' fails on Postgres with: column is of type boolean but default
        # expression is of type integer.
        sa.Column('family_revoked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_family_id'), 'refresh_tokens', ['family_id'], unique=False)

    op.create_table(
        'rule_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('version_code', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_document', sa.String(length=255), nullable=True),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rule_versions_version_code'), 'rule_versions', ['version_code'], unique=True)

    op.add_column(
        'scans',
        sa.Column('rule_version', sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('scans', 'rule_version')
    op.drop_index(op.f('ix_rule_versions_version_code'), table_name='rule_versions')
    op.drop_table('rule_versions')
    op.drop_index(op.f('ix_refresh_tokens_family_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

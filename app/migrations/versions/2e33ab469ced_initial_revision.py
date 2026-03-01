"""initial revision

Revision ID: 2e33ab469ced
Revises: 
Create Date: 2026-02-25 23:27:04.950424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2e33ab469ced'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    # Вставляем роли
    op.bulk_insert(
        sa.table(
            'roles',
            sa.column('name', sa.String),
            sa.column('created_at', sa.TIMESTAMP),
            sa.column('updated_at', sa.TIMESTAMP),
        ),
        [
            {"name": "User"},
            {"name": "Moderator"},
            {"name": "Admin"},
            {"name": "Superadmin"}
        ]
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password', sa.String(), nullable=False),
        sa.Column('role_id', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone_number')
    )


def downgrade() -> None:
    op.drop_table('users')
    op.drop_table('roles')

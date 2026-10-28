"""drop_hashed_password_server_default

Revision ID: c8a2e465c6e2
Revises: 6b8b9af3d05e
Create Date: 2026-10-29 00:00:00.000000

users.hashed_password の初期値 '' を外す。
パスワードを入れ忘れたユーザー作成を、空文字で保存せず NOT NULL 制約のエラーにするため。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a2e465c6e2'
down_revision: Union[str, None] = '6b8b9af3d05e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'users',
        'hashed_password',
        existing_type=sa.String(length=255),
        existing_nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        'users',
        'hashed_password',
        existing_type=sa.String(length=255),
        existing_nullable=False,
        server_default='',
    )

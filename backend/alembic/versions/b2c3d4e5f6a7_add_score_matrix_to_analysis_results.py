"""analysis_results テーブルにスコアマトリクスのカラムを追加する

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-17

"""
# Union[str, None] のような型ヒントを書くために必要
from typing import Sequence, Union

# op: add_column / drop_column などの DB 操作メソッドを提供するオブジェクト
from alembic import op
# sa: sa.Column() / sa.Float() のようにカラムの型を定義するために使う
import sqlalchemy as sa


# このマイグレーション自身の ID
revision: str = 'b2c3d4e5f6a7'
# 1つ前のマイグレーションの ID。ここで実行順序が決まる（チェーン構造）
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
# 並列マイグレーションブランチの管理用（今回は使わない）
branch_labels: Union[str, Sequence[str], None] = None
# 別マイグレーションへの依存関係（今回は使わない）
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """alembic upgrade head を実行したときに呼ばれる（カラム追加）"""
    op.add_column('analysis_results', sa.Column('total_score', sa.Float(), nullable=True))
    op.add_column('analysis_results', sa.Column('faithfulness_score', sa.Float(), nullable=True))
    op.add_column('analysis_results', sa.Column('technique_score', sa.Float(), nullable=True))
    op.add_column('analysis_results', sa.Column('naturalness_penalty', sa.Float(), nullable=True))


def downgrade() -> None:
    """alembic downgrade -1 を実行したときに呼ばれる（upgrade の逆操作）"""
    op.drop_column('analysis_results', 'naturalness_penalty')
    op.drop_column('analysis_results', 'technique_score')
    op.drop_column('analysis_results', 'faithfulness_score')
    op.drop_column('analysis_results', 'total_score')

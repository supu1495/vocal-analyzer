"""
Alembic環境設定
マイグレーション実行時にDBへの接続とモデル情報を提供する
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# /app 配下の models.py / database.py を参照できるようにパスを追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# models.py のテーブル定義を読み込むために必要
# このimportがないとAlembicがテーブルを認識できない
import models  # noqa: F401
from database import Base

# alembic.ini のログ設定を読み込む
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembicに「どのテーブルを管理するか」を教える
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    DATABASE_URL を環境変数から取得する
    alembic.ini には書かず、docker-compose.yml の environment から取得する
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 環境変数が設定されていません")
    return url


def run_migrations_offline() -> None:
    """
    オフラインモード: DBに接続せずSQLファイルだけ生成する
    本番DBに直接繋がない環境でSQLを事前確認したいときに使う
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    オンラインモード: DBに直接接続してマイグレーションを実行する
    通常の開発・本番デプロイで使用する
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # マイグレーション後は接続を即時解放する
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

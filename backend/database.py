"""
データベース接続設定
SQLAlchemyのエンジン・セッション・Baseクラスを提供する
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# docker-compose.yml の environment から取得
DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)

# autocommit=False: 明示的にcommit/rollbackを呼ぶ（意図しない変更を防ぐ）
# autoflush=False: commit前に自動でSQLが走らないようにする
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """全モデルの基底クラス"""
    pass


def get_db():
    """
    FastAPIのDependency Injection用セッション取得関数
    リクエスト処理が終わったら自動でセッションを閉じる

    使用例:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

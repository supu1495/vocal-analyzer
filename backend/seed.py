"""
開発用シードスクリプト
DB リセット後にテスト用アカウントとサンプル分析結果を投入する

実行: docker compose exec backend python seed.py
冪等性: 既存ユーザーがいる場合はスキップする
"""

from datetime import timedelta

from database import SessionLocal
from models import AnalysisResult, User, now_utc
from auth_utils import hash_password


TEST_USERS = [
    {"email": "test1@example.com", "password": "password123"},
    {"email": "test2@example.com", "password": "password123"},
]

SAMPLE_ANALYSES = [
    {"song_title": "Lemon", "artist_name": "米津玄師", "pitch": 72.5, "rhythm": 68.0, "days_ago": 14},
    {"song_title": "Pretender", "artist_name": "Official髭男dism", "pitch": 75.0, "rhythm": 71.5, "days_ago": 10},
    {"song_title": "夜に駆ける", "artist_name": "YOASOBI", "pitch": 78.0, "rhythm": 74.0, "days_ago": 7},
    {"song_title": "Feeling", "artist_name": "Mrs. GREEN APPLE", "pitch": 80.5, "rhythm": 77.0, "days_ago": 3},
    {"song_title": "ケセラセラ", "artist_name": "Mrs. GREEN APPLE", "pitch": 83.0, "rhythm": 79.5, "days_ago": 1},
]


def seed_users(db) -> dict[str, User]:
    """テストユーザーを作成。既存ならスキップして取得する"""
    users = {}
    for spec in TEST_USERS:
        existing = db.query(User).filter(User.email == spec["email"]).first()
        if existing:
            print(f"  - skip: {spec['email']} (already exists)")
            users[spec["email"]] = existing
            continue
        user = User(
            email=spec["email"],
            hashed_password=hash_password(spec["password"]),
            disclaimer_accepted=True,
        )
        db.add(user)
        db.flush()  # id を確定させる
        print(f"  + create: {spec['email']} (id={user.id})")
        users[spec["email"]] = user
    return users


def seed_analyses(db, user: User) -> None:
    """指定ユーザーにサンプル分析結果を投入。既に1件でもあればスキップする"""
    existing_count = db.query(AnalysisResult).filter(AnalysisResult.user_id == user.id).count()
    if existing_count > 0:
        print(f"  - skip: analyses for {user.email} (already {existing_count} records)")
        return

    base_time = now_utc()
    for spec in SAMPLE_ANALYSES:
        record = AnalysisResult(
            user_id=user.id,
            song_title=spec["song_title"],
            artist_name=spec["artist_name"],
            pitch_accuracy=spec["pitch"],
            rhythm_score=spec["rhythm"],
            techniques={
                "vibrato": {"count": 3, "avg_frequency": 5.5, "avg_depth": 50.0},
                "kobushi": {"count": 2, "timestamps": [12.5, 45.0]},
                "fall": {"count": 1, "avg_depth": 120.0},
                "shakuri": {"count": 4, "avg_height": 80.0},
                "long_tone": {"count": 2, "avg_duration": 3.2},
            },
            created_at=base_time - timedelta(days=spec["days_ago"]),
        )
        db.add(record)
    print(f"  + create: {len(SAMPLE_ANALYSES)} analyses for {user.email}")


def main() -> None:
    db = SessionLocal()
    try:
        print("Seeding users...")
        users = seed_users(db)

        print("Seeding sample analyses...")
        seed_analyses(db, users["test1@example.com"])

        db.commit()
        print("Done.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

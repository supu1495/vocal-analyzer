"""
データベースモデル定義
PostgreSQLのテーブル構造をSQLAlchemyのORMで定義する
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def now_utc() -> datetime:
    """タイムゾーン付きの現在UTC時刻を返す"""
    return datetime.now(timezone.utc)


class User(Base):
    """
    ユーザーテーブル
    免責同意済みのユーザー情報と声紋データを保持する
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # 声紋データ: 将来的にベクトルデータを格納するためJSONで保持
    voiceprint_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    disclaimer_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc
    )

    # リレーション: 1ユーザーが複数の分析結果を持つ
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(
        "AnalysisResult", back_populates="user"
    )


class AnalysisResult(Base):
    """
    分析結果テーブル
    音声分析の結果を保存する（音声ファイル本体は著作権保護のため保存しない）
    """

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 認証実装前はNullableにしておく（Phase 4完了後にNOT NULLへ変更予定）
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    song_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    artist_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    # 分析スコア（0.0〜1.0 の範囲）
    pitch_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhythm_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 歌唱テクニック一覧: ["vibrato", "melisma"] のようなリスト
    techniques: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # 音域: {"min_hz": 130.0, "max_hz": 880.0} のような辞書
    vocal_range: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # AIフィードバックテキスト
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc
    )

    # リレーション
    user: Mapped["User | None"] = relationship("User", back_populates="analysis_results")

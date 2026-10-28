import logging
import os

from logging_config import setup_logging
from secret_check import validate_secrets

# ルーターを import すると auth_utils が SECRET_KEY を読むため、その前にチェックする
setup_logging()
validate_secrets()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from api.analysis import router as analysis_router  # noqa: E402
from api.auth import router as auth_router  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(
    title="vocal-analyzer API",
    description="カラオケ音声分析システムのバックエンドAPI",
    version="0.1.0",
)

# CORS 許可オリジンはカンマ区切りで CORS_ALLOWED_ORIGINS 環境変数から読む
# 例: "http://localhost:5173,https://vocal-analyzer.supu361.dev"
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]
logger.info("Application starting. CORS allowed origins: %s", allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    # このアプリは GET（取得系）と POST（ログイン・登録・アップロード・ログアウト）のみ使用
    allow_methods=["GET", "POST"],
    # JSON / FormData で使う Content-Type のみ許可（Cookie は allow_credentials で別途扱われる）
    allow_headers=["Content-Type"],
    # 別オリジンの fetch では標準外のレスポンスヘッダーを JS から読めないため明示的に公開する
    # Retry-After: ログイン制限（429）の残り秒数。フロントが解除時刻の表示に使う
    expose_headers=["Retry-After"],
)

# ルーターを登録
app.include_router(auth_router)
app.include_router(analysis_router)

@app.get("/")
def root():
    return {"message": "vocal-analyzer API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
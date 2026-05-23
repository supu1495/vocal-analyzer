import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.analysis import router as analysis_router
from api.auth import router as auth_router

app = FastAPI(
    title="vocal-analyzer API",
    description="カラオケ音声分析システムのバックエンドAPI",
    version="0.1.0",
)

# CORS 許可オリジンはカンマ区切りで CORS_ALLOWED_ORIGINS 環境変数から読む
# 例: "http://localhost:5173,https://vocal-analyzer.supu361.dev"
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.analysis import router as analysis_router
from api.auth import router as auth_router
import os

app = FastAPI(
    title="vocal-analyzer API",
    description="カラオケ音声分析システムのバックエンドAPI",
    version="0.1.0",
)

_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,https://vocal-analyzer.supu361.dev",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
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
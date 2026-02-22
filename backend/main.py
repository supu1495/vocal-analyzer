from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="vocal-analyzer API",
    description="カラオケ音声分析システムのバックエンドAPI",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "vocal-analyzer API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
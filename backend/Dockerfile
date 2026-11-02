FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-nodeps.txt ./
RUN pip install --no-cache-dir --no-deps -r requirements-nodeps.txt && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# ビルドしたコミットの ID（git rev-parse HEAD の40文字）。/health で返し、フロントのコミットと比べる
# 渡し方: GIT_COMMIT=$(git rev-parse HEAD) docker compose build backend（scripts/deploy_backend.sh が行う）
# pip install より後ろに置く。前に置くと、コミットが変わるたびにライブラリのインストールからやり直しになる
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
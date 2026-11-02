#!/usr/bin/env bash
# 本番の backend / celery_worker を main の最新に更新する
# 本番用フォルダ（~/works/vocal-analyzer-prod）で実行する: scripts/deploy_backend.sh
#
# 流れ: 安全確認 → git pull → コミットIDを焼き込んでビルド・起動 → マイグレーション → /health のコミットIDを確認
# 手順の背景は docs/DEPLOY.md
set -euo pipefail

# どこから実行しても、リポジトリの一番上で動かす
cd "$(dirname "$0")/.."

fail() {
  echo "中止: $*" >&2
  exit 1
}

# ── 1. 本番用フォルダかどうか ─────────────────────────────────────────────
# ここで止まる設定のまま進むと、開発用の設定（コードの mount・--reload）で本番が動いてしまう
# .env の値は画面に出さない（grep -q で有無だけ見る）

[[ -f .env ]] || fail ".env がありません。本番用フォルダで実行してください"

grep -q '^COMPOSE_PROJECT_NAME=vocal-analyzer$' .env \
  || fail ".env の COMPOSE_PROJECT_NAME が vocal-analyzer ではありません。本番用フォルダで実行してください"

[[ "${COMPOSE_FILE:-}" != *dev* ]] \
  || fail "シェルの COMPOSE_FILE に開発用の設定が入っています（unset COMPOSE_FILE してから実行）"

if grep -q '^COMPOSE_FILE=.*dev' .env; then
  fail ".env の COMPOSE_FILE に開発用の設定が入っています"
fi

[[ ! -e docker-compose.override.yml ]] \
  || fail "docker-compose.override.yml があります。本番では自動で読まれてしまうので消してください"

# ── 2. git の状態 ─────────────────────────────────────────────────────────
# 本番用フォルダでは main を pull するだけにする。手で変えたファイルがあったら止める

[[ "$(git branch --show-current)" == "main" ]] || fail "ブランチが main ではありません"
[[ -z "$(git status --porcelain)" ]] || fail "コミットしていない変更があります（git status で確認）"

echo "▶ git pull"
git pull --ff-only

# ── 3. 最終確認: 実際に読まれる設定に、コードの mount がないか ──────────
# --no-interpolate: .env の値を埋め込まずに出す（秘密を扱わないため）。出力は画面に出さない
if docker compose config --no-interpolate | grep -q 'target: /app$'; then
  fail "backend / celery_worker にコードの mount（/app）が入っています。開発用の設定が読まれていないか確認してください"
fi

# ── 4. ビルド・起動 ───────────────────────────────────────────────────────
# GIT_COMMIT は docker-compose.yml の build.args 経由で Dockerfile に渡り、/health で返る
# 40文字のまま渡す（フロントの WORKERS_CI_COMMIT_SHA も40文字のため）
GIT_COMMIT="$(git rev-parse HEAD)"
export GIT_COMMIT

echo "▶ ビルド・起動（コミット ${GIT_COMMIT:0:7}）"
# --wait: healthcheck が通るまで待つ。通らなければここで失敗して止まる
docker compose up -d --build --wait backend celery_worker

# ── 5. マイグレーション ───────────────────────────────────────────────────
echo "▶ alembic upgrade head"
docker compose exec -T backend alembic upgrade head

# ── 6. /health のコミットIDを確認 ─────────────────────────────────────────
# 本番はホストにポートを出していないので、コンテナの中から呼ぶ
running_commit="$(docker compose exec -T backend python -c \
  "import json, urllib.request; print(json.load(urllib.request.urlopen('http://localhost:8000/health'))['commit'])")"

[[ "$running_commit" == "$GIT_COMMIT" ]] \
  || fail "/health のコミットID（${running_commit}）が、pull したコミット（${GIT_COMMIT}）と一致しません"

echo "✔ 更新しました: backend は ${GIT_COMMIT:0:7} で動いています"
echo "  フロントの警告の帯が消えているか、画面でも確認してください"

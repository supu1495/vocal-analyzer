#!/usr/bin/env bash
# 本番の backend / celery_worker を main の最新に更新する
# 本番用フォルダ（~/works/vocal-analyzer-prod）で実行する: scripts/deploy_backend.sh
#
# 流れ: 安全確認 → git pull → ビルド → マイグレーション → 分析中でないか確認 → 作り直し → /health のコミットIDを確認
# 作り直すまでは古いコンテナが動き続けるので、途中で止まっても本番は古いまま動いている
# 手順の背景・失敗したときの戻し方は docs/DEPLOY.md
set -euo pipefail

# どこから実行しても、リポジトリの一番上で動かす
cd "$(dirname "$0")/.."

fail() {
  echo "中止: $*" >&2
  exit 1
}

# y を入力したときだけ続ける。対話できない実行（パイプ・cron など）では止める
confirm_or_fail() {
  [[ -t 0 ]] || fail "$1（対話できないため止めました）"
  local answer
  read -r -p "$1 続けますか？ [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || fail "止めました"
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
echo "  更新前のコミット: $(git rev-parse HEAD)（失敗して戻すときはこれを使う。docs/DEPLOY.md「失敗したとき」）"
git pull --ff-only

# ── 3. 最終確認: 実際に読まれる設定に、コードの mount がないか ──────────
# --no-interpolate: .env の値を埋め込まずに出す（秘密を扱わないため）。出力は画面に出さない
if docker compose config --no-interpolate | grep -q 'target: /app$'; then
  fail "backend / celery_worker にコードの mount（/app）が入っています。開発用の設定が読まれていないか確認してください"
fi

# ── 4. ビルド ─────────────────────────────────────────────────────────────
# イメージを作るだけ。動いているコンテナはまだ古いまま
# GIT_COMMIT は docker-compose.yml の build.args 経由で Dockerfile に渡り、/health で返る
# 40文字のまま渡す（フロントの WORKERS_CI_COMMIT_SHA も40文字のため）
GIT_COMMIT="$(git rev-parse HEAD)"
export GIT_COMMIT

echo "▶ ビルド（コミット ${GIT_COMMIT:0:7}）"
docker compose build backend celery_worker

# ── 5. マイグレーション ───────────────────────────────────────────────────
# 新しいイメージで一回きりのコンテナを作って実行する（--rm: 終わったら消す）
# exec は使わない。動いている古いコンテナには、新しいマイグレーションのファイルが入っていないため
# このあと作り直すまでは「古いコードが新しい DB で動く」。マイグレーションは列・テーブルの追加だけにすること
echo "▶ alembic upgrade head"
docker compose run --rm -T backend alembic upgrade head

# ── 6. 分析中でないか ─────────────────────────────────────────────────────
# 作り直すと worker は10秒で強制終了され、実行中の分析は中断して一時ファイルが残る（#55）
# 待ち行列のタスクは Redis に残り、新しい worker が引き継ぐので、見るのは「実行中」だけ
# 確認から作り直しまでの隙間を短くするため、ビルドとマイグレーションの後のここで確認する
# backend コンテナから問い合わせる（worker のコンテナが止まっていても、確認を試せるように）
echo "▶ 分析中でないか確認"
active_count_script='
from celery_app import celery_app
replies = celery_app.control.inspect(timeout=5).active()
if replies is None:  # 応答した worker が1つもない
    raise SystemExit(2)
print(sum(len(tasks) for tasks in replies.values()))
'
if active_count="$(docker compose exec -T backend python -c "$active_count_script" 2>/dev/null)"; then
  [[ "$active_count" == "0" ]] \
    || fail "分析が ${active_count} 件実行中です。終わってからもう一度実行してください（ビルドとマイグレーションは済んでいるので、次はすぐ終わります）"
else
  confirm_or_fail "worker が応答しないため、分析中かどうかを確認できません。作り直すと実行中の分析は中断されます。"
fi

# ── 7. 作り直し ───────────────────────────────────────────────────────────
# --wait: healthcheck が通るまで待つ。通らなければここで失敗して止まる（戻し方は docs/DEPLOY.md）
echo "▶ 作り直し"
docker compose up -d --wait backend celery_worker

# ── 8. /health のコミットIDを確認 ─────────────────────────────────────────
# 本番はホストにポートを出していないので、コンテナの中から呼ぶ
running_commit="$(docker compose exec -T backend python -c \
  "import json, urllib.request; print(json.load(urllib.request.urlopen('http://localhost:8000/health'))['commit'])")"

[[ "$running_commit" == "$GIT_COMMIT" ]] \
  || fail "/health のコミットID（${running_commit}）が、pull したコミット（${GIT_COMMIT}）と一致しません"

echo "✔ 更新しました: backend は ${GIT_COMMIT:0:7} で動いています"
echo "  フロントの警告の帯が消えているか、画面でも確認してください"

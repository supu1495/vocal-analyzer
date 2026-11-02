# デプロイ・運用手順

backend の更新手順、本番と開発の分け方、運用コマンドをまとめる（issue #31）。

## 構成

| | 場所 | 更新のしかた |
|---|---|---|
| フロント | `https://vocal-analyzer.supu361.dev`（Cloudflare） | main に push すると Cloudflare が自動でビルド・配信する |
| API | `https://vocal-api.supu361.dev` → CF Tunnel → 自宅 PC の `http://backend:8000` | **手動**。本番用フォルダで `scripts/deploy_backend.sh` |
| ローカル開発 | `http://localhost:5173`（Vite の proxy で `/api/*` を backend へ転送） | 保存すると反映（backend は `--reload`） |

フロントは自動、backend は手動で更新するので、片方だけ新しくなることがある。そのときは画面の一番上に
「フロントと API のバージョンが違います」という黄色い帯が出る（`frontend/src/components/VersionWarning.tsx`）。
フロントはビルド元のコミットID（`WORKERS_CI_COMMIT_SHA`）を、backend は `/health` の `commit` を持っていて、40文字のまま比べる。

### 本番用フォルダと開発フォルダ

デスクトップでは、本番と開発を**別のフォルダ**から同時に動かす。

| | 本番用フォルダ | 開発フォルダ |
|---|---|---|
| 場所 | デスクトップの `~/works/vocal-analyzer-prod` | デスクトップの `~/works/vocal-analyzer`、ノートPC |
| ブランチ | main だけ。pull 以外の git 操作をしない | 自由 |
| 読む compose | `docker-compose.yml` だけ | `docker-compose.yml` + `docker-compose.dev.yml` |
| backend のコード | イメージに焼き込んだもの（保存しても変わらない） | `./backend` を mount（保存すると変わる） |
| ポート公開 | なし（cloudflared がコンテナ間でつなぐ） | 127.0.0.1 の 8080 / 5173 / 80 / 5432 |
| frontend / nginx | なし（画面は Cloudflare から配る） | あり |
| cloudflared | あり | なし |
| `/health` の commit | 40文字のコミットID | `dev` |

`.env` は次の3項目を書き分ける（説明は `.env.example`）。

| | 本番用フォルダ | 開発フォルダ |
|---|---|---|
| `COMPOSE_PROFILES` | `prod` | 空 |
| `COMPOSE_FILE` | 空 | `docker-compose.yml:docker-compose.dev.yml` |
| `COMPOSE_PROJECT_NAME` | `vocal-analyzer` | `vocal-dev` |

- `COMPOSE_PROJECT_NAME` はコンテナ名・volume 名の頭に付く。同じ PC で両方を動かすので、必ず別の名前にする
- **本番の名前（`vocal-analyzer`）は変えない。** 変えると DB の volume（`vocal-analyzer_postgres_data`）が別物になり、空の DB で起動する
- 秘密（`SECRET_KEY` など）は本番と開発で別の値にする

`.env` の設定は、値を出さずに次で確かめる。

```bash
docker compose config --no-interpolate | head -1   # name: vocal-analyzer（本番）/ name: vocal-dev（開発）
docker compose config --services                   # 動くサービスの一覧
```

## backend の更新（毎回）

1. GitHub で PR をマージする。Cloudflare がフロントをビルドすると、画面に黄色い帯が出る（backend がまだ古いため）
2. 本番用フォルダでスクリプトを実行する

   ```bash
   cd ~/works/vocal-analyzer-prod
   scripts/deploy_backend.sh
   ```

3. 最後に `✔ 更新しました` と出たら、画面を再読み込みして**帯が消えたか**確認する

スクリプトは次の順に進み、問題があればその場で止まる。

| 順 | 内容 | 止まる条件 |
|---|---|---|
| 1 | 本番用フォルダかどうか | `.env` がない／プロジェクト名が `vocal-analyzer` でない／`COMPOSE_FILE` に dev が入っている／`docker-compose.override.yml` がある |
| 2 | git | main でない／未コミットの変更がある。問題なければ更新前のコミットを表示して `git pull --ff-only` |
| 3 | compose の最終確認 | backend などにコードの mount（`/app`）が入っている |
| 4 | ビルド | ビルドの失敗。`GIT_COMMIT`（40文字）をイメージに焼き込む |
| 5 | マイグレーション | `alembic upgrade head` の失敗。新しいイメージの一回きりのコンテナ（`docker compose run --rm`）で実行する |
| 6 | 分析中でないか | 分析が実行中。worker が応答しないときは「続けますか？」と聞く |
| 7 | 作り直し | healthcheck が通らない（`up --wait`） |
| 8 | `/health` の確認 | commit が pull したコミットと違う |

**6 までは古いコンテナが動き続けている。** 1〜6 で止まった場合、本番は古いコードのまま正常に動いている。

### 分析中でないかの確認

作り直すと、worker は10秒待ったあと強制終了される（`docker stop` の既定）。実行中の分析は中断され、
アップロードされた一時ファイルが残る（#55）。待ち行列にあるだけの分析は Redis に残り、新しい worker が引き継ぐ。

- スクリプトは**作り直しの直前**（ビルドとマイグレーションの後）に確認する。ビルドは時間がかかるので、最初に確認すると、作り直すまでのあいだに新しい分析が始まりやすい
- それでも確認から作り直しまでに数秒の隙間はある。利用者が少ない時間に実行する
- 分析が実行中で止まったときは、終わるのを待って再実行する。ビルドはキャッシュが効き、マイグレーションも済んでいるので、2回目はすぐ終わる
- worker が応答しない（固まっている・止まっている）ときは「続けますか？」と聞く。worker を直すための更新ができなくならないようにするため
- 手で確かめるときは本番用フォルダで次を実行する（`- empty -` なら分析中ではない）

  ```bash
  docker compose exec celery_worker celery -A celery_app inspect active
  ```

### マイグレーションのルール：追加だけにする

スクリプトは「マイグレーション → 作り直し」の順に進むので、そのあいだ**古いコードが新しい DB で動く**。

- 列・テーブルの**追加**は問題ない。古いコードは知らない列を無視する。NOT NULL の列を足すときは、既定値（`server_default`）を付ける
- 列・テーブルの**削除・名前の変更**は、2回のリリースに分ける。1回目で新しいコードがその列を使わないようにし、2回目のリリースで消す
- 逆の順（作り直し → マイグレーション）にしない理由：
  - 新しいコードが古い DB で動く時間ができ、新しい列を使う API が 500 になる
  - マイグレーションが失敗すると、新しいコードが古い DB のまま残る
- マイグレーションは1つのトランザクションで実行される（`backend/alembic/env.py`）。PostgreSQL ではテーブル定義の変更も取り消せるので、途中で失敗しても DB は元に戻る

## 失敗したとき

### 1〜6 で止まった（本番は古いまま動いている）

表示された理由を直して、もう一度 `scripts/deploy_backend.sh` を実行する。

- コードの問題（ビルド・マイグレーションの失敗）なら、開発フォルダで直す → PR → マージ → 再実行
- 2 の pull だけが済んで止まった場合も、そのまま再実行してよい（pull は何もせずに進む）

### 7・8 で止まった、または更新後に不具合が見つかった：ひとつ前のコミットに戻す

スクリプトが表示した「更新前のコミット」を使う（見失ったら `git reflog` で pull の前の行を探す）。

```bash
cd ~/works/vocal-analyzer-prod
docker compose logs backend --tail=50          # まず原因を見る
docker compose logs celery_worker --tail=50

git switch --detach <更新前のコミット>          # 本番用フォルダを、更新前のコードにする
GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build --wait backend celery_worker
docker compose exec -T backend python -c "import json, urllib.request; print(json.load(urllib.request.urlopen('http://localhost:8000/health'))['commit'])"
# ↑ 更新前のコミットIDが出れば戻っている。画面には帯が出る（フロントは新しいまま）
```

- 戻している間、本番用フォルダは main ではない（detached）ので、`scripts/deploy_backend.sh` は止まる
- 直したコードが main にマージされたら、`git switch main` してからスクリプトを実行する
- **DB は普通は戻さない。** マイグレーションが追加だけなら、古いコードは新しい DB でも動く
- どうしても DB を戻すときは、`git switch --detach` の**前に**、新しいイメージで実行する。古いイメージには、戻す対象のマイグレーションファイルが入っていないため

  ```bash
  docker compose run --rm -T backend alembic downgrade <戻したい revision>   # 先に実行
  ```

- フロントも戻したいときは、Cloudflare のダッシュボードで以前のデプロイに戻す（要確認：手順はまだ試していない）

## 移行（issue #31 のマージ後に1回だけ）

#31 で compose の構成が変わった。マージ後、次の順に移行する。

### 1. 本番用フォルダ（デスクトップ）

初回は本番用フォルダにスクリプトがまだないので、先に手で pull する。

```bash
cd ~/works/vocal-analyzer-prod
git pull --ff-only

# cloudflared が本番の設定に含まれているか（含まれていなければ .env の COMPOSE_PROFILES=prod を確認）
docker compose config --services

scripts/deploy_backend.sh
```

移行前の本番は、frontend / nginx のコンテナも動かしていた。新しい `docker-compose.yml` には定義がないので、名前を指定して片付ける。

```bash
docker ps -a --filter label=com.docker.compose.project=vocal-analyzer --format '{{.Names}}'   # 名前を確認
docker rm -f vocal-analyzer-frontend-1 vocal-analyzer-nginx-1
```

- `docker compose up --remove-orphans` は使わない。`COMPOSE_PROFILES` が読まれていない状態で実行したとき、cloudflared まで消えないかがわからないため（要確認）
- 最後に、画面の帯が消えたことを確認する（#31 の完了条件）

### 2. 開発フォルダ（デスクトップの `~/works/vocal-analyzer`）

**本番用フォルダの移行が済んでから行う。** 移行前の開発フォルダの `.env` はプロジェクト名が `vocal-analyzer` のままなので、ここで `docker compose up` / `down` を実行すると本番のコンテナを操作してしまう。

`.env` を次のように書き換える（値を画面に出さないため、エディタで開くか sed を使う）。

1. `COMPOSE_PROFILES=` を空にする（`prod` のままだと、開発環境の cloudflared が本番と同じトンネルにつながる）
2. `TUNNEL_TOKEN=` を空にする
3. `COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml` と `COMPOSE_PROJECT_NAME=vocal-dev` を書く
4. 秘密を本番と別の値に作り直す（開発の DB は新しく作るので、`POSTGRES_PASSWORD` も変えてよい）

   ```bash
   cd ~/works/vocal-analyzer
   for key in SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD INVITE_CODE; do
     sed -i "s/^${key}=.*/$(python3 scripts/gen_secrets.py ${key})/" .env
   done
   ```

書き換えたら、プロジェクト名とサービスを確かめてから起動する。

```bash
docker compose config --no-interpolate | head -1   # name: vocal-dev になっていること
docker compose config --services                   # frontend・nginx があり、cloudflared がないこと
docker compose up -d --build
docker compose exec backend alembic upgrade head   # 新しい DB は空なので、テーブルを作る
docker compose exec backend python seed.py         # テストユーザーとサンプル分析を入れる
curl http://localhost:8080/health                  # {"status":"ok","commit":"dev"}
```

### 3. ノートPC

ノートPCは本番を動かしていないので、プロジェクト名をそのまま使っても本番とはぶつからない。
ただ、デスクトップの開発フォルダと手順をそろえるため `vocal-dev` にする。

1. 今のコンテナを、今のプロジェクト名のまま止める（`.env` を書き換える前に行う）

   ```bash
   docker compose ls                                  # 今のプロジェクト名を確認
   docker compose -p <今のプロジェクト名> down --remove-orphans
   ```

2. `.env` に次の2行を足す（`COMPOSE_PROFILES` は空のまま）

   ```
   COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml
   COMPOSE_PROJECT_NAME=vocal-dev
   ```

3. デスクトップの開発フォルダと同じく、`config` で確かめて起動し、`alembic upgrade head` と `seed.py` を実行する

- プロジェクト名が変わると、DB は新しい空の volume になる。ノートPCの今の DB のデータを使い続けたいときは、`COMPOSE_PROJECT_NAME` に今のプロジェクト名を書く
- 古い volume は残っている。いらなければ `docker volume ls` で名前を確かめて `docker volume rm` する

## コマンド早見表

**どちらのフォルダで実行するか**に注意する。本番用フォルダで状態を変えるのは、原則 `scripts/deploy_backend.sh` だけにする。

### 起動・確認

```bash
# 開発フォルダ
docker compose up -d                     # 全サービス起動（frontend / nginx も）
docker compose restart celery_worker     # worker のコード変更を反映（backend は保存で自動反映）
docker compose up -d --build backend     # requirements.txt や Dockerfile を変えたとき
docker compose logs backend --tail=30
docker compose logs celery_worker -f
curl http://localhost:8080/health

# 本番用フォルダ（ホストにポートを出していないので curl は外の URL に）
docker compose ps
docker compose logs backend --tail=30
docker compose logs celery_worker -f
docker compose logs cloudflared --tail=30
curl https://vocal-api.supu361.dev/health
docker compose up -d cloudflared         # トンネルだけ起動し直す（以前の nohup cloudflared tunnel run の代わり）
```

### DB 操作

```bash
# 開発・本番とも、そのフォルダで実行する（-U / -d は .env の POSTGRES_USER / POSTGRES_DB）
docker compose exec db psql -U postgres -d vocal_analyzer
docker compose exec db psql -U postgres -d vocal_analyzer -c "\dt"
docker compose exec db psql -U postgres -d vocal_analyzer -c "SELECT id, email, created_at FROM users;"

# マイグレーション：開発フォルダでは exec でよい。本番は scripts/deploy_backend.sh が行う
docker compose exec backend alembic upgrade head
```

### DB 完全初期化（データが消える。開発フォルダだけ）

```bash
# 開発フォルダ。.env の COMPOSE_PROJECT_NAME が vocal-dev であることを先に確かめる
docker compose config --no-interpolate | head -1   # name: vocal-dev
docker compose down
docker volume rm vocal-dev_postgres_data
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
```

本番の `vocal-analyzer_postgres_data` は消さない。

### テスト（開発フォルダ）

```bash
docker compose exec backend python -m pytest -v
```

### デバッグ

```bash
docker compose exec celery_worker celery -A celery_app inspect active   # 実行中の分析
docker compose exec redis redis-cli keys "lockout:*"                     # ログイン制限中のメール
docker compose exec redis redis-cli keys "login_fail:*"                  # ログイン失敗の回数
docker compose exec celery_worker ls -la /tmp/vocal_analyzer/            # 残っている一時ファイル（#55）
```

`redis-cli` のパスワードは、コンテナの環境変数 `REDISCLI_AUTH` から読まれる（`-a` で渡さない）。

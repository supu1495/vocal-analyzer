# CLAUDE.md - 引き継ぎドキュメント

## プロジェクト概要
カラオケ音声分析システム。ユーザーがカラオケで録音した音声をAIで分析し、歌唱力向上のフィードバックを提供するWebアプリ。

---
## Claude Codeへの指示
・わからないことは「わからない」と言ってください
・推測と確実な情報は区別して答えてください
・情報源がある場合は明示してください
・間違っていたら指摘するので、その場合は素直に訂正してください
・存在しないAPIやライブラリを使わないでください
・不確かなコードには「要確認」とコメントを入れてください
・一度に大量のコードを書かず、ステップで確認しながら進めてください
・エラーが出た場合は原因を推測ではなく調査ベースで答えてください****

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | TypeScript + React + Vite |
| バックエンド | Python 3.11 + FastAPI |
| 音源分離 | Demucs v4（現在スタブ） |
| ピッチ検出 | Crepe + TensorFlow |
| 音響特徴 | librosa |
| DB | PostgreSQL 15 |
| キャッシュ | Redis 7 |
| インフラ | Docker + Docker Compose + Nginx |

---

## ポート構成

| サービス | ポート |
|---|---|
| Nginx | 80（外部公開） |
| Backend | 8080:8000 |
| Frontend | 5173:5173 |
| PostgreSQL | 5432 |
| Redis | 6379 |

---

## 完了済みフェーズ

### Phase 1: Docker環境構築 ✅
- 5サービス（frontend / backend / db / redis / nginx）起動確認済み

### Phase 2: 音声分析エンジン ✅
- Crepeによるピッチ検出
- librosaによる音響特徴抽出
- 歌唱技法検出（ビブラート・こぶし・フォール・しゃくり・ロングトーン）
- `POST /api/v1/analysis/upload` で 200 OK 確認済み

### Phase 3: フロントエンド3画面実装 ✅
- アップロード画面・分析結果画面・統計ダッシュボード画面

### Phase 4: DB連携 ✅
- `backend/database.py`: SQLAlchemy接続設定・`get_db()` DI関数
- `backend/models.py`: `users` / `analysis_results` テーブル定義
- `backend/alembic/`: マイグレーション設定・初回マイグレーション実行済み
- `backend/api/analysis.py`: `analysis_store` dict → PostgreSQL保存に変更
- `GET /api/v1/analysis/user/statistics` エンドポイント実装
- フロントエンド: ダッシュボードのダミーデータ → 実API接続に変更

### Phase 5: 認証（Authentication）✅
- `backend/auth_utils.py`: JWT生成・検証、パスワードハッシュ化、Redisロックアウト
- `backend/api/auth.py`: register / login / me / logout エンドポイント
- JWT保存方式: httpOnly Cookie（XSS対策）
- ログイン失敗ロックアウト: 5回失敗で15分ロック（Redis）
- `backend/api/analysis.py`: `upload_audio` を認証必須に変更
- Alembicマイグレーション: `users` テーブルに `hashed_password` カラム追加
- フロントエンド: ログイン・登録画面追加、全APIに `credentials: 'include'` 付与

---

## 現在の状態

- **作業ブランチ**: `main`
- **mainブランチ**: Phase 5まで全てマージ済み

---

## 決定済みの仕様・注意事項

**著作権保護:** 録音音声ファイルは保存しない。分析結果のみPostgreSQLに保存。

**Demucsのスタブ化（一時的）:** CPUでの処理が遅すぎるため、Celery非同期処理実装後に本番復帰予定。現在は `backend/audio/separator.py` がlibrosで音声をそのままボーカルとして返すスタブ実装。

**Crepe採用:** 精度重視のためlibrosa.pyinへの変更はしない。

**コードの書き方:** リーダブルコードの考えに準拠する。

**Dockerfileの特殊対応:**
```dockerfile
RUN pip install --no-cache-dir --no-deps crepe==0.0.13 && \
    pip install --no-cache-dir -r requirements.txt
```
crepeを `--no-deps` でインストールしてhmmlearnのpybind11競合を回避。

**ファイルの一時保存:** アップロードされたファイルの拡張子をそのまま保持（`.m4a`等）してlibrosで読み込む。

**user_idのNullable:** Phase 5で認証を実装済み。`NOT NULL` への変更は Phase 6以降にAlembicマイグレーションで対応予定。

**声紋データ（voiceprint_data）:** 分析精度向上のため重要な機能として `users` テーブルに保持。認証実装後に声紋生成・比較機能を追加予定。

---

## 次にやるべきこと

### Phase 6: テスト

- バックエンドユニットテスト（pytest）
  - `auth_utils.py` のJWT・パスワード関数
  - 各APIエンドポイントのAPIテスト
- フロントエンドテスト（任意）

### Phase 7以降

| フェーズ | 内容 |
|---|---|
| Phase 7 | 非同期処理（Celery + RedisでDemucs本番復帰） |

---

## ファイル構成（重要ファイル）

```
vocal-analyzer/
├── docker-compose.yml
├── nginx/default.conf
├── backend/
│   ├── main.py                      # FastAPIアプリ本体
│   ├── database.py                  # SQLAlchemy接続・get_db()
│   ├── models.py                    # DBモデル（User / AnalysisResult）
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/                # マイグレーションファイル
│   ├── auth_utils.py                # JWT・パスワード・ロックアウトユーティリティ
│   ├── api/
│   │   ├── auth.py                  # 認証APIエンドポイント
│   │   └── analysis.py              # 分析APIエンドポイント
│   └── audio/
│       ├── analyzer.py              # 分析司令塔
│       ├── separator.py             # 音源分離（現在スタブ）
│       ├── pitch.py                 # Crepeピッチ検出
│       └── techniques.py            # 歌唱技法検出
└── frontend/
    └── src/
        └── App.tsx                  # 全画面のReactコンポーネント
```
---
## 決定事項ログ
### 2026-03-25 認証レビュー
- JWT保存: localStorage → httpOnly Cookie に変更予定（未対応）
- シークレットキー: デフォルト値を削除済み
- ロックアウト: 次タスクで実装予定
- エラーメッセージ: 合格、変更なし
- JWT有効期限: ブラックリスト対応は次フェーズ

### 2026-03-25 コード総ざらいレビュー

#### 完了済み
- JWT: httpOnly Cookie方式に変更済み
- シークレットキー: docker-compose.ymlで${SECRET_KEY}参照に変更済み
- ロックアウト: Redis実装済み（5回失敗→15分ロック）
- ログアウトエンドポイント: POST /api/v1/auth/logout 追加済み
- エラーメッセージ: 曖昧化済み（ユーザー列挙攻撃対策）

#### 未対応・要修正
- main.py: auth routerの登録が抜けている（最優先）
- App.tsx: ログイン・登録画面が未反映（feature/AuthNの変更がmainに入っていない可能性）
- analysis.py: get_current_userによるログイン必須化が未反映
- Alembic: hashed_passwordカラム追加マイグレーション未実行
- models.py: hashed_passwordフィールドがない

#### 次にやること
1. main.pyにauth routerを登録
2. App.tsxのログイン画面をfeature/AuthNから確認・反映
3. Alembicマイグレーション実行

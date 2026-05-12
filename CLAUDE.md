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
・エラーが出た場合は原因を推測ではなく調査ベースで答えてください

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
- 歌唱技法検出（ビブラート・こぶし・フォール・しゃくり・ロングトーン）※検出ロジック未実装（スタブ）、Phase 7で本実装予定
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

### Phase 6: テスト ✅
- `backend/tests/conftest.py`: SQLiteインメモリDB・fakeredis・TestClient の共通フィクスチャ
- `backend/tests/test_auth_utils.py`: JWT・パスワード・ロックアウトのユニットテスト
- `backend/tests/test_api_auth.py`: 認証APIエンドポイントのテスト（register / login / me / logout）
- `backend/tests/test_api_analysis.py`: 分析APIエンドポイントのテスト（upload / get / statistics）
- 34テスト全pass確認済み

---

## 現在の状態

- **作業ブランチ**: `main`
- **mainブランチ**: Phase 6まで全てマージ済み
- **ローカル動作確認**: Docker Compose で全5サービス起動確認済み（2026-03-26）
- **注意**: port 80 はホスト側の Apache が競合する場合あり。その場合は `http://localhost:5173` に直接アクセス

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

### Phase 7以降

| フェーズ | 内容 |
|---|---|
| Phase 7 | 歌唱技法検出・リズム評価・声域計算・スコアマトリクス・ルールベースフィードバック生成 |
| Phase 8 | 非同期処理（Celery + RedisでDemucs本番復帰） |

### 技術的負債・将来対応

- **本番環境の接続情報管理**: `.env.example` の `DATABASE_URL` / `REDIS_URL` は開発用のデフォルト値がそのまま書かれている。本番デプロイ時には環境変数またはAWS Secrets Managerなどのシークレット管理ツールで注入すること（`POSTGRES_PASSWORD` のハードコードも同様）
- **PC版UI実装**: 現状はスマートフォン向けレイアウト。PC向けレスポンシブ対応またはPC専用レイアウトを追加する
- **複数ファイル一括アップロード・日付指定機能**: 複数の音声ファイルを一度に投下する機能、および録音日時を手動で指定して登録する機能

---

## ファイル構成（重要ファイル）

```
vocal-analyzer/
├── docker-compose.yml
├── .env.example                         # 環境変数のテンプレート（実際の値は .env に書く）
├── .gitignore
├── nginx/default.conf                   # nginxリバースプロキシ設定
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
│   ├── audio/
│   │   ├── analyzer.py              # 分析司令塔
│   │   ├── separator.py             # 音源分離（現在スタブ）
│   │   ├── pitch.py                 # Crepeピッチ検出
│   │   └── techniques.py            # 歌唱技法検出
│   └── tests/
│       ├── conftest.py              # テスト共通フィクスチャ（SQLite・fakeredis・TestClient）
│       ├── test_auth_utils.py       # auth_utils.py ユニットテスト
│       ├── test_api_auth.py         # 認証APIテスト
│       └── test_api_analysis.py     # 分析APIテスト
└── frontend/
    └── src/
        └── App.tsx                  # 全画面のReactコンポーネント
```
---
## ログ

### 2026-03-25 認証レビュー → 全対応済み（2026-03-26）
- JWT保存: localStorage → httpOnly Cookie に変更済み
- シークレットキー: `docker-compose.yml` で `${SECRET_KEY}` 参照に変更済み
- ロックアウト: Redis実装済み（5回失敗→15分ロック）
- ログアウトエンドポイント: `POST /api/v1/auth/logout` 実装済み
- エラーメッセージ: 曖昧化済み（ユーザー列挙攻撃対策）
- JWT有効期限: ブラックリスト対応は次フェーズ
- `feature/AuthN` → `main` マージ済み

### 2026-03-26 起動時バグ修正
- `requirements.txt`: `pydantic==2.5.3` → `pydantic[email]==2.5.3`
  - `EmailStr` 使用時に `email-validator` が必要なため

### 2026-04-12 コードレビュー修正
- `backend/api/analysis.py`: ループ変数 `r` → `record` に変更
  - リーダブルコードの観点から、何を表しているか明確な名前に統一
- `CLAUDE.md`: Phase 2 の歌唱技法検出に「※検出ロジック未実装（スタブ）、Phase 7で本実装予定」を追記
  - `backend/audio/techniques.py` の全メソッドがTODOスタブのため実態と合わせた

### 2026-04-17 コードレビュー修正
- `backend/audio/techniques.py`: `detect_vibrato` の返り値に `gratuitous_count` フィールドを追加
  - 間奏など旋律のない区間（ピッチ変化がほぼゼロの無声区間）で発生したビブラートをカウントするフィールド
  - 歌唱中のビブラートはアレンジとして加点。旋律のない区間でのビブラートのみ減点対象とする設計方針をTODOコメントに明記

### 2026-05-08 コードレビュー修正
- `frontend/src/App.tsx`: `handleResult` の引数 `r` → `result` に変更
  - リーダブルコードの観点から、何を表しているか明確な名前に統一（`backend/api/analysis.py` の `r` → `record` と同じ方針）

### 2026-05-09 コードレビュー修正
- `frontend/index.html`: `<title>frontend</title>` → `<title>Vocal Analyzer</title>` に変更
  - Viteの初期値のままだったため、プロジェクト名に合わせた
- `frontend/README.md`: 削除
  - `npm create vite` 時に自動生成されたViteデフォルトのREADMEで、プロジェクト固有の内容がなかったため

### 2026-05-09 コードレビュー方針追記・バグ修正
- `SPEC.md` / `CLAUDE.md`: 本番環境の接続情報管理に関する注記を追加
  - `.env.example` の `DATABASE_URL` / `REDIS_URL` は開発用デフォルト値がそのまま記載されているため、本番デプロイ時には環境変数またはシークレット管理ツールで注入すること
  - `docker-compose.yml` の `POSTGRES_PASSWORD` ハードコードも同様に本番では別途管理が必要な旨を明記
- `README.md`: セットアップのURLを修正
  - `http://localhost:8000` → `http://localhost:8080`（docker-compose.ymlのポートマッピングが `8080:8000` のため）

### 2026-05-09 python-jose → PyJWT 移行（CVE-2024-33663対応）
- `backend/requirements.txt`: `python-jose[cryptography]==3.3.0` → `PyJWT==2.12.1`
  - CVE-2024-33663（ECDSA署名検証の脆弱性）が報告されており、メンテナンスが活発なPyJWTへ切り替え
- `backend/auth_utils.py`: `from jose import JWTError, jwt` → `import jwt` / `JWTError` → `jwt.InvalidTokenError`
- `SPEC.md`: 既知の問題リストを更新（Phase 5.5で解決済みの3項目を解決済みセクションへ移動）
- `SPEC.md`: Phase 6 テスト計画を詳細化（認証・認可・入力バリデーション・正常系の主要フローを網羅）

### 2026-05-12 Phase 6 テスト実装・passlib → bcrypt 移行
- `backend/tests/`: pytest テスト一式を新規追加（34テスト全pass確認）
  - `conftest.py`: SQLiteインメモリDB（StaticPool）・fakeredis・TestClient の共通フィクスチャ
  - `test_auth_utils.py`: JWT・パスワード・ロックアウトのユニットテスト（13テスト）
  - `test_api_auth.py`: 認証APIテスト・register / login / me / logout（12テスト）
  - `test_api_analysis.py`: 分析APIテスト・upload / get / statistics（9テスト）
- `backend/requirements.txt`: テスト用パッケージ追加（`pytest==8.3.5` / `httpx==0.27.0` / `fakeredis==2.26.2`）
- `backend/tests/conftest.py`: `StaticPool` 追加
  - SQLiteインメモリDBは接続ごとに別DBが作られるため、`create_all` で作ったテーブルが別接続から見えず "no such table" になる問題を修正
  - `StaticPool` で全接続が同一SQLite接続を共有するよう変更
- `backend/requirements.txt`: `passlib[bcrypt]==1.7.4` を削除
  - Python の標準ライブラリ `crypt` モジュールが Python 3.13 で削除されており、passlib がモジュールロード時にこれをインポートするため将来 ImportError が発生するリスクがある
  - passlib のメンテナンスが停滞しており自己修正が見込めないため bcrypt を直接使う形に移行
- `backend/auth_utils.py`: passlib → bcrypt 直接呼び出しに変更
  - `from passlib.context import CryptContext` / `pwd_context = CryptContext(...)` を削除
  - `hash_password`: `bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()`
  - `verify_password`: `bcrypt.checkpw(plain_password.encode(), hashed_password.encode())`
  - `DUMMY_HASH`: `bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()`

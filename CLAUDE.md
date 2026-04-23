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

---

## 現在の状態

- **作業ブランチ**: `main`
- **mainブランチ**: Phase 5まで全てマージ済み
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

### Phase 6: テスト

- バックエンドユニットテスト（pytest）
  - `auth_utils.py` のJWT・パスワード関数
  - 各APIエンドポイントのAPIテスト
- フロントエンドテスト（任意）

### Phase 7以降

| フェーズ | 内容 |
|---|---|
| Phase 7 | 非同期処理（Celery + RedisでDemucs本番復帰） |

### 技術的負債・将来対応

- **python-jose → PyJWT への切り替え**: `python-jose` にCVEが報告済み。コードレビュー完了後に `PyJWT` へ切り替える
- **PC版UI実装**: 現状はスマートフォン向けレイアウト。PC向けレスポンシブ対応またはPC専用レイアウトを追加する
- **複数ファイル一括アップロード・日付指定機能**: 複数の音声ファイルを一度に投下する機能、および録音日時を手動で指定して登録する機能

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

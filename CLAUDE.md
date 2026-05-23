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
| 音源分離 | Demucs v4 |
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

### Phase 7: 音声分析エンジン本実装 ✅
- `backend/audio/techniques.py`: 歌唱技法検出を全実装（ビブラート・こぶし・フォール・しゃくり・ロングトーン）
- `backend/audio/analyzer.py`: 声域計算・リズム評価・スコアマトリクス・ルールベースフィードバック生成を実装
- `backend/models.py` + Alembicマイグレーション: `analysis_results` に4カラム追加（`total_score` / `faithfulness_score` / `technique_score` / `naturalness_penalty`）
- 34テスト全pass確認済み

### Phase 8: 非同期処理（Celery）・Demucs本番実装 ✅
- `backend/celery_app.py`: Celeryアプリ設定（Broker: Redis DB0 / Backend: Redis DB1）
- `backend/tasks.py`: `analyze_audio_task` Celeryタスク（分析実行・DB保存・一時ファイル削除）
- `backend/audio/separator.py`: スタブ実装 → Demucs v4 による実装に変更
- `backend/api/analysis.py`: 同期分析 → タスク登録（`.delay()`）方式に変更。`GET /status/{task_id}` エンドポイント追加
- `backend/audio/analyzer.py`: `_calculate_rhythm_score` の死んだコード（else分岐）を削除
- `docker-compose.yml`: `celery_worker` サービス追加・`vocal_uploads` 共有ボリューム追加
- `backend/requirements.txt`: `celery==5.3.6` 追加
- `backend/tests/test_api_analysis.py`: モック対象を `analyze_audio_task.delay` に変更・ステータス確認テスト3件追加
- 37テスト全pass確認済み

### Phase 9: 本番環境デプロイ ✅
- **構成**: CF Pages（フロント）+ CF Tunnel（自宅PCへの橋渡し）+ Docker Compose（自宅PC）
- **ドメイン**: `vocal-analyzer.supu361.dev`（フロント）/ `vocal-api.supu361.dev`（API）
- `backend/main.py`: CORS 許可オリジンを `CORS_ALLOWED_ORIGINS` 環境変数化
- `frontend/.env.production`: `VITE_API_BASE_URL=https://vocal-api.supu361.dev` を本番ビルドに埋め込み
- `frontend/vite.config.ts`: ローカル開発用の proxy 設定（`/api/*` → `http://backend:8000`）
- `backend/api/auth.py`: クロスドメイン Cookie のため `samesite="none"` に変更
- `frontend/src/App.tsx`: 非同期分析のポーリング処理を実装（5秒間隔・最大120回 = 10分）
- `frontend/src/App.tsx`: ロックアウト 429 受信時にログインボタンを 15分無効化する UI
- `backend/audio/separator.py`: M4A→WAV 変換を ffmpeg で追加（torchaudio が M4A 非対応のため）
- `backend/tasks.py`: PyTorch fork デッドロック回避のため AudioAnalyzer を遅延初期化
- `backend/api/analysis.py`: アップロード時のサイズチェックをチャンクストリーミング化（DoS耐性）
- `backend/api/analysis.py`: `AsyncResult` に `celery_app` を明示渡し（DisabledBackend バグ修正）
- `backend/models.py` + マイグレーション: `analysis_results.user_id` を NOT NULL 化
- `backend/tasks.py`: 例外時に `db.rollback()` を呼ぶ
- `backend/Dockerfile`: `--reload` を本番デフォルトから削除（`docker-compose.override.yml` でローカルのみ復活）
- `docker-compose.yml`: PostgreSQL `ports` をローカル開発専用 override に移動
- `docker-compose.yml` + `.env.example`: `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` を環境変数化
- `backend/requirements.txt`: `scipy==1.10.1` 固定（librosa 0.10.1 が `scipy.signal.hann` を使用しており scipy 1.11 以降で削除されたため）

---

## 現在の状態

- **作業ブランチ**: `phase9`
- **mainブランチ**: Phase 8まで全てマージ済み。Phase 9 のマージは `phase9` ブランチで進行中
- **ローカル動作確認**: Docker Compose で全6サービス起動確認済み（2026-05-24）
- **本番動作確認**: CF Pages（`vocal-analyzer.supu361.dev`）+ CF Tunnel（`vocal-api.supu361.dev`）→ 自宅PC Docker Compose で動作確認済み
- **注意**: port 80 はホスト側の Apache が競合する場合あり。その場合は `http://localhost:5173` に直接アクセス（Viteの proxy 設定で `/api/*` は backend に転送される）

---

## 決定済みの仕様・注意事項

**著作権保護:** 録音音声ファイルは保存しない。分析結果のみPostgreSQLに保存。

**Demucs（Phase 8）:** `backend/audio/separator.py` は Demucs v4 で実装済み。モデルは `htdemucs`（標準）を使用。Celery Worker コンテナで非同期実行するため CPU 処理の遅さはユーザー体験に影響しない（`htdemucs_ft` は4倍重いアンサンブルモデルのためCPUでは非実用的。GPU 化のタイミングで切り替えを検討する。Phase 10以降で対応）。

**Crepe採用:** 精度重視のためlibrosa.pyinへの変更はしない。

**コードの書き方:** リーダブルコードの考えに準拠する。

**techniques.py のファイル分割:** 現状は1ファイル（技法ごとにメソッド分割）で維持する。アクセント・ハンマリングなど技法追加のタイミングでも分割しない。プロダクトが一通り完成した後のリファクタリングフェーズで検討する。

**Dockerfileの特殊対応:**
```dockerfile
RUN pip install --no-cache-dir --no-deps crepe==0.0.13 && \
    pip install --no-cache-dir -r requirements.txt
```
crepeを `--no-deps` でインストールしてhmmlearnのpybind11競合を回避。

**ファイルの一時保存:** アップロードされたファイルの拡張子をそのまま保持（`.m4a`等）してlibrosで読み込む。

**user_id NOT NULL（Phase 9完了）:** Phase 5で認証を実装済み。Phase 9のAlembicマイグレーション（`6b8b9af3d05e`）で `analysis_results.user_id` を NOT NULL に変更済み。

**声紋データ（voiceprint_data）:** 分析精度向上のため重要な機能として `users` テーブルに保持。認証実装後に声紋生成・比較機能を追加予定。

---

## 次にやるべきこと

### Phase 10以降

| フェーズ | 内容 |
|---|---|
| Phase 10 | 精度確認（実際のカラオケ録音を使った検出精度の検証）+ GPU化（RTX 4060 Ti を活用） + CF D1 への移行（PostgreSQL → SQLite） |
| Phase 11 | 時系列成長分析（録音日時の手動入力・スコア推移・練習継続率の可視化） |

**Phase 10 で予定している3つの大きな作業:**

1. **精度確認**: 実音声で技法検出・スコア計算の精度を検証し、必要なら閾値を調整する
2. **GPU化**: WSL2 + NVIDIA Container Toolkit + CUDA版 PyTorch を導入して RTX 4060 Ti を活用。`htdemucs_ft`（より高品質なDemucsモデル）への切り替えも検討
3. **CF D1 移行**: PostgreSQL（SQLAlchemy）から SQLite ベースの CF D1 への移行。アプリケーションコードの書き直しが必要

### 技術的負債・将来対応

- **CF D1 への部分移行（Phase 10予定）**: 現在は自宅PC + CF Tunnel 構成で動かしているが、Phase 10 で PostgreSQL（SQLAlchemy + Alembic）から CF D1（SQLite）への移行を計画中。CF Workers（API）/ CF R2（ファイル一時保存）への移行は FastAPI の書き直しが必要なため当面見送り
- **GPU 化（Phase 10予定）**: ホストマシンに RTX 4060 Ti 8GB を搭載しているが、現在の Docker 構成は CPU 版 PyTorch を使用しており GPU を活用できていない。Phase 10 で WSL2 + NVIDIA Container Toolkit + CUDA 版 PyTorch を導入予定
- **Cloudflare Tunnel のエグレスについて**: 分析結果（JSON）の返却はエグレスに該当するが、データ量がKB単位のテキストのため実質問題なし。CF Tunnelの無料プランには明示的な帯域制限の記載がなく、禁止されているのは「動画・音声ファイルの大量配信」であり今回の用途とは異なる
- **本番環境の接続情報管理**: Phase 9 で `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` を環境変数化済み。本格的な本番運用時には AWS Secrets Manager 等のシークレット管理ツールで注入する形に移行する
- **PC版UI実装**: 現状はスマートフォン向けレイアウト。PC向けレスポンシブ対応またはPC専用レイアウトを追加する
- **複数ファイル一括アップロード・日付指定機能**: 複数の音声ファイルを一度に投下する機能、および録音日時を手動で指定して登録する機能（後日まとめてアップロードしても正しい日時で記録できるようにする。Phase 11 の時系列成長分析と合わせて実装予定）
- **アクセント・ハンマリング検出**: DAM AI HEART を参考に追加予定の歌唱技法。Phase 7完了後に検討（詳細は SPEC.md「将来検討」参照）
- **分析進捗表示**: 解析中の残り時間・プログレスバーをUIに表示。Phase 8（Celery非同期）と連動して実装
- **score_matrix / vocal_range のフロントエンド表示**: backend は Phase 7 で `total_score` / `faithfulness_score` / `technique_score` / `naturalness_penalty` / `vocal_range` を計算・DB保存しているが、frontend は無視して `(pitch + rhythm) / 2` の単純平均で「総合評価」を表示している。Phase 10（精度確認）または Phase 11 でフロントを修正する
- **録音ガイドUI**: 音量・距離・ノイズを視覚的にチェックする機能。カラオケ機器の機種差による品質ばらつきを軽減する目的
- **話者分離・歌声検出のテスト発声**: 他の人の声の除去・歌声と話し声の判別。分析前のテスト発声で声のプロファイルを取得する（詳細は SPEC.md「将来検討」参照）

---

## ファイル構成（重要ファイル）

```
vocal-analyzer/
├── docker-compose.yml                   # 本番・開発共通の構成
├── docker-compose.override.yml          # ローカル開発専用の上書き（gitignore対象）
├── .env.example                         # 環境変数のテンプレート（実際の値は .env に書く）
├── .gitignore
├── nginx/default.conf                   # nginxリバースプロキシ設定
├── wrangler.jsonc                       # CF Pages のデプロイ設定
├── backend/
│   ├── main.py                      # FastAPIアプリ本体（CORS は環境変数から読み込み）
│   ├── database.py                  # SQLAlchemy接続・get_db()
│   ├── models.py                    # DBモデル（User / AnalysisResult）
│   ├── celery_app.py                # Celeryアプリ設定（Broker: Redis DB0 / Backend: Redis DB1）
│   ├── tasks.py                     # Celeryタスク（analyze_audio_task）
│   ├── Dockerfile                   # uvicorn を --reload なしで起動（override で復活）
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/                # マイグレーションファイル
│   ├── auth_utils.py                # JWT・パスワード・ロックアウトユーティリティ
│   ├── api/
│   │   ├── auth.py                  # 認証APIエンドポイント
│   │   └── analysis.py              # 分析APIエンドポイント（チャンクストリーミング書き込み）
│   ├── audio/
│   │   ├── analyzer.py              # 分析司令塔
│   │   ├── separator.py             # 音源分離（Demucs v4・M4A→WAV変換含む）
│   │   ├── pitch.py                 # Crepeピッチ検出
│   │   └── techniques.py            # 歌唱技法検出
│   └── tests/
│       ├── conftest.py              # テスト共通フィクスチャ（SQLite・fakeredis・TestClient）
│       ├── test_auth_utils.py       # auth_utils.py ユニットテスト
│       ├── test_api_auth.py         # 認証APIテスト
│       └── test_api_analysis.py     # 分析APIテスト
└── frontend/
    ├── .env.production              # 本番ビルドで埋め込む VITE_API_BASE_URL
    ├── vite.config.ts               # ローカル開発用の /api/* proxy 設定
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

### 2026-05-16 設計思想・将来機能の整理（SPEC.md / CLAUDE.md 更新）
- SPEC.md / CLAUDE.md: アクセント・ハンマリング検出を将来検討機能として追記（DAM AI HEART 参考）
- SPEC.md / CLAUDE.md: 分析進捗表示・録音ガイドUI・話者分離テスト発声を将来対応として追記
- SPEC.md: ハードウェア依存の説明をカラオケ機器の機種差として修正（キャリブレーションではなく録音ガイドUIが解決策）
- SPEC.md: 技法密度分析にバラードAメロのしゃくり連発→減点の具体例を追記
- SPEC.md: 話者分離の目的に「他の人の声を除く」を明記

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

### 2026-05-24 Phase 9: 本番デプロイ完了 + 既知のバグ修正一括対応
- `backend/main.py`: CORS を `CORS_ALLOWED_ORIGINS` 環境変数化（localhost:5173 + 本番ドメイン）
- `frontend/.env.production`: `VITE_API_BASE_URL=https://vocal-api.supu361.dev` 追加
- `frontend/vite.config.ts`: ローカル開発用の `/api/*` proxy 設定（`localhost:5173` 直アクセス時に Vite が API リクエストを 404 で返す問題を解消）
- `backend/api/auth.py`: クロスドメイン Cookie のため `samesite="none"`
- `backend/api/analysis.py`: ファイルサイズチェックを一括読み込みからチャンクストリーミングへ変更（DoS耐性向上）
- `backend/api/analysis.py`: `AsyncResult` に `celery_app` を明示渡し（DisabledBackend バグ修正）
- `backend/audio/separator.py`: torchaudio が M4A 非対応のため ffmpeg で WAV 変換する `_to_wav()` を追加
- `backend/tasks.py`: PyTorch fork デッドロック回避のため AudioAnalyzer を遅延初期化、例外時に `db.rollback()` 追加
- `backend/Dockerfile`: `--reload` を本番デフォルトから削除（`docker-compose.override.yml` でローカルのみ復活）
- `backend/models.py` + マイグレーション `6b8b9af3d05e`: `analysis_results.user_id` を NOT NULL に変更
- `docker-compose.yml`: PostgreSQL `ports` 公開を削除（override に移動）
- `docker-compose.yml` + `.env.example`: `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` を環境変数化（パスワード直書き解消）
- `backend/requirements.txt`: `scipy==1.10.1` 固定（librosa 0.10.1 が `scipy.signal.hann` を使用しており scipy 1.11 以降で削除されたため）
- `frontend/src/App.tsx`: ロックアウト 429 受信時にログインボタンを 15分無効化する UI、`analysis_id` 型修正（`string` → `number`）、未使用 `status` フィールド削除、ポーリング上限を 5分→10分（120回×5秒）に延長
- 本番動作確認: CF Pages（`vocal-analyzer.supu361.dev`）+ CF Tunnel（`vocal-api.supu361.dev`）でログイン・アップロード・分析完了まで動作確認済み

### 2026-05-18 Phase 8: 非同期処理（Celery）・Demucs本番実装
- `backend/celery_app.py`: 新規作成。Celeryアプリ設定（Broker: Redis DB0 / Backend: Redis DB1 / JSON シリアライザー）
- `backend/tasks.py`: 新規作成。`analyze_audio_task` Celeryタスク（分析・DB保存・一時ファイル削除）
- `backend/audio/separator.py`: librosa スタブ → Demucs v4（htdemucs）本番実装に変更
- `backend/api/analysis.py`: 同期分析処理を削除し `.delay()` によるタスク登録方式に変更
  - `upload_audio`: ファイルを共有ボリュームに書き込み → `analyze_audio_task.delay()` → `task_id` 返却
  - `GET /status/{task_id}` エンドポイント新規追加（`AsyncResult` でステータス確認）
- `backend/audio/analyzer.py`: `_calculate_rhythm_score` の else 分岐（死んだコード）を削除
  - Demucs 出力が常にステレオのため `mono = vocals.mean(axis=0)` のみに
- `docker-compose.yml`: `celery_worker` サービス追加・`vocal_uploads` 共有ボリューム追加
- `backend/requirements.txt`: `celery==5.3.6` 追加
- `backend/tests/test_api_analysis.py`: Phase 8 の API 変更に対応してテストを書き直し
  - モック対象: `audio_analyzer.analyze` → `analyze_audio_task.delay`
  - `_create_analysis_record()` ヘルパー追加（Worker なしでDB直接作成）
  - ステータス確認テスト3件追加（`test_get_analysis_status_*`）
  - 37テスト全pass確認済み（Phase 7: 34テスト → +3）

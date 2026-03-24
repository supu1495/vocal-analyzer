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

---

## 現在の状態

- **作業ブランチ**: `feature/AuthN`
- **mainブランチ**: Phase 4まで全てマージ済み

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

**user_idのNullable:** 認証未実装のため暫定的にNullable。認証実装後に `NOT NULL` へ変更するAlembicマイグレーションを追加する。

**声紋データ（voiceprint_data）:** 分析精度向上のため重要な機能として `users` テーブルに保持。認証実装後に声紋生成・比較機能を追加予定。

---

## 次にやるべきこと

### Phase 5: 認証（Authentication）- `feature/AuthN` ブランチで作業

**実装順序:**

1. **`backend/schemas.py` 作成**
   - Pydanticスキーマ定義（UserCreate / UserLogin / Token など）

2. **`backend/api/auth.py` 作成**
   - `POST /api/v1/auth/register` — ユーザー登録
   - `POST /api/v1/auth/login` — ログイン・JWTトークン発行
   - `GET /api/v1/auth/me` — ログイン中ユーザー情報取得

3. **`backend/auth.py` 作成**
   - パスワードハッシュ化（passlib / bcrypt）
   - JWT生成・検証（python-jose）
   - `get_current_user()` DI関数

4. **`backend/api/analysis.py` 修正**
   - `upload_audio` に `current_user: User = Depends(get_current_user)` を追加
   - `user_id` をログインユーザーのIDで保存するよう変更

5. **Alembicマイグレーション**
   - `users.id` にパスワードハッシュカラムを追加
   - `analysis_results.user_id` を `NOT NULL` に変更

6. **フロントエンド対応**
   - ログイン・登録画面の追加
   - JWTトークンをlocalStorageに保存
   - APIリクエストに `Authorization: Bearer <token>` ヘッダーを付与

---

### Phase 6以降（認証完了後）

| フェーズ | 内容 |
|---|---|
| Phase 6 | テスト（バックエンドユニットテスト・APIテスト） |
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
│   ├── api/
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

# vocal-analyzer

カラオケ録音をアップロードするだけで、AIがピッチ精度・歌唱技法・リズム感などを分析し、歌唱力向上のフィードバックを提供するWebアプリです。

> ⚠️ 現在開発中です

---

## 実装済みの機能

- **ユーザー認証** — メール・パスワードによる登録・ログイン（JWT / httpOnly Cookie）
- **ログイン保護** — 5回連続失敗で15分ロックアウト（Redis）
- **音声アップロード** — WAV / MP3 / M4A（最大50MB）
- **ピッチ精度分析** — Crepeを用いた高精度ピッチ検出・スコア化
- **分析結果の保存** — 結果のみPostgreSQLに保存（音声ファイルは即時削除）
- **統計ダッシュボード** — 過去の分析結果の推移を可視化

## 開発予定の機能

- **歌唱技法の検出** — ビブラート・こぶし・フォール・しゃくり・ロングトーンの自動評価
- **リズム・グルーブ感の評価** — BPMに対するタイミングのズレを評価
- **声域の可視化** — 最低音〜最高音の計測・経時変化の追跡
- **AIフィードバック生成** — スコアに基づいた具体的な改善アドバイス
- **音源分離（Demucs）** — カラオケ録音からのボーカル自動抽出（現在はスタブ）
- **おすすめ楽曲提案** — 声域・歌唱スタイルに合った楽曲の提案
- **非ログインでの分析** — ゲストユーザーによる分析機能

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | TypeScript、React、Vite |
| バックエンド | Python 3.11、FastAPI |
| 音声処理 | Crepe、librosa、Demucs v4（実装予定）、PyTorch |
| データベース | PostgreSQL 15 |
| キャッシュ / ロックアウト | Redis 7 |
| 認証 | JWT（httpOnly Cookie）、bcrypt |
| インフラ | Docker、Docker Compose、Nginx |

---

## セットアップ

前提条件：Docker と Docker Compose がインストール済みであること

```bash
# 1. リポジトリをクローン
git clone https://github.com/supu1495/vocal-analyzer.git
cd vocal-analyzer

# 2. 環境変数ファイルを作成
cp .env.example .env
# .env を編集して SECRET_KEY を設定してください

# 3. 全サービスを起動
docker compose up --build
```

| サービス | URL |
|---|---|
| フロントエンド | http://localhost:5173 |
| バックエンドAPI | http://localhost:8000 |
| APIドキュメント | http://localhost:8000/docs |

---

## APIエンドポイント

### 認証

| メソッド | エンドポイント | 説明 |
|---|---|---|
| `POST` | `/api/v1/auth/register` | ユーザー登録 |
| `POST` | `/api/v1/auth/login` | ログイン・Cookie発行 |
| `GET` | `/api/v1/auth/me` | ログイン中ユーザー情報取得 |
| `POST` | `/api/v1/auth/logout` | ログアウト・Cookie削除 |

### 音声分析

| メソッド | エンドポイント | 説明 | 認証 |
|---|---|---|---|
| `POST` | `/api/v1/analysis/upload` | 音声をアップロードして分析 | 必須 |
| `GET` | `/api/v1/analysis/{id}` | 分析結果を取得 | 必須 |
| `GET` | `/api/v1/analysis/user/statistics` | ユーザーの統計・進捗を取得 | 必須 |

---

## セキュリティとプライバシー

- **音声データを保存しない** — 録音は処理後に即時削除。分析結果のみ保存
- **JWT認証** — httpOnly Cookieで管理（XSS対策）
- **ロックアウト** — 連続ログイン失敗をRedisで検知・ブロック
- **HTTPS** — 本番環境ではSSL/TLSによる通信暗号化を前提とする

---

## 開発ロードマップ

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 1 | Docker環境構築（5サービス構成） | ✅ 完了 |
| Phase 2 | 音声分析エンジン（Crepe・librosa） | ✅ 完了 |
| Phase 3 | フロントエンド（アップロード・結果・ダッシュボード） | ✅ 完了 |
| Phase 4 | DB連携（PostgreSQL・Alembic） | ✅ 完了 |
| Phase 5 | 認証（JWT / httpOnly Cookie / Redisロックアウト） | ✅ 完了 |
| Phase 6 | テスト（pytest・APIテスト） | 🔲 予定 |
| Phase 7 | 音声分析コア実装（技法検出・リズム・声域・フィードバック） | 🔲 予定 |
| Phase 8 | 非同期処理（Celery + Demucs本番復帰） | 🔲 予定 |
| Phase 9 | 本番環境デプロイ | 🔲 予定 |

---

## ライセンス

未定

---

## お問い合わせ

ご質問・ご意見はIssueからお気軽にどうぞ。

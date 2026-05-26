# vocal-analyzer

カラオケ録音データを使い、ピッチ精度や歌唱技法などを自動解析し、歌唱力向上をサポートするWebアプリです。

> ⚠️ 現在開発中です

---

## 実装済みの機能

- **ユーザー認証** — メール・パスワードによる登録・ログイン（JWT / httpOnly Cookie）
- **ログイン保護** — 5回連続失敗で15分ロックアウト（Redis）。UI 側でも 429 受信時にログインボタンを 15分無効化
- **音声アップロード** — WAV / MP3 / M4A（最大50MB、チャンクストリーミングで早期拒否）
- **ピッチ精度分析** — Crepeを用いた高精度ピッチ検出・スコア化
- **リズム・グルーブ感の評価** — 発声タイミングとビートのズレの一貫性を計測
- **声域の計測** — 最低音〜最高音・音域幅（半音数）を計算
- **歌唱技法の検出** — ビブラート・こぶし・フォール・しゃくり・ロングトーンを自動検出
- **スコアマトリクス** — 基本忠実度・技法スコア・不自然さペナルティ・総合スコアを算出
- **フィードバック生成** — スコアと技法データをもとにルールベースで改善アドバイスを生成
- **分析結果の保存** — 結果のみPostgreSQLに保存（音声ファイルは即時削除）
- **非同期処理** — Celery + Redis によるタスクキュー。アップロード後すぐにレスポンスを返し、バックグラウンドで分析を実行
- **音源分離** — Demucs v4（htdemucs）でカラオケ録音からボーカルを自動抽出
- **統計ダッシュボード** — 過去の分析結果の推移を可視化

<img width="452" height="713" alt="image" src="https://github.com/user-attachments/assets/a11b8a8d-b3d4-4a89-9a98-d4728322545e" />
<img width="662" height="920" alt="image" src="https://github.com/user-attachments/assets/88c96efe-8fb9-4565-b3ef-e535d099c67b" />
<img width="660" height="732" alt="image" src="https://github.com/user-attachments/assets/818e22c1-31f9-436c-88cf-49c85c42816f" />



## 開発予定の機能

- **GPU対応** — RTX 4060 Ti を活用した高速分析・高品質音源分離（htdemucs_ft）
- **精度改善** — 実音声による技法検出精度の検証・閾値調整
- **時系列成長分析** — 録音日時・スコア推移・練習継続率の可視化
- **LLMフィードバック** — ローカルLLMによる個別化された歌唱アドバイス
- **PC版UI** — レスポンシブ対応
- **発音ごまかし検出** — 音素分析による歌詞の代替発音の検出
- **おすすめ楽曲提案** — 声域・歌唱スタイルに合った楽曲の推薦

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | TypeScript、React、Vite |
| バックエンド | Python 3.11、FastAPI |
| 音声処理 | Crepe、librosa、Demucs v4、PyTorch |
| 非同期処理 | Celery、Redis |
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
# .env を編集して以下を設定してください
#   - SECRET_KEY: openssl rand -base64 32 などで生成した強い秘密鍵
#   - POSTGRES_PASSWORD: 同様にランダム生成した強いパスワード
#   - CORS_ALLOWED_ORIGINS: フロントエンドのオリジン（カンマ区切りで複数可）

# 3. 全サービスを起動
docker compose up --build
```

| サービス | URL |
|---|---|
| フロントエンド | http://localhost:5173 |
| バックエンドAPI | http://localhost:8080 |
| APIドキュメント | http://localhost:8080/docs |

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
| `POST` | `/api/v1/analysis/upload` | 音声をアップロードしてタスク登録（task_id を返す） | 必須 |
| `GET` | `/api/v1/analysis/status/{task_id}` | 分析タスクのステータス確認 | 必須 |
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
| Phase 6 | テスト（pytest・APIテスト） | ✅ 完了 |
| Phase 7 | 音声分析コア実装（技法検出・リズム・声域・スコアマトリクス・フィードバック） | ✅ 完了 |
| Phase 8 | 非同期処理（Celery + Demucs本番復帰） | ✅ 完了 |
| Phase 9 | 本番環境デプロイ（Cloudflare Pages + Tunnel） | ✅ 完了 |
| Phase 10 準備 | 開発基盤整備（フロント分割・ロギング） | 🔲 予定 |
| Phase 10a | GPU化 + Docker改善 | 🔲 予定 |
| Phase 10b | 精度確認（実音声での検出精度検証・技法バグ修正） | 🔲 予定 |
| Phase 10c | DB移行 + セキュリティ強化 | 🔲 予定 |
| Phase 11 | 時系列成長分析・UI改善・LLMフィードバック | 🔲 予定 |
| Phase 12 | 音声認識の高度化（技法追加・楽曲構造検出・発音検出） | 🔲 予定 |
| Phase 13 | 楽曲連携（おすすめ楽曲提案） | 🔲 予定 |

---

## ライセンス

未定

---

## お問い合わせ

ご質問・ご意見はIssueからお気軽にどうぞ。

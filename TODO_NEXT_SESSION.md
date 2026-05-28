# 次回 Claude セッション用 引き継ぎドキュメント

最終更新: 2026-05-29

---

## このセッションでやったこと

### Phase 10 準備（マージ済み）

App.tsx 分割（#1）/ ドキュメント重複整理（#8）/ シードスクリプト（#31）/ ロギング実装（#13）の4項目すべて完了 → `feature/phase10-prep` を main にマージ。

### Phase 10a: 部分完了

| # | 項目 | 状態 |
|---|---|---|
| 4 | crepe を requirements に追加 | ✅ `requirements-nodeps.txt` を新設して移動 |
| 5 | Docker healthcheck | ✅ 4サービス（db / redis / backend / celery_worker）に追加、起動順序を `service_healthy` に変更 |
| 6 | Docker ログローテーション | ✅ 全6サービス（YAML アンカー `&default-logging` で重複排除） |
| 36 | GPU化 | ❌ **見送り・巻き戻し**（詳細は後述） |
| 33 | 本番環境の接続情報管理 | ⏳ 次回セッションに持ち越し |

### おまけ: テストバグ修正

Phase 9 で `AsyncResult` → `celery_app.AsyncResult` に変えた際にテストが追従していなかった（`api.analysis.AsyncResult` をパッチしようとして AttributeError）。`api.analysis.celery_app.AsyncResult` をパッチするよう修正。37テスト全 pass。

### GPU化見送りの経緯

- 環境は OK だった（WSL2 で nvidia-smi OK・Container Toolkit インストール済み・PyTorch は `+cu121` ビルド）
- docker-compose.yml に GPU 設定追加して `torch.cuda.is_available() == True` まで確認
- しかし Crepe（TensorFlow）が GPU を検出すると XLA JIT で `libdevice` / `ptxas` を要求して失敗
- TF を CPU 固定にする試み3つすべて失敗
  - `tf.config.set_visible_devices([], "GPU")` → TF が import 時点で GPU 検出済み
  - `CUDA_VISIBLE_DEVICES=-1` を import 前後で setup/restore → Celery fork で子プロセスが復元後の状態を継承
  - `TF_XLA_FLAGS=--tf_xla_auto_jit=0` → Crepe 内部の `@tf.function` JIT は止められない
- separator.py / pitch.py / docker-compose.yml の GPU 関連変更をすべて巻き戻して CPU 動作に戻した
- 詳細は CLAUDE.md「決定済みの仕様・注意事項」の「GPU 化見送り」と LEARNING_LOG.md「PyTorch CUDA vs TensorFlow CUDA の違い」を参照

---

## 現在のブランチ状態

- **作業ブランチ**: `feature/phase10a-gpu`（マージ待ち）
- **main ブランチ**: Phase 10 準備までマージ済み

---

## 全体配置（確定版）

```
Phase 10準備 → 10a → 10b → 10c → Phase 11 → Phase 12 → Phase 13
(基盤整備)   (GPU)  (精度)  (D1)  (時系列     (音声高度化)  (楽曲連携)
                                   +UI+LLM)
```

10a（GPU化）を先にやることで、10b（精度確認）で実音声を繰り返し分析する際の処理速度が上がり、htdemucs_ft での検証も可能になる。10c（CF D1移行）はDB層大改修のため最後。

---

### Phase 10 準備：フロント分割 + 開発基盤整備

| # | 項目 | 備考 |
|---|---|---|
| 1 | App.tsx 分割（670行 → 画面ごと） | 以降のフロント修正の前提 |
| 8 | CLAUDE.md / SPEC.md 重複整理 | 以降の追記で混乱しないように |
| 31 | テスト用シードスクリプト（seed.py） | SPEC.md「開発環境セットアップ方針」に記載 |
| 13 | ロギング実装 | SPEC.md「既知の問題」。精度確認・GPU化のデバッグで必須 |

### Phase 10a：GPU化 + Docker改善

Dockerfile / docker-compose.yml / requirements.txt を触る作業をまとめた。精度確認（10b）の前に GPU 環境を整える。

| # | 項目 | 備考 |
|---|---|---|
| 36 | GPU化本体 | WSL2 + NVIDIA Container Toolkit + CUDA PyTorch。htdemucs_ft 切り替え検討 |
| 4 | crepe を requirements.txt に追加 | 現在 Dockerfile に直書き（0.0.13） |
| 5 | Docker healthcheck 追加 | SPEC.md「既知の問題」 |
| 6 | Docker ログローテーション設定 | 長期運用でディスク圧迫 |
| 33 | 本番環境の接続情報管理（Secrets Manager） | インフラ整備タイミングで |

### Phase 10b：精度確認 + 技法検出の既知バグ修正

techniques.py / pitch.py / analyzer.py を触る作業をまとめた。GPU化済みの環境で実音声を検証しながらバグも同時修正。

| # | 項目 | 備考 |
|---|---|---|
| 37 | 精度確認本体（実音声での閾値調整） | GPU化済みで高速。htdemucs_ft での検証も可能 |
| 3 | `calculate_accuracy` の reference 引数整理 | pitch.py:63。第2引数が常に `{}` で未使用 |
| 14 | しゃくり avg_height 過小評価 | SPEC.md 補足参照。藤井風スタイルの問題 |
| 15 | 200セント超の音程変化が未分類 | 将来「感情表現強度」指標として検出したい |
| 16 | 有声区間内のしゃくり未検出 | ピッチスムージングが必要 |
| 17 | 大振幅ビブラートのフォール誤検出 | ビブラート区間をフォール検出から除外 |
| 18 | フレーズ末尾の上昇こぶし未検出 | 低信頼度フラグ付き記録 or 隣接区間参照 |
| 19 | ビブラートの意図識別（暫定改善） | 根本解決は Phase 13（リファレンス楽曲比較） |
| 34 | score_matrix / vocal_range のフロント表示 | backend は計算済み。frontend が未反映 |
| 28 | 分析進捗表示（プログレスバー） | Celery タスクステータス取得は実装済み |

### Phase 10c：CF D1 移行 + セキュリティ

DB層・認証層を触る作業をまとめた。

| # | 項目 | 備考 |
|---|---|---|
| 35 | CF D1 移行本体 | SQLAlchemy → SQLite (D1) |
| 9 | JWT ブラックリスト | 認証層を書き替えるので一緒に |
| 10 | API レート制限 | CF 側の Rate Limiting も活用 |
| 11 | CSP ヘッダー | CF Pages の `_headers` ファイル |
| 21 | 非ログインでの分析（ゲスト） | DB設計変更タイミングで仕様確定 |
| 32 | `hashed_password` デフォルト `''` 見直し | SPEC.md データモデル概要の注記 |

### Phase 11：時系列成長分析 + UI改善 + LLMフィードバック

| # | 項目 | 備考 |
|---|---|---|
| 38 | 時系列成長分析本体 | recorded_at カラム追加・スコア推移・練習継続率 |
| 26 | 複数ファイル一括アップロード・日付指定 | CLAUDE.md に「Phase 11 と合わせて」と記載 |
| 2 | 分析キャンセル機能 | UI 大改修タイミング |
| 25 | PC版UI | スマホ → レスポンシブ対応 |
| 24 | LLM フィードバック（ローカル LLM） | **費用増なし。詳細は後述** |
| 7 | フロントエンドテスト | UI が出揃った後にテスト |
| 12 | CVE スキャン設定（pip-audit / Dependabot） | 機能開発が落ち着くタイミング |

### Phase 12：音声認識の高度化 + 歌唱分析の深化

| # | 項目 | 備考 |
|---|---|---|
| 27 | アクセント・ハンマリング検出 | DAM AI HEART 参考。技法追加 |
| 23 | 楽曲構造検出（A/Bメロ・サビ） | 区間別スコアの基盤 |
| 22 | 声紋登録・比較 | users.voiceprint_data カラムは存在 |
| 29 | 録音ガイドUI | 音量・距離・ノイズの事前チェック |
| 30 | 話者分離・歌声検出のテスト発声 | 声プロファイル取得 |
| 39 | 発音ごまかし検出 | **メイン分析後に別工程。詳細は後述** |

### Phase 13：楽曲連携

| # | 項目 | 備考 |
|---|---|---|
| 20 | おすすめ楽曲提案 | Spotify API 等。外部データ必要 |
| 19 | ビブラートの意図識別（根本解決） | リファレンス楽曲データとの比較が必要 |

---

## 重要な設計決定（このセッションで確定）

### LLM フィードバック（Phase 11）

- **方式**: ローカル LLM（Ollama 等 + RTX 4060 Ti 8GB）
- **モデル**: Llama 3.1 8B / gemma2 9B の Q4量子化（VRAM 4-5GB に収まる）
- **コスト**: 電気代のみ。外部 API 費用は発生しない
- **VRAM 利用**: Demucs/Crepe の分析完了後に LLM 推論を実行。1つの分析リクエスト内で GPU を時間的に排他利用する（同時使用なし）
- **将来**: 知識ベース（発声法・テクニック解説）構築後に RAG に進化可能。これもローカル完結
- **前提**: Phase 10b の GPU 化が完了していること
- **補足**: 「Q4量子化」= モデルパラメータの精度を 16bit → 4bit に圧縮して容量を約1/4にする技術。歌唱フィードバック程度なら実用上問題ない精度

### 発音ごまかし検出（Phase 12）

- **方式**: Whisper で音素列を取得し、音素の繰り返しパターンを分析（方式A）
- **実行タイミング**: メイン分析（Demucs → Crepe → 技法検出 → スコア計算）完了後に別工程で実行。既存の分析精度に影響しない
- **判定ロジック**:
  - 録音データ全体を通して発声している言葉がずっと同じ → **ごまかしの疑いありとして検出**
  - 部分的に同じ言葉が出てくる → **歌詞の一部と推測して検出しない**
- **歌詞データは不要**。Whisper の音素分析だけで完結する

### 開発方針（プロジェクト全体）

- **費用を増やさない**: LLM フィードバックに限らず、開発全体で追加の金銭的費用を極力発生させない方針

---

## 全40項目の番号対応表

重複排除した全項目。各フェーズの表内の `#` はこの番号。

| # | 項目 | 出典 |
|---|---|---|
| 1 | App.tsx 分割 | TODO #9 |
| 2 | 分析キャンセル機能 | TODO #14 |
| 3 | `calculate_accuracy` reference 未使用 | TODO #16 |
| 4 | crepe が requirements.txt にない | TODO #17 |
| 5 | Docker healthcheck | TODO #19 / SPEC.md 既知の問題 |
| 6 | Docker ログローテーション | TODO #20 |
| 7 | フロントエンドテスト・統合テスト・E2E | TODO #21 |
| 8 | CLAUDE.md / SPEC.md 重複整理 | TODO #22 |
| 9 | JWT ブラックリスト | TODO 将来検討 / SPEC.md 将来検討 |
| 10 | API レート制限 | TODO 将来検討 |
| 11 | CSP ヘッダー | TODO 将来検討 |
| 12 | CVE スキャン | TODO 将来検討 |
| 13 | ロギング未実装 | SPEC.md 既知の問題 |
| 14 | しゃくり avg_height 過小評価 | SPEC.md 既知の問題 |
| 15 | 200セント超の音程変化が未分類 | SPEC.md 既知の問題 |
| 16 | 有声区間内のしゃくり未検出 | SPEC.md 既知の問題 |
| 17 | 大振幅ビブラートのフォール誤検出 | SPEC.md 既知の問題 |
| 18 | フレーズ末尾の上昇こぶし未検出 | SPEC.md 既知の問題 |
| 19 | ビブラートの意図識別不能 | SPEC.md 既知の問題 |
| 20 | おすすめ楽曲提案 | SPEC.md 将来検討 |
| 21 | 非ログインでの分析（ゲスト） | SPEC.md 将来検討 |
| 22 | 声紋登録・比較 | SPEC.md 将来検討 |
| 23 | 楽曲構造検出（A/Bメロ・サビ） | SPEC.md 将来検討 |
| 24 | LLM フィードバック | SPEC.md 将来検討 + ユーザー追加要望 |
| 25 | PC版UI | SPEC.md 将来検討 / CLAUDE.md 技術的負債 |
| 26 | 複数ファイル一括アップロード・日付指定 | SPEC.md 将来検討 / CLAUDE.md 技術的負債 |
| 27 | アクセント・ハンマリング検出 | SPEC.md 将来検討 / CLAUDE.md 技術的負債 |
| 28 | 分析進捗表示 | SPEC.md 将来検討 / CLAUDE.md 技術的負債 |
| 29 | 録音ガイドUI | SPEC.md 将来検討 / CLAUDE.md 技術的負債 |
| 30 | 話者分離・歌声検出のテスト発声 | SPEC.md 将来検討 / CLAUDE.md 技術的負債 |
| 31 | テスト用シードスクリプト（seed.py） | SPEC.md 開発環境セットアップ方針 |
| 32 | `hashed_password` デフォルト `''` 見直し | SPEC.md データモデル概要 |
| 33 | 本番環境の接続情報管理（Secrets Manager） | CLAUDE.md 技術的負債 |
| 34 | score_matrix / vocal_range フロント表示 | CLAUDE.md 技術的負債 |
| 35 | CF D1 移行 | CLAUDE.md Phase 10 予定 |
| 36 | GPU化 | CLAUDE.md Phase 10 予定 |
| 37 | 精度確認 | CLAUDE.md Phase 10 予定 |
| 38 | 時系列成長分析 | CLAUDE.md Phase 11 予定 |
| 39 | 発音ごまかし検出 | ユーザー追加要望 |

---

## 推奨される次回作業の進め方

### Step 1: `feature/phase10a-gpu` ブランチを継続（main にはまだマージしない）

Phase 10a は #33 が未完のため、同ブランチ上で作業を続行する。

### Step 2: #33 を実施して Phase 10a を締める

**現実的なスコープに修正**: 自宅 PC + CF Tunnel の構成では AWS Secrets Manager 等の本格ツールは過剰。以下の組み合わせを提案：

| 案 | 内容 |
|---|---|
| A | 起動時バリデーション（SECRET_KEY が `your-secret-key-here` のまま、POSTGRES_PASSWORD が `changeme` のままなら起動失敗） |
| B | シークレット生成ヘルパースクリプト（`python scripts/gen_secrets.py` で雛形を出力） |
| D | `.env.example` のドキュメント拡充（用途・ローテーション方法・生成方法） |

C（Docker Secrets 化）は home PC では効果薄なので見送り。

### Step 3: Phase 10a を main にマージしてから Phase 10b（精度確認 + 技法バグ修正）に進む

```bash
git checkout main
git merge feature/phase10a-gpu
git checkout -b feature/phase10b-accuracy
```

GPU化は見送ったが Phase 10b は CPU で進められる。GPU 化は Phase 10c 以降で再挑戦するときの選択肢：
- TF を `tensorflow[and-cuda]` に置き換え（イメージ +1〜2GB）
- Crepe を別プロセスで実行して PyTorch と CUDA 状態を分離

| # | 項目 |
|---|---|
| 37 | 精度確認本体（実音声での閾値調整） |
| 3 | `calculate_accuracy` の reference 引数整理（pitch.py:63） |
| 14〜19 | 既知の技法検出バグ修正（しゃくり・フォール・こぶし・ビブラート） |
| 34 | score_matrix / vocal_range のフロント表示 |
| 28 | 分析進捗表示 |

---

## 既知の挙動（バグではない）

- **CF Tunnel の瞬断**: ログイン時など CF → 自宅 PC の接続が一瞬切れると「Failed to fetch」が出る。リトライで通る
- **Cloudflare レートリミット (error code 1015)**: 短時間に大量リクエストで CF 側で弾かれる。通常操作では発動しない
- **ロックアウト UI の制約**: ページリロードでロックアウト状態が失われる（サーバー側 Redis にはカウントが残る）

---

## 重要なファイル・コマンド早見表

### 起動・確認

```bash
docker compose up -d
docker compose restart celery_worker
docker compose up -d --build backend
docker compose logs celery_worker -f
docker compose logs backend --tail=30
```

### CF Tunnel

```bash
cat ~/.cloudflared/config.yml
nohup cloudflared tunnel run > /tmp/cloudflared.log 2>&1 &
ps aux | grep cloudflared | grep -v grep
```

### DB 操作

```bash
docker compose exec db psql -U postgres -d vocal_analyzer
docker compose exec db psql -U postgres -d vocal_analyzer -c "\dt"
docker compose exec db psql -U postgres -d vocal_analyzer -c "SELECT id, email, created_at FROM users;"
docker compose exec backend alembic upgrade head

# DB 完全初期化
docker compose down
docker volume rm vocal-analyzer_postgres_data
docker compose up -d
docker compose exec backend alembic upgrade head
```

### テスト実行

```bash
docker compose exec backend python -m pytest -v
```

### デバッグ

```bash
docker compose exec celery_worker celery -A celery_app inspect active
docker compose exec redis redis-cli keys "lockout:*"
docker compose exec redis redis-cli keys "login_fail:*"
docker compose exec celery_worker ls -la /tmp/vocal_analyzer/
```

### 構成

- Frontend: `https://vocal-analyzer.supu361.dev`（CF Pages）
- Backend API: `https://vocal-api.supu361.dev`（CF Tunnel → 自宅PC `localhost:8080`）
- ローカル開発: `http://localhost:5173`（Vite proxy で `/api/*` を backend に転送）

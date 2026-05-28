# CLAUDE.md - 引き継ぎドキュメント

## プロジェクト概要
カラオケ音声分析システム。ユーザーがカラオケで録音した音声をAIで分析し、歌唱力向上のフィードバックを提供するWebアプリ。

---
## Claude Codeへの指示

### 回答スタイル
・わからないことは「わからない」と明示する。推測と確実な情報は区別する
・情報源（公式ドキュメント等）がある場合は明示する
・間違いを指摘されたら素直に訂正する
・不確かなコードには「要確認」とコメントを入れる
・エラーは原因を推測ではなく調査ベースで答える
・存在しないAPI・ライブラリは絶対に使わない

### 進め方
・授業形式で進める（質問を細かく受け付ける）
・一度に大量のコードを書かず、ステップで確認しながら進める
・新しい import を追加する前に「何のために必要か」を説明してから承認を得る
・コードの変更はステップごとに確認しながら進める

### 作業ルール
・git操作（コミット・push・マージ等）と docker compose の状態変更コマンドは実行せず、コマンドをコードブロックで提示する。ユーザーが自分で実行する派
・docker compose logs / docker ps / curl などの読み取り専用の確認コマンドは Bash ツールで実行して結果を確認しても良い
・LEARNING_LOG.md に学習記録が蓄積されている。新セッションでも内容を踏まえて回答する
・ユーザーが「メモしてほしい」と言ったときに LEARNING_LOG.md に追記する。自発的には追記しない

### セッション開始時
・`TODO_NEXT_SESSION.md` を読んで前回までの作業内容・次にやることを把握する
・`CLAUDE.md` 内の「現在の状態」セクションで現在のブランチ・進捗を確認する
・必要に応じて `SPEC.md` で機能要件・設計方針を確認する

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

| Phase | 内容 | テスト |
|---|---|---|
| 1 | Docker環境構築（5サービス） | — |
| 2 | 音声分析エンジン（Crepe + librosa） | — |
| 3 | フロントエンド3画面 | — |
| 4 | DB連携（PostgreSQL + SQLAlchemy + Alembic） | — |
| 5 | 認証（JWT httpOnly Cookie + Redis ロックアウト） | — |
| 6 | バックエンドテスト（pytest） | 34テスト |
| 7 | 音声分析エンジン本実装（技法検出 + スコアマトリクス） | 34テスト |
| 8 | 非同期処理（Celery + Demucs v4） | 37テスト |
| 9 | 本番デプロイ（CF Pages + CF Tunnel） | 37テスト |

各フェーズの詳細な変更内容はページ下部の「ログ」セクションを参照。

---

## 現在の状態

- **作業ブランチ**: `feature/phase10a-gpu`（#33 が未実施のため main マージ前）
- **mainブランチ**: Phase 10 準備までマージ済み
- **ローカル動作確認**: Docker Compose で全6サービス起動確認済み（healthcheck・ログローテーション設定済み）
- **本番動作確認**: CF Pages + CF Tunnel で動作確認済み
- **注意**: port 80 はホスト側の Apache が競合する場合あり。その場合は `http://localhost:5173` に直接アクセス（Viteの proxy 設定で `/api/*` は backend に転送される）

---

## 決定済みの仕様・注意事項

**著作権保護:** 録音音声ファイルは保存しない。分析結果のみPostgreSQLに保存。

**Demucs（Phase 8）:** `backend/audio/separator.py` は Demucs v4 で実装済み。モデルは `htdemucs`（標準）を使用。Celery Worker コンテナで非同期実行するため CPU 処理の遅さはユーザー体験に影響しない（`htdemucs_ft` は4倍重いアンサンブルモデルのためCPUでは非実用的。GPU 化のタイミングで切り替えを検討する。Phase 10以降で対応）。

**Crepe採用:** 精度重視のためlibrosa.pyinへの変更はしない。

**GPU 化見送り（Phase 10a で挑戦・失敗）:** Demucs（PyTorch）の GPU 化は環境としては動作確認済み（WSL2 で `nvidia-smi` OK・NVIDIA Container Toolkit 導入済み・PyTorch は `+cu121` ビルド）。しかし Crepe が依存する TensorFlow が同コンテナで GPU を検出すると XLA JIT コンパイル時に `libdevice` / `ptxas` を要求して失敗する。`tf.config.set_visible_devices`・`CUDA_VISIBLE_DEVICES` env 操作・`TF_XLA_FLAGS` での XLA 無効化のいずれも効かなかった（TF の遅延初期化・fork 後の再検出・`@tf.function` 内の JIT が原因）。

Phase 10a では一旦 CPU 動作に戻し、Phase 10c 以降で次のいずれかを再検討する想定：
- TF を `tensorflow[and-cuda]` に差し替えて TF CUDA 依存ライブラリを揃える（イメージサイズ +1〜2GB）
- Crepe を別プロセスで実行して TF と PyTorch の CUDA 状態を分離する

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

## 既知の問題・技術的負債

| 問題 | 重大度 | 対応予定 |
|---|---|---|
| ロギング未実装 | 🟡 低 | Phase 10準備 |
| `docker-compose.yml` に healthcheck 未設定 | 🟡 低 | Phase 10a |
| しゃくり検出の `avg_height` 過小評価（ゆっくり上昇スタイル） | 🟡 低 | Phase 10b |
| 200セント超の音程変化を未分類のまま除外している | 🟡 低 | Phase 10b |
| 有声区間内のしゃくり（無声区間をはさまない滑り込み）を未検出 | 🟡 低 | Phase 10b |
| 大振幅ビブラートがフレーズ末尾まで続く場合、フォールと誤検出する可能性 | 🟡 低 | Phase 10b |
| フレーズ末尾で上昇して終わるこぶし（逆V字）を未検出 | 🟡 低 | Phase 10b |
| ビブラートの「加点目的」と「アーティストのアレンジ模倣」を区別できない | 🟡 低 | Phase 13 |

#### 補足

**しゃくりの `avg_height` 過小評価：**  
`_SHAKURI_SETTLE_FRAMES`（5フレーム）以内にゆっくり上昇するスタイル（藤井風のようなグルーヴ重視のアーティスト）では、安定音程の推定に上昇中のフレームが混入して `avg_height` が実際より小さく出る。検出の有無には影響しないが正確な幅の計測には改善が必要。

**有声区間内のしゃくり：**  
現在の実装は「無声（NaN）→ 有声」の切り替わり時のみしゃくりを検出する。母音が連続するメリスマや有声子音（n, r など）が続くフレーズでは NaN が生まれないため、その区間内のしゃくりを取りこぼす。有声区間内の「ピッチ下降 → 上昇パターン」を検出するにはピッチのスムージングが必要で、実音声によるパラメータ調整が先決のため現段階では対応しない。

**ビブラートの意図識別不能：**  
「旋律のない区間でのビブラート」を減点したい一方で、アーティストのビブラートスタイルを模倣した表現は加点したい。しかし、「採点目的の加点行為」と「意図的なアレンジ模倣」は音声データだけでは区別できない。どこにビブラートをかけるべきかという文脈判断には楽曲のリファレンスデータが必要なため、現フェーズでは `detect_vibrato` の返り値から `gratuitous_count` フィールドを除外している。将来的にはLLMフィードバックやリファレンス楽曲との比較で対応する。

**フレーズ末尾の上昇こぶし未検出：**  
`detect_kobushi` はこぶしの「ベースラインへの戻り」を確認するために逸脱区間の後にフレームが必要なため、有声区間の末尾に達した逸脱はスキップしている。下降方向の末尾逸脱は `detect_fall` が担当するが、上昇方向（逆V字）の末尾こぶしはいずれにも検出されない。対応方針として、逸脱が上昇方向かつ有声区間の末尾に達した場合は「戻り確認なしのこぶし候補」として低信頼度フラグ付きで記録する、または隣接する有声区間の開始ピッチをもって「戻り」とみなす方法が考えられる。

**大振幅ビブラートのフレーズ末尾でのフォール誤検出：**  
フォール検出は「有声 → 無声（NaN）への切り替わり直前の単調下降区間」を対象にしている。ビブラートが大きな振幅（±100cent以上）でフレーズ末尾まで続いた場合、最後の下降半周期（約60ms・100cent程度）が深さ・時間・速度の全フィルタを通過してフォールとして誤検出される可能性がある。単調性ウォークにより拾う区間を1サイクル分に絞っているため影響は限定的。根本解決はビブラート検出（`detect_vibrato`）の実装後に「ビブラート区間をフォール検出から除外する」後処理を加えることで対応する。

**200セント超の音程変化：**  
`_SHAKURI_MAX_CENTS = 200.0` を超える上昇をしゃくりから除外しているが、原因は複数考えられる。体力が続かず音程をキープできていないケース、感情的な荒々しさや意図的な崩しの表現である可能性もある。現段階では未分類のまま除外しており、将来は「感情表現強度」の別指標として検出できると望ましい。

---

## 次にやるべきこと

### 開発ロードマップ（Phase 10〜13）

```
Phase 10準備 → 10a(GPU) → 10b(精度) → 10c(D1) → Phase 11 → Phase 12 → Phase 13
```

| フェーズ | 内容 |
|---|---|
| Phase 10 準備 | App.tsx 分割・ドキュメント整理・ロギング実装・シードスクリプト |
| Phase 10a | GPU化（CUDA PyTorch + RTX 4060 Ti）・Docker改善（healthcheck・ログローテーション）・接続情報管理 |
| Phase 10b | 精度確認（実音声での閾値調整・技法検出バグ修正）・スコア表示のフロント反映・分析進捗表示 |
| Phase 10c | CF D1 移行（PostgreSQL → SQLite）・セキュリティ強化（JWTブラックリスト・レート制限・CSP）・ゲスト分析仕様確定・`hashed_password` デフォルト見直し |
| Phase 11 | 時系列成長分析・一括アップロード/日付指定・分析キャンセル・PC版UI・ローカルLLMフィードバック・フロントエンドテスト・CVEスキャン |
| Phase 12 | アクセント/ハンマリング検出・楽曲構造検出・声紋登録/比較・録音ガイドUI・話者分離/テスト発声・発音ごまかし検出 |
| Phase 13 | おすすめ楽曲提案・ビブラートの意図識別（根本解決・リファレンス楽曲比較） |

10a（GPU化）を精度確認より先にやることで、10b で実音声を繰り返し分析する際の処理速度と品質（htdemucs_ft）が向上する。

### 設計決定事項（2026-05-27 確定）

- **LLM フィードバック（Phase 11）**: ローカル LLM（Ollama 等 + RTX 4060 Ti）で実装。外部 API 費用を増やさない。分析完了後に GPU を排他利用して推論
- **発音ごまかし検出（Phase 12）**: Whisper 音素分析でメイン分析後に別工程実行。録音全体で同じ言葉 → ごまかし検出。部分的に同じ言葉 → 歌詞と推測し除外
- **開発方針**: 追加の金銭的費用を極力発生させない

### 注意事項

- **Cloudflare Tunnel のエグレス**: 分析結果（JSON）はKB単位のテキストのため実質問題なし
- **score_matrix / vocal_range のフロント未反映**: backend は計算済みだが frontend は `(pitch + rhythm) / 2` の単純平均で表示中。Phase 10b で修正予定

全項目の詳細は `TODO_NEXT_SESSION.md` を参照。

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
        ├── App.tsx                  # ルーティング・認証状態管理・ヘッダー
        ├── types.ts                 # 型定義・定数・ユーティリティ
        ├── components/
        │   ├── ScoreRing.tsx        # スコアリング表示
        │   ├── TechniqueBar.tsx     # 技法バー
        │   └── LineChart.tsx        # 折れ線グラフ
        └── screens/
            ├── AuthScreen.tsx       # ログイン / 登録
            ├── UploadScreen.tsx     # アップロード + ポーリング
            ├── ResultScreen.tsx     # 分析結果表示
            └── DashboardScreen.tsx  # 統計ダッシュボード
```
---
## ログ

### 2026-05-28 Phase 10 準備：フロント分割・ドキュメント整理・シード・ロギング実装
- `frontend/src/App.tsx`: 670行 → 9ファイル（最大187行）に分割
  - `types.ts`（型定義・定数・ユーティリティ）/ `components/`（ScoreRing・TechniqueBar・LineChart）/ `screens/`（Auth・Upload・Result・Dashboard）
- `CLAUDE.md` / `SPEC.md`: 重複整理
  - 設計判断・既知の問題は CLAUDE.md に一元化、SPEC.md は製品仕様（機能要件・コア評価ロジック・データモデル）に特化
- `backend/seed.py`: 新規追加
  - テストユーザー2件 + サンプル分析5件（日付分散）を投入。冪等性あり
- `backend/logging_config.py`: 新規追加・全モジュールに logger 仕込み
  - INFO（ログイン成功・アップロード受信・タスク開始/完了）/ WARNING（ログイン失敗・ロックアウト・403・アップロード拒否）/ ERROR（タスク失敗）/ DEBUG（各分析段階の処理時間）
  - `LOG_LEVEL` 環境変数で切り替え可能
- `feature/phase10-prep` → `main` マージ済み

### 2026-05-28〜29 Phase 10a: GPU化挑戦・見送り + Docker改善
- `backend/requirements-nodeps.txt`: 新規追加・`crepe==0.0.13` を移動（Dockerfile 直書きを解消）
- `docker-compose.yml`: 4サービス（db / redis / backend / celery_worker）に healthcheck 追加、`depends_on` を `condition: service_healthy` に変更
- `docker-compose.yml`: 全6サービスにログローテーション設定（json-file driver・10MB × 3世代）。YAML アンカー `&default-logging` で重複排除
- `backend/tests/test_api_analysis.py`: 既存バグ修正（`api.analysis.AsyncResult` → `api.analysis.celery_app.AsyncResult` にパッチ対象を変更）。Phase 9 でコード変更時にテスト追従漏れがあったものを発見
- **GPU化見送り**: Demucs（PyTorch）の GPU 化は環境設定で動く想定だったが、Crepe（TensorFlow）の制約で諦め。詳細は「決定済みの仕様・注意事項」の「GPU 化見送り」参照
  - 試行：`tf.config.set_visible_devices` / `CUDA_VISIBLE_DEVICES` env / `TF_XLA_FLAGS` — すべて効かず
  - 最終的に separator.py・pitch.py・docker-compose.yml の GPU 関連変更を巻き戻し
- #33（本番環境の接続情報管理）は次回セッションに持ち越し

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

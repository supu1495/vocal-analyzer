# LEARNING_LOG.md

Claude Codeと進めた学習の記録。コードの理解・疑問・気づきをまとめる。

---

## `.claude/settings.local.json` — Claude Codeの権限設定ファイル

Claude Codeがコマンドを実行するとき、デフォルトでは毎回「許可しますか？」と確認を求めてくる。このファイルに書いたコマンドは確認なしで自動実行される。

現在は `git add` だけ許可されている。ローカル操作（add）は間違えても取り返しがつくが、リモートへの反映（push）は慎重にするという設計になっている。

`settings.json`（チーム共有用）と`settings.local.json`（個人環境用）に分かれており、後者は個人設定をチームに押しつけないようにするためのもの。

**疑問と回答:**
- Q: `.gitignore`に入れた方がいい？
- A: チーム開発なら入れるべき（個人設定を他人に押しつけない）。1人で複数マシンを使う場合はgitで共有してOK

## `main.py` — アプリの入口

FastAPIはPythonのフレームワーク。フレームワークとは「よく使う機能をまとめた土台」で、URLの解析・エラー処理・ドキュメント生成などが最初から揃っている。APIとはアプリ同士が決められた形式で情報をやり取りするための窓口のこと。

`app = FastAPI(...)` でアプリ本体を作成し、`app`という変数に入れる。以降の設定はすべてこの`app`に対して行う。`title`や`description`は`http://localhost:8000/docs`で見られる自動生成APIドキュメントに表示される。

CORSMiddlewareはFastAPIが提供するクラス。CORS（Cross-Origin Resource Sharing）はブラウザのセキュリティ機能で、デフォルトでは別サーバーへのリクエストをブロックする。フロントエンド（localhost:5173）からバックエンド（localhost:8000）へのリクエストは「別のサーバー」扱いになるため明示的に許可が必要。`allow_origins`に指定したURLからのリクエストだけを許可する。`allow_methods=["*"]`はGET/POST/DELETEなど全メソッドを、`allow_headers=["*"]`は全ヘッダーを許可する。

ルーターとは「このURLが来たらこの処理をする」という対応表。`auth_router`は認証関連（login/register等）、`analysis_router`は音声分析関連のURLと処理をまとめたもの。main.pyで`include_router`することで接続される。こうすることでファイルが肥大化せず機能ごとに分割できる。

`GET /` は動作確認用で「APIが動いてるよ」というメッセージを返すだけ。`GET /health` はDockerなどのインフラが「このサービスは生きているか」を確認するために叩くエンドポイント。

**疑問と回答:**
- Q: CORSMiddlewareはクラス？
- A: そう、FastAPIが提供しているクラス

- Q: 別サーバーへのリクエストをブロックするのは悪質なところに情報を取られないため？
- A: ほぼ合っている。正確には「悪意あるサイトがユーザーのブラウザを踏み台にして別サーバーに勝手にリクエストを送る」攻撃を防ぐため

- Q: Cookieとは？
- A: ブラウザに保存される小さなデータ。ログイン状態などを覚えておくために使い、リクエスト時にブラウザが自動で送り続ける

- Q: JWTとは？
- A: ログイン状態を証明するデジタルの「入館証」。ログイン成功時にサーバーが発行し、以降のリクエストで提示することで認証済みを証明する

- Q: httpOnly Cookieとは？
- A: JavaScriptから読み取れないCookie。通常のCookieは`document.cookie`で中身が見えるが、httpOnly属性をつけるとJSから読めなくなる。悪意あるスクリプトにJWTを盗まれないための対策

- Q: `allow_credentials=True`が必要な理由は？
- A: CookieはデフォルトでCORSリクエスト（別サーバーへのリクエスト）に自動送信されない。TrueにすることでフロントエンドからのリクエストにCookieが自動でついてくる

## `database.py` — DB接続設定

`os.environ`はOS上で設定されている環境変数の一覧。`os.environ["DATABASE_URL"]`のようにキー名で値を取り出せる。コードに直接URLやパスワードを書くとGitHubに上げたとき誰でも見えてしまうため、コードと設定値を分離する目的で使う。`docker-compose.yml`に書いた値がコンテナ起動時に環境変数としてセットされ、ここで取り出される。

`docker-compose.yml`自体はGitHubに上がる。DBの接続URLは開発用のデフォルト値（ユーザー名`postgres`・パスワード`postgres`）なので直書きでも実害はない。本当に隠すべき`SECRET_KEY`は`${SECRET_KEY}`という書き方で`.env`ファイルから読み込む。`.env`は`.gitignore`に入れてGitHubに上げない。

SQLAlchemyはPythonからDBを操作するためのORMライブラリ。ORM（Object-Relational Mapper）とは「DBのテーブルをPythonのクラスとして扱えるようにする仕組み」。生のSQL文字列を書く代わりにPythonのコードとしてDB操作を書ける。

`engine`はDBへの接続の窓口。`SessionLocal`はSessionを作るためのファクトリーで、呼び出すたびに新しいSessionが作られる。Sessionとはトランザクション（複数の操作をひとまとめにして全部成功か全部なかったことにする仕組み）を管理するDBとの会話の単位。`commit()`はその操作をDBに正式に書き込む確定命令。`autocommit=False`は手動で`commit()`を呼ぶまでDBに反映しない設定。`autoflush=False`は`commit()`前にSQLが自動で走らないようにする設定。`bind=engine`はこのSessionがどのengine（DB接続）を使うかを紐付ける引数。

`DeclarativeBase`はSQLAlchemyが提供する基底クラス。これを継承した`Base`をさらに継承することで、SQLAlchemyはそのクラスを「DBのテーブルを表すクラス」として認識する。`Base`を一段かませているのは全モデル共通の設定を後から追加できるようにするため。

`get_db()`はFastAPIのDependency Injection（DI）という仕組みで使われる関数。DIとは「関数が必要とするものを外から渡す仕組み」。エンドポイントに`db: Session = Depends(get_db)`と書くとFastAPIがリクエストのたびに自動でSessionを作って渡してくれる。Sessionを使うことで`db.query(...)`でDB検索や`db.add(...)`でレコード追加ができる。`yield`を使っているので処理が終わったら必ず`db.close()`でSessionが閉じられる。

**疑問と回答:**
- Q: docker-compose.ymlはGitHubに上がらないの？
- A: 上がる。ただしDBの接続URLは開発用のデフォルト値なので実害はない。本当に秘密にすべき`SECRET_KEY`は`.env`経由で渡し、`.env`は`.gitignore`でGitHubに上げない

- Q: `Base`と書いてあるだけでSQLAlchemyはDBのテーブルだと認識するの？
- A: `Base`という名前自体に意味はない。`DeclarativeBase`を継承したクラスの子孫をSQLAlchemyが追跡する仕組みになっている

### `auth_utils.py` — 認証ユーティリティ

JWT生成・検証・パスワードハッシュ化・ロックアウト管理をまとめたファイル。

**定数と初期設定：**
`SECRET_KEY`はJWTの署名に使う秘密鍵。`ALGORITHM = "HS256"`はHMAC + SHA-256という署名方式。SHA-256はどんな入力でも256ビットの固定長の値に変換するハッシュ関数。HMACはSHA-256にSECRET_KEYを組み合わせて署名を作る方式で、SECRET_KEYを知らないと同じ署名が作れない。JWTを受け取るとき同じ計算をして署名が一致すれば「本物・改ざんなし」と判断する。

変数名に単位が含まれている：`ACCESS_TOKEN_EXPIRE_MINUTES`は分単位（`timedelta(minutes=...)`に渡す）、`_LOCKOUT_SECONDS`は秒単位（RedisのEXPIREコマンドが秒単位のため）。

**bcrypt：** パスワードのハッシュ化に特化したアルゴリズム。SHA-256は高速だがパスワードには逆効果（攻撃者が総当たり攻撃をしやすくなる）。bcryptは意図的に計算を遅くして総当たり攻撃を現実的でなくしている。`deprecated="auto"`はbcrypt自体が非推奨という意味ではなく「古いハッシュ方式で保存されたパスワードを検証したとき自動的に新しい方式で再ハッシュするよう促す」設定。このままで問題ない。

**`_redis`：** Redisサーバーへの接続を持つオブジェクト。Redisは「高速な一時データ置き場」でデータをメモリ上に置くため読み書きが速い。PostgreSQLがデータを永続的にディスクに保存するのに対して、Redisは有効期限付きの一時データに向いている。このアプリではログイン失敗カウントの管理に使っている。先頭の`_`は「このファイル内でだけ使う変数」という慣習。

**DUMMY_HASH：** タイミング攻撃対策。存在するメールは「DBを検索＋bcrypt検証（約100ms）」、存在しないメールは「DBを検索のみ（約1ms）」となり時間差でメールの存在が推測できてしまう。DUMMY_HASHを使うことで存在しない場合もbcryptを実行して時間差をなくす。

**LuaスクリプトとINCR・EXPIRE・atomic：**
- INCR：Redisのコマンドでキーの値を1増やす（インクリメント）
- EXPIRE：Redisのコマンドでキーに有効期限（TTL: Time To Live）をセットする
- atomic：複数の操作が途中で分割されずに実行されること
PythonでINCRとEXPIREを別々に呼ぶとその間にクラッシュした場合タイマーがセットされずロックが永遠に解除されない。LuaスクリプトにまとめてRedisに渡すとRedisが「これは1つの操作」として実行するので途中で止まらない。`_redis.eval(スクリプト, キーの数, キー名, 有効期限秒数)`という形式で呼ぶ。

**パスワード関連：** `hash_password`は生のパスワードをbcryptでハッシュ化して返す。DBには絶対に生のパスワードを保存しない。`verify_password`は入力されたパスワードとDBのハッシュを照合する。ハッシュは元に戻せないので「同じハッシュになるか」を計算して一致確認する。

**JWT関連：**
JWTは3つのパーツをBase64でエンコードした形式。Base64はバイナリデータや特殊文字を含むデータを「URLや通信で安全に扱える文字列」に変換する方式。暗号化ではないので秘密情報を隠す目的では使えない。

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.xxxxx
       ↑ヘッダー          ↑ペイロード    ↑署名
```

ペイロードとは「運んでいる中身のデータ」のこと。このアプリではユーザーID（`sub`）と有効期限（`exp`）が入っている。デコードとはBase64でエンコードされたJWTを元のデータに戻す操作。デコードと同時に署名の検証も行い改ざんされていないか確認する。

`_decode_token`の先頭`_`は「このファイル内でだけ使う関数」という慣習。

`headers={"WWW-Authenticate": "Bearer"}`はHTTPの標準規格で「Bearer方式のJWTで認証してください」とクライアントに伝えるヘッダー。PostmanなどのAPIテストツールがこのレスポンスを受け取ると「Bearer認証が必要なAPIだ」と自動認識する。

**Postman：** APIのテストツール。ブラウザで手軽にできないPOSTやDELETEなどのリクエストを手動で送ったりヘッダー・Cookieを自由に設定してAPIの動作確認ができる。

`get_current_user`の`Cookie(default=None)`はFastAPIがリクエストのCookieから`access_token`という名前の値を自動で取り出す仕組み。Cookieにトークンがなければ`None`になり401エラーを返す。CookieからJWTを取り出してデコードし、DBでユーザーを確認して返すという一連の認証処理をまとめた関数。

**疑問と回答：**
- Q: 20行目は分単位、24行目は秒単位、どこで設定しているの？
- A: 変数名に単位が書いてある（MINUTES・SECONDS）。渡す先の関数がそれぞれ分・秒を受け取る仕様になっている

- Q: `deprecated="auto"`はbcryptが古いということ？
- A: bcrypt自体は現役。古いハッシュ方式で保存されたパスワードを自動的に新方式で再ハッシュするよう促す設定

- Q: 429エラーの意味はどこかに書いてある？デバッグが不安
- A: 429 = Too Many Requests（リクエスト過多）。コメントに補足を追記した。`detail`フィールドのメッセージがAPIレスポンスに含まれるのでデバッグ時はそちらで確認できる

## `models.py` — DBのテーブル定義

`database.py`で作った`Base`を継承して実際のテーブルをPythonのクラスとして定義するファイル。`users`テーブルと`analysis_results`テーブルの2つがある。

カラムとはDBのテーブルの「列」のこと。Excelで例えると行が1件のレコード、列がカラム。`mapped_column()`はSQLAlchemyが提供する関数で「このPythonの変数はDBの1つのカラムです」と定義するために使う。`Mapped[int]`はPythonの型ヒントで「このカラムはint型」とエディタやツールに伝える。

`mapped_column()`の主な引数：`Integer`・`String`・`Float`・`Boolean`などはSQLAlchemyの型クラスでDBでの型を指定する。
- `Mapped[int]`はPythonの型ヒント。「このカラムはint型」とエディタやツールに伝える
- `mapped_column()`の引数でDBの制約を指定する
  - `primary_key=True` — このカラムがテーブルの主キー（レコードを一意に識別するID）
  - `unique=True` — 同じ値を2件以上入れられない
  - `nullable=False` — NULLを許可しない（必須項目）
  - `index=True` — 検索を速くするためのインデックスを作る

`ForeignKey("users.id")`は「このカラムの値は`users`テーブルの`id`を参照する」という制約。存在しないユーザーIDは入れられなくなる。

`relationship()`はDBのカラムではなくPython上で「このUserに紐づく分析結果一覧」を取得できるようにする仕組み。`user.analysis_results`と書くだけでそのユーザーの全分析結果が取れる。文字列`"AnalysisResult"`で書くのはこの時点でクラスがまだ定義されていないため（前方参照）。`back_populates`で両クラスのリレーションを互いに紐付ける。

**疑問と回答:**
- Q: `sqlalchemy`は`SQLAlchemy`じゃなくていいのか？波線が出ている
- A: パッケージ名（import時）は小文字の`sqlalchemy`が正しい。波線はDockerの中にインストールされていてローカルのPythonには入っていないためで、動作には影響しない

- Q: `nullable=False`はユーザーが記述するということ？
- A: `song_title`は`nullable=False, default=""`なのでNULLは入れられないが、未入力なら空文字が入る。ユーザーが必ず入力しなくてもエラーにはならない

- Q: `disclaimer_accepted`はリーダブルコードの観点で分かりにくい
- A: コメント不足だった。「利用規約・免責事項への同意フラグ（登録時にTrueにする）」というコメントを追記して修正済み

---

## 開発者として動作確認する方法

フロントエンドが未完成でも、バックエンドのAPIが動いていれば動作確認できる。APIを直接呼ぶ方法として Swagger UI（`http://localhost:8080/docs`）やcurlがある。

curlはAPIを直接呼ぶコマンドラインツール。`-c cookies.txt` でブラウザ代わりにCookieを保存・送信できるため、「登録→ログイン→認証が必要なAPIを叩く」という一連の流れをフロントエンドなしで確認できる。ただしhttpOnly CookieはSwagger UIで扱いにくいため、認証周りの確認はcurlの方が向いている。

UIを目で確認したい場合はフロントエンドに直接アクセスしてアカウントを登録するのが最短。

**疑問と回答:**
- Q: アカウントを作らずに分析画面や統計画面に直接アクセスできないの？
- A: できない。`App.tsx`で `{screen === 'upload' && auth && <UploadScreen />}` のように `auth` がセットされていないと画面が描画されない仕組みになっているため

---

## Vite の proxy 設定

`localhost:5173`（フロントエンド）から `/api/...` を呼ぶとき、ブラウザは「5173番ポートに `/api` があるはず」と解釈する。実際のAPIは`localhost:8000`（バックエンド）にあるため、proxyでリクエストを転送する設定が必要。

`vite.config.ts` に `server.proxy` を設定することで「`/api` で始まるリクエストをバックエンドに転送する」ことができる。NginxがPort 80でやっていることと同じことをViteがPort 5173でやるイメージ。

**ハマりポイント：** Viteはコンテナ内で動いているため、proxy先のアドレスはホスト側の `localhost:8080` ではなくDocker内部のサービス名 `backend:8000` を指定する必要がある。`localhost` はコンテナ内では自分自身を指すため届かない。

```ts
server: {
  proxy: {
    '/api': 'http://backend:8000',
  },
},
```

---

## `.env` ファイルと SECRET_KEY

`echo "KEY=value" > .env` の `>` は「画面に出力する代わりにファイルに書き込む」リダイレクト。`echo` 自体は文字を出力するコマンドで、`>` でその出力先をファイルに変える。

`SECRET_KEY` はJWTトークンの署名に使う鍵。JWTは「このデータは本物のサーバーが作った」と証明するために署名が必要で、その署名に使う秘密の文字列が `SECRET_KEY`。値自体に特別な意味はなく「推測されにくい秘密の文字列」であればよい。本番環境ではランダムな文字列を使う。

`docker compose restart` は環境変数を再読み込みしない。`.env` を新しく作った後は `docker compose up -d` でコンテナを再作成する必要がある。

---

## passlib と bcrypt のバージョン互換性問題

`passlib 1.7.4` は起動時に bcrypt の動作確認テストとして内部で72バイト超のパスワードを使う。`bcrypt 4.x` からは72バイト超のパスワードをエラーにする仕様に変わったため、このテストで `ValueError` が発生してバックエンドごと落ちる。

`requirements.txt` で `bcrypt==4.0.1`（まだ厳格なチェックが入っていないバージョン）に固定することで回避。

---

## `backend/api/auth.py` — 認証APIエンドポイント

### JSON・パース・Pydantic・BaseModel

フロントエンドがバックエンドにデータを送るとき、次のような形式のテキストで送る。これが JSON。

```json
{ "email": "test@example.com", "password": "mypassword" }
```

「パース」とはこのテキストを読み解いて、Python が使えるデータに変換する操作のこと。JSON はただの文字列なので、そのままでは `email` や `password` を取り出せない。

Pydantic はパースとバリデーション（形式チェック）を自動でやってくれるライブラリ。`BaseModel` はその基底クラスで、継承したクラスを定義するだけでJSON の自動変換と入力チェックが使えるようになる。

```python
class RegisterRequest(BaseModel):
    email: EmailStr   # @がなければ自動でエラー
    password: str
```

FastAPI がリクエストを受け取ると JSON をこのクラスに変換し、以降は `body.email`・`body.password` でアクセスできる。

スキーマは入出力の役割で分かれている。
- `RegisterRequest` / `LoginRequest` — リクエスト（受け取るデータ）用
- `AuthResponse` — 登録・ログイン成功時のレスポンス用
- `UserResponse` — `/me` エンドポイントのレスポンス用（`disclaimer_accepted` が追加）

### `raise HTTPException` と `return` の違い

`return` は正常終了して値を返す。`raise` はエラーを発生させてそこで処理を中断する。`raise` した後の行は実行されない。

`HTTPException` は FastAPI が提供するエラー用クラス。`status_code` で HTTP ステータスコード、`detail` でエラーメッセージを指定する。この2つはただの引数なので `HTTPException` に渡すことで初めて「HTTPエラーレスポンスを返す」という意味を持つ。

```python
raise HTTPException(status_code=400, detail="パスワードは8文字以上で設定してください。")
```

### `disclaimer_accepted` とは

「免責事項・利用規約への同意フラグ」。サービス登録時に「利用規約に同意します」のチェックボックスに相当する。登録直後は同意画面をまだ見ていないため `False` で作り、将来同意画面を実装した際に `True` に更新する想定。

### `password_valid` とは

`verify_password` 関数が返す `True`/`False` を受け取る変数。「パスワードが有効か？」という意味。`True`/`False` を入れる変数には「〜は有効か？」「〜は正しいか？」という名前をつけるのが一般的。

### エンドポイントの全体像

| エンドポイント | 処理 |
|---|---|
| `POST /register` | ユーザー作成 → JWT を Cookie にセット → `201 Created` |
| `POST /login` | ロックアウト確認 → パスワード照合 → JWT を Cookie にセット |
| `GET /me` | Cookie の JWT を検証 → ログイン中ユーザー情報を返す |
| `POST /logout` | Cookie を削除 → `204 No Content` |

`response_model=AuthResponse` を指定すると、`User` モデルにある `hashed_password` など定義外のフィールドはレスポンスから自動除外される。パスワードが外部に漏れない仕組み。

`db.refresh(user)` は commit 後に DB から最新状態（自動採番された `id` など）を読み直す命令。commit するまで `user.id` が None のため必要。

ログアウトボタンをクリックすると `POST /api/v1/auth/logout` が送信され、このエンドポイントが Cookie を削除する。以降のリクエストには JWT が付かなくなりログアウト完了。

**疑問と回答:**
- Q: `HTTPException` がないと `status_code` と `detail` を書いてもうまく作動しない？
- A: そう。2つはただの引数で、`HTTPException` に渡すことで初めて「HTTPエラーレスポンスを返す」という動作になる

---

## `git merge` — マージコミットとnanoエディタ

`git merge`を実行すると、Gitは「なぜマージするか」を記録するためのマージコミットを作成する。
その際、コミットメッセージを編集させるためにデフォルトのエディタ（nanoなど）が自動で起動される。

デフォルトのメッセージ（`Merge branch 'main' of ...`）がすでに入っているので、
内容を変えたくない場合はそのまま保存して閉じるだけでよい。

**nanoの閉じ方:**
1. `Ctrl + X` を押す
2. `Enter` でファイル名確定 → マージ完了

**疑問と回答:**
- Q: なんで突然エディタが開くの？
- A: Gitがマージの理由をコミット履歴に残すため。自動で起動される。

**次回から確認画面をスキップしたい場合:**
```bash
git merge --no-edit
```
デフォルトメッセージをそのまま使い、エディタを起動しない

---

## `backend/api/analysis.py` — 音声分析APIエンドポイント

### ファイル全体の構造

```
analysis.py
├── エンドポイント（公開）
│   ├── POST /upload            — 音声ファイルをアップロードして分析
│   ├── GET  /user/statistics   — 統計情報を返す
│   └── GET  /{analysis_id}     — 特定の分析結果を1件取得
│
└── プライベート関数（_で始まる）
    ├── _validate_audio_file()   — ファイル形式チェック
    ├── _validate_file_size()    — ファイルサイズチェック
    ├── _run_analysis()          — 一時ファイルに書いて分析実行
    ├── _save_to_db()            — DB保存
    └── _calculate_growth_rate() — 成長率計算
```

エンドポイントをシンプルに保ち、処理はプライベート関数に切り出す構造になっている。

---

### import について

`from X import Y` は「Xというライブラリ・ファイルの中からYだけ取り出す」書き方。`import fastapi` とまるごとimportすることもできるが、使うものだけ名前で取り出す方が読みやすく、Pythonの慣習として標準的。パフォーマンスの差はほぼない。

**外部ライブラリ（自分では書いていない）**

| import | 何者か |
|---|---|
| `fastapi` | FastAPIフレームワーク本体 |
| `sqlalchemy` | ORM。DBをPythonで操作するためのライブラリ |

**自分たちのコード**

| import | どこにあるか |
|---|---|
| `AudioAnalyzer` | `backend/audio/analyzer.py` |
| `get_current_user` | `backend/auth_utils.py` |
| `get_db` | `backend/database.py` |
| `AnalysisResult, User` | `backend/models.py` |

**FastAPIからimportしているもの**

| 名前 | 役割 |
|---|---|
| `APIRouter` | URLのグループをまとめるクラス |
| `Depends` | 「この引数はこの関数から自動で取ってきて」という仕組み |
| `HTTPException` | エラーレスポンスを返すためのクラス |
| `UploadFile` | アップロードされたファイルを受け取るための型 |
| `File` | 「これはフォームのファイルです」と宣言する |

---

### FastAPI とは

WebサーバーのPythonフレームワーク。HTTPリクエストの受け取り・URLの解析・データの変換・レスポンスの返却など、自分で書かなくていい部分を全部やってくれる。

---

### デコレータ（`@`）とは

関数を受け取り、機能を追加した関数を返す仕組み。

```python
@router.post("/upload")
async def upload_audio(...):
    ...
```

これは以下と同じ意味：

```python
async def upload_audio(...):
    ...
upload_audio = router.post("/upload")(upload_audio)
```

`@router.post("/upload")` は「`upload_audio` 関数を POST /upload として登録する」処理。FastAPIがこれを見て「POST /upload が来たら `upload_audio` を呼び出す」と覚える。

`router.post()` / `router.get()` などはFastAPIがあらかじめ `APIRouter` クラスに用意しているメソッドで、自分で作るものではない。

---

### POST と GET の違い

HTTPの規格で決まっているもの。自分で名前を決めるのではなく最初から決まっている。

| メソッド | 用途 |
|---|---|
| POST | データを送信して何かを実行する（アップロード・登録・ログイン） |
| GET | データを取得する（結果を見る・一覧を見る） |

---

### APIバージョン（`/api/v1/`）

URLに `v1` が含まれているのはAPIのバージョン番号。将来APIの仕様を大きく変えたくなったとき、既存ユーザーを壊さずに新しいバージョンを出せるようにするための備え。現時点ではv1しかないが、慣習として最初から書いておく。

---

### ルーターの初期化とアナライザーの起動（16〜19行目）

```python
router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
audio_analyzer = AudioAnalyzer()
```

- `prefix="/api/v1/analysis"` — このルーターに登録する全URLの先頭に自動でこの文字列がつく。`@router.post("/upload")` と書くと実際のURLは `/api/v1/analysis/upload` になる
- `tags=["analysis"]` — Swagger UIでエンドポイントをグループ分けして表示するためのラベル。動作には影響しない
- `audio_analyzer = AudioAnalyzer()` — グローバルスコープに置いているためサーバー起動時に1回だけ実行される。Demucsモデルのロードが重いため毎リクエストごとに実行しないようにする工夫

**Swagger UI** とはFastAPIが自動で生成するAPIのドキュメントページ兼テスト画面。`http://localhost:8080/docs` でブラウザから確認できる。

---

### `upload_audio` 関数（22〜50行目）

```python
@router.post("/upload")
async def upload_audio(
    audio_file: UploadFile = File(...),
    song_title: str = "",
    artist_name: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
```

- `POST /upload` が来たら `upload_audio` が実行される
- `audio_file` — アップロードされたファイル。`UploadFile` はFastAPIが提供するクラスで `.read()` や `.filename` などのメソッドを持つ
- `song_title` / `artist_name` — フロントエンドからフォームデータとして送られてくるテキスト
- `db: Session = Depends(get_db)` — FastAPIがリクエストのたびに自動で `get_db()` を呼んでDBセッションを作って渡してくれる。`db` を通してDBの検索・保存・確定などの操作を行う
- `current_user: User = Depends(get_current_user)` — CookieのJWTを検証して誰がリクエストしてきたかを特定して渡してくれる

**処理の流れ（37〜50行目）：**

```python
_validate_audio_file(audio_file)      # ① ファイル形式チェック
content = await audio_file.read()     # ② ファイルをメモリに読み込む
_validate_file_size(content)          # ③ ファイルサイズチェック
analysis_data = _run_analysis(...)    # ④ 音声分析を実行
saved = _save_to_db(...)              # ⑤ 分析結果をDBに保存
return { "analysis_id": ..., ... }   # ⑥ 結果を返す
```

①→②→③の順番に意味がある。読み込む前にサイズチェックはできないのでこの順番になっている。

**`await` について：**

`await` は「この処理が終わるまで待つ」という意味。`await` なしだと読み込みが終わる前に次の行に進んでしまう。ファイルの読み込みやDB操作など「外部とやりとりする処理（I/O操作）」は時間がかかるため `await` が必要。CPUの計算だけで完結する処理には不要。

**I/O操作（Input/Output）：** プログラムの外とデータをやりとりする処理の総称。ファイルの読み書き・ネットワーク通信・DB操作などが該当する。

---

### JSON とは

フロントエンドとバックエンドは別々のプロセスで動いており、HTTPという**テキストの通信**でしかやりとりできない。PythonのdictやJavaScriptのオブジェクトはそのまま送れないため、一度テキストに変換して送り、受け取った側がまたオブジェクトに戻す手順が必須。そのテキストフォーマットがJSON。

```
JavaScript側               HTTP通信（テキスト）             Python側
{ email: "test@..." }  →  '{"email":"test@..."}'  →  body.email
```

FastAPIとPydanticがこの変換を自動でやってくれる。

---

### `get_user_statistics` 関数（53〜87行目）

ログインユーザーの全分析結果を集計してダッシュボード用の統計情報を返す。

**DBからデータ取得（63〜68行目）：**

```python
results = (
    db.query(AnalysisResult)
    .filter(AnalysisResult.user_id == current_user.id)
    .order_by(AnalysisResult.created_at.asc())
    .all()
)
```

- `.query(AnalysisResult)` — `analysis_results` テーブルを対象にする
- `.filter(...)` — ログイン中のユーザーのものだけに絞る
- `.order_by(AnalysisResult.created_at.asc())` — 作成日時の古い順に並べる
  - `asc()` は ascending（昇順）の略。古い順（1月→2月→3月）
  - 反対は `desc()`（降順）。新しい順
- `.all()` — 条件に合う全レコードをリストとして取得する

**`history` リストの作成（70〜77行目）：**

```python
history = [
    {
        "date": record.created_at.strftime("%m/%d"),
        "pitch": round(record.pitch_accuracy) if record.pitch_accuracy is not None else 0,
        "rhythm": round(record.rhythm_score) if record.rhythm_score is not None else 0,
    }
    for record in results
]
```

`results` の全レコードを1件ずつ処理してグラフ表示用のデータに変換したリスト。`for record in results` で1件ずつ `record` に入れて繰り返す。

- `strftime("%m/%d")` — datetime型を「月/日」形式の文字列に変換するPythonの標準関数
- `if ... is not None else 0` — 分析結果が取れなかった場合に `None` が入る可能性があるため、`None` なら `0` にする

**`return` の内容（82〜87行目）：**

- `len(history)` — Pythonの組み込み関数。リストの件数を返す
- `max(pitch_values) if pitch_values else 0` — `max()` は最大値を返す組み込み関数。空リストだとエラーになるので空の場合は `0` を返す
- `growth_rate` — `_calculate_growth_rate()` で計算した成長率

---

### `get_analysis` 関数（90〜119行目）

指定したIDの分析結果を**1件だけ**取得して返す。`/user/statistics` が全件まとめて統計にするのに対してこちらは1件のみ。

`{analysis_id}` はURLの中に変数を埋め込む書き方。`GET /api/v1/analysis/5` とアクセスすると `analysis_id = 5` として関数に渡される。

**2段階のチェック（102〜106行目）：**

```python
result = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
if result is None:
    raise HTTPException(status_code=404, ...)  # 存在しない
if result.user_id != current_user.id:
    raise HTTPException(status_code=403, ...)  # 他人のデータ
```

- `.first()` — 条件に合う最初の1件を返す。存在しなければ `None`
- 404 — 指定したIDのレコードがDBに存在しない
- 403 — レコードは存在するが他のユーザーのもの

---

### プライベート関数

#### `_validate_audio_file`

**型ヒント：** `audio_file: UploadFile` は「この引数には `UploadFile` 型のデータが入りますよ」とPythonやエディタに伝えるための書き方。`-> None` は「この関数は何も返しません」という意味。型ヒントを書かなくても動作は変わらない。

**MIMEタイプ：** ファイルの種類を表すインターネットの標準規格。ブラウザがアップロード時に自動でセットする。

| MIMEタイプ | ファイル形式 |
|---|---|
| `audio/wav` | WAV |
| `audio/mpeg` | MP3 |
| `audio/mp4` | M4A |
| `audio/x-m4a` | M4A（別表記） |

#### `_validate_file_size`

```python
max_size = 50 * 1024 * 1024
```

単位の変換。`len(content)` はバイト単位で返るため50MBをバイトに変換している。

```
1KB = 1024バイト
1MB = 1024 * 1024バイト
50MB = 50 * 1024 * 1024 = 52,428,800バイト
```

`50000000` と直書きより `50 * 1024 * 1024` の方が「50MBという意図」が読んだ人に伝わる。リーダブルコードの考え方。

#### `_run_analysis`

```python
suffix = os.path.splitext(filename)[1]
with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
    tmp.write(content)
    tmp_path = tmp.name

try:
    result = audio_analyzer.analyze(tmp_path)
    ...
finally:
    os.unlink(tmp_path)
```

- `os.path.splitext("song.m4a")` → `("song", ".m4a")` — ファイル名を名前と拡張子に分割するPythonの標準関数。`[1]` で拡張子だけ取り出す
- `tempfile.NamedTemporaryFile()` — OSの一時ファイル置き場（Linuxでは `/tmp`）に空のファイルを作る標準関数
  - `suffix=suffix` — 拡張子を指定する。librosaがファイル形式を判別するために必要
  - `delete=False` — `with` ブロックを抜けてもファイルを自動削除しない。後で `analyze()` がそのファイルを読む必要があるため
- **`with` ブロック** — ブロックを抜けると自動でファイルが閉じられる。閉じ忘れを防ぐ構文。`as tmp` でブロック内でそのファイルを操作するための変数名をつける
- `try/finally` — tryの中でエラーが起きても起きなくても `finally` は必ず実行される。分析が成功しても失敗しても一時ファイルを削除するために使っている
- `os.unlink(tmp_path)` — ファイルを削除するPythonの標準関数。著作権保護のため分析後は即削除する仕様

**OS（Operating System）とは：** コンピュータ上で動く全ソフトウェアの土台。WindowsやmacOS、Linuxがそれにあたる。DockerコンテナはLinuxで動いており、デプロイ先のクラウドサーバーもLinuxなので `_run_analysis` の処理はどこでも同じように動く。

#### `_save_to_db`

`AnalysisResult` クラスに値を渡してインスタンスを作り、`db.add()` でDBに追加、`db.commit()` で確定する。`db.refresh(record)` は `commit()` 後にDBが自動採番した `id` を取得するために必要。

#### `_calculate_growth_rate`

```python
def _calculate_growth_rate(pitch_values: list[float]) -> int:
    if len(pitch_values) < 2 or pitch_values[0] == 0:
        return 0
    growth = ((pitch_values[-1] - pitch_values[0]) / pitch_values[0]) * 100
    return round(growth)
```

- `list[float]` / `-> int` — 型ヒント。変換は何もしていない。「引数はfloatのリスト、戻り値はint」とエディタに伝えるだけ
- `len(pitch_values) < 2` — 2件未満は最初と最後の比較ができないので `0` を返す
- `pitch_values[0] == 0` — 最初のスコアが0だと次の行で「0で割る」計算が発生してエラーになるので先に弾く
- `pitch_values[-1]` — Pythonでリストの最後の要素を取り出す書き方
- 成長率の計算式 → `(最新 - 最初) / 最初 × 100`
- `round(growth)` — 小数点以下を四捨五入して整数で返す

---

## `audio/analyzer.py` — 音声分析の司令塔

このファイルは音声分析の「司令塔」。自分では分析処理を持たず、3つの専門モジュールを組み合わせて結果を作る。

```
AudioAnalyzer（司令塔）
├── VocalSeparator    → 音源分離（ボーカルを取り出す）
├── PitchDetector     → ピッチ検出（音程を測る）
└── TechniqueDetector → 歌唱技法検出（ビブラートなどを判定）
```

### `__init__` メソッド

`__init__` はクラスのインスタンスを作るときに自動で呼ばれる初期化メソッド。`AudioAnalyzer()` と書いた瞬間に動き、3つのモジュールが `self` に紐づいた状態で準備される。

`self` は「このインスタンス自身」を指す変数。`self.separator` に入れることで、後から `self.separator.separate(...)` と呼び出せる。

`analysis.py` でグローバルに `audio_analyzer = AudioAnalyzer()` しているのでサーバー起動時に1回だけ `__init__` が動く。

### `analyze` メソッドの処理フロー

```
① separate()             — 音源分離（ボーカル抽出）
② detect()               — ピッチ検出
③ detect_all()           — 歌唱技法検出
④ calculate_accuracy()
   _calculate_rhythm_score() — スコア計算
⑤ _generate_feedback()   — フィードバック文章生成
```

結果は辞書（dict）で返す。`analysis.py` の `_run_analysis()` がこの戻り値を受け取ってDBに保存する。

### スタブメソッド（3つ）

`_calculate_vocal_range` / `_calculate_rhythm_score` / `_generate_feedback` の3つは `# TODO:` コメントのスタブ。固定値・固定文字列を返すだけで本実装はPhase 7以降の予定。

### 疑問と回答

- Q: `self.separator.separate()` の `separate` はPythonの組み込み機能？
- A: 違う。`VocalSeparator` クラスの中に自分たちで定義したメソッド。`self.separator` は `VocalSeparator` のインスタンスで、`separate` はそのクラス内で定義した関数。`list.append()` などはPythonが用意したメソッドだが、自分で作ったクラスのメソッドは全部自分で定義する必要がある

---

## `audio/separator.py` — 音源分離モジュール（現在スタブ）

### このファイルの役割

カラオケ録音からボーカルだけを取り出す処理を担当する。本来はDemucs v4というAIモデルで音源分離するが、CPU処理が遅すぎるため現在はスタブになっている（Phase 7で本実装予定）。

### import

- **numpy（`np`）** — 数値計算ライブラリ。音声データは数値の配列として扱うため必須。`np` という短い名前で使うのが慣習
- **librosa** — 音声処理ライブラリ。音声ファイルの読み込み・特徴抽出などに使う

### `separate` メソッドの処理

**① `librosa.load()` で音声ファイルを読み込む**

```python
audio, sample_rate = librosa.load(audio_path, sr=None, mono=False)
```

- カンマで2つの変数に受け取る書き方は「タプルのアンパック」。`librosa.load()` が2つの値を返すのでそれぞれに代入される
- `sr=None` — 元のサンプリングレートをそのまま使う（librosaのデフォルトは22050Hzに変換するため、それを防ぐ指定）
- `mono=False` — ステレオ（左右2チャンネル）のままで読み込む

**② モノラルなら2次元に変換する**

```python
if audio.ndim == 1:
    audio = audio[np.newaxis, :]
```

- `ndim` はnumpyの配列が持つ属性で「次元数」を返す
  - モノラル → `[サンプル, サンプル, ...]` → `ndim = 1`（1次元）
  - ステレオ → `[[左, ...], [右, ...]]` → `ndim = 2`（2次元）
- `== 1` は「モノラルだったら」という条件
- `np.newaxis` は「ここに新しい次元を追加する」という意味のnumpyの特殊な値
  - 変換前: `[1, 2, 3, 4]` → shape=(4,)（1次元）
  - 変換後: `[[1, 2, 3, 4]]` → shape=(1, 4)（2次元）
- `:` は「残りの次元はそのまま」というスライス記法
- 後続の `PitchDetector` が「チャンネル数 × サンプル数」の2次元配列を前提にしているため、モノラルでも形を揃える

**③ スタブとして音声をそのまま返す**

- `vocals` には元の音声をそのまま入れる（分離していない）
- `drums` / `bass` / `other` は `np.zeros_like(audio)`（同じ形のゼロ配列）を返す
- 本番ではDemucsが4トラックを本当に分離して返す予定

### サンプリングレートについて

| ツール | 種類 | 適切なサンプリングレート |
|---|---|---|
| **librosa** | 音声処理ライブラリ（読み込み・特徴抽出） | 元のレートのまま（`sr=None`）が基本 |
| **Crepe** | ピッチ検出モデル | 16000 Hz |
| Whisperなど | 音声認識AIモデル | 16000 Hz |

librosaはAIモデルではなく「音声ファイルを読み込んで処理する道具」。`sr=None` で元のレートを保持するのは正しい。Crepeに渡す際は `pitch.py` の中で16000 Hzにリサンプリングする。

---

## `audio/pitch.py` — ピッチ検出モジュール

### このファイルの役割

ボーカルトラックの音声データを受け取り「どの時点でどの音程を歌っていたか」を検出するモジュール。Crepeというピッチ検出に特化したAIモデルを使う。

### `__init__`

`pass` は「何もしない」という意味のキーワード。Crepeは `import crepe` した時点で自動的にモデルをメモリに読み込むため `__init__` で特別な初期化は不要。

### `detect` メソッド

**引数の型ヒント：**
- `np.ndarray` — numpyの配列型。`separator.py` の `librosa.load()` が返す `audio` は内部的にnumpyの配列として作られており、それが渡されてくる。型ヒントはその型を宣言しているだけ
- `sample_rate: int = 44100` — デフォルト値つきの引数。呼び出し側が省略したら44100が使われる

**ステレオ→モノラル変換：**

Crepeはモノラルのデータしか受け付けない。ステレオの場合は左右の平均を取って変換する。

```python
vocals_as_mono = vocals.mean(axis=0)
```

`axis=0` は「0番目の軸（チャンネル方向）で平均を取る」という意味。

```
ステレオ: [[左1, 左2, ...], [右1, 右2, ...]]  shape=(2, N)
        ↓ axis=0 で平均
モノラル: [平均1, 平均2, ...]                  shape=(N,)
```

**`crepe.predict()` の戻り値：**

`vocals_as_mono` はあくまで入力。`crepe.predict()` は4つの値を返す。

| 変数 | 中身 | 例 |
|---|---|---|
| `times` | 各フレームの時刻（秒） | `[0.0, 0.01, 0.02, ...]` |
| `frequencies` | 各時刻で検出した音程（Hz） | `[440.2, 441.0, 439.8, ...]` |
| `confidence` | 各時刻での検出の自信度（0〜1） | `[0.9, 0.85, 0.3, ...]` |
| `_` | 内部の活性化マトリクス（使わない） | 捨てる |

「0.01秒ごとに音程を測定した結果の一覧」が3つの配列として返ってくるイメージ。`viterbi=True` は `frequencies` の推定をより滑らかにするオプションで特定の変数に格納されるわけではない。

**`.tolist()` でリストに変換：**

numpyの配列（`ndarray`）はそのままではJSONに変換できない。`.tolist()` でPythonのリストに変換してから返す。

### `calculate_accuracy` メソッド

**信頼度フィルタ（82〜88行目）：**

```python
is_confident = confidence > 0.5
reliable_frequencies = frequencies[is_confident]
```

`confidence > 0.5` は配列全体に一括で比較演算をかけて `True/False` の配列を作り、それをインデックスとして使って信頼できるデータだけ抽出する。

```
frequencies:  [440, 450, 200, 445]
is_confident: [True, True, False, True]
結果:         [440, 450, 445]  ← Falseの200が除外される
```

**HzをMIDIノート番号に変換（91行目）：**

MIDIノート番号は音程を数値で表す規格（例：ラ4 = 440Hz = 69）。Hzのままだと音程のズレを計算しにくいため変換する。

**半音内のズレで安定性を計算（95〜96行目）：**

MIDIノート番号の小数部分（`% 1`）は「一番近い音程からのズレ」を表す。`np.std()` は標準偏差で「値のばらつき具合」を数値化する。ばらつきが小さいほどピッチが安定＝スコアが高い。

---

## `audio/techniques.py` — 歌唱技法検出モジュール

### このファイルの役割

`pitch.py` が「どの音程を歌っているか（Hz）」を測るのに対して、このファイルは「どんな歌い方をしているか（技法）」を判定する担当。

```
pitch.py        → 音程データ（時刻・Hz・自信度）を出力
techniques.py   → そのデータを受け取り、5つの技法を判定
```

| 技法 | 説明 |
|---|---|
| ビブラート | 音を細かく揺らす歌い方 |
| こぶし | 短時間で音を急激に変化させる |
| フォール | 音の終わりで音程を下げる |
| しゃくり | 音の始まりで音程を下から上げてくる |
| ロングトーン | 長い音を安定して伸ばす |

### クラス構造

```python
class TechniqueDetector:
    def detect_all(...)       ← 5つをまとめて呼ぶ「窓口」
    def detect_vibrato(...)
    def detect_kobushi(...)
    def detect_fall(...)
    def detect_shakuri(...)
    def detect_long_tone(...) ← 個別の検出メソッド
```

`detect_all` は5つの個別メソッドを呼び出して辞書にまとめて返す。呼び出し側（`analyzer.py`）は1回呼ぶだけで全結果が取れる。

`__init__` は書いていない。初期化時に必要なものがないため、Pythonが自動で用意するデフォルトの `__init__` で十分。

### 各メソッドの返り値

```python
# ビブラート
{"count": 0, "avg_frequency": 0.0, "avg_depth": 0.0, "gratuitous_count": 0}
# count           → 検出回数
# avg_frequency   → 揺れの速さ（Hz）
# avg_depth       → 揺れの深さ（cent）
# gratuitous_count → 加点目的と判定されたビブラートの回数（旋律のない区間のみ）

# こぶし
{"count": 0, "timestamps": []}
# timestamps → 発生した時刻のリスト（例: [1.2, 3.5, 5.0]）

# フォール
{"count": 0, "avg_depth": 0.0}
# avg_depth → 平均でどれくらい音程を下げたか（cent）

# しゃくり
{"count": 0, "avg_height": 0.0}
# avg_height → 平均でどれくらい音程を上げてくるか（cent）

# ロングトーン
{"count": 0, "avg_duration": 0.0, "avg_stability": 0.0}
# avg_duration  → 平均持続時間（秒）
# avg_stability → ピッチの安定度（0〜100）
```

**cent（セント）とは？** 音楽の音程の単位。半音 = 100 cent。

### スタブとTODO

全メソッドが `# TODO:` コメントのスタブで、現在はゼロを返すだけ。Phase 7で本実装予定。

**FFT（Fast Fourier Transform / 高速フーリエ変換）とは？** 音や信号の「周期的なパターン」を数値で取り出す数学的手法。ビブラートは定期的に音程が揺れる現象なのでFFTで検出する。

### ビブラートのスコア設計方針

| 区間 | ビブラート | 扱い |
|---|---|---|
| 歌唱中（旋律あり） | あり | 加点（アレンジとして評価） |
| 間奏など（ピッチ変化ほぼゼロの無声区間） | あり | `gratuitous_count` にカウント → 減点 |

**課題（Phase 7で検証）:** 間奏中のおしゃれなアドリブ・装飾的なビブラートも「無声区間」として拾ってしまうリスクがある。しきい値の調整とテストで「アレンジは通る・加点稼ぎは弾く」をどこまで分けられるか確認する。

---

---

## `Dockerfile` — コンテナの設計図

バックエンド（`backend/Dockerfile`）とフロントエンド（`frontend/Dockerfile`）の2つがある。

### 命令の一覧

| 命令 | 役割 |
|---|---|
| `FROM` | ベースイメージを指定。コンテナの土台となるOS+ランタイム環境 |
| `WORKDIR` | 作業ディレクトリを設定。以降の命令はここを起点に実行される |
| `RUN` | ビルド時にコマンドを実行する |
| `COPY` | ホスト（自分のPC）のファイルをコンテナ内にコピーする |
| `CMD` | コンテナ起動時に実行するコマンドを指定する |

---

### `apt-get install` と `-y`

`apt-get` はLinuxにシステムツールをインストールするコマンド。`pip`（Pythonライブラリ）や`npm`（JSパッケージ）と「名前を指定するとネットからダウンロードしてインストールしてくれる」点が同じで、対象が違うだけ。

| コマンド | 対象 |
|---|---|
| `apt-get` | ffmpeg・gitなどLinuxのシステムツール |
| `pip` | FastAPI・crepeなどPythonのライブラリ |
| `npm` | React・ViteなどJavaScriptのパッケージ |

通常 `apt-get install` は途中で確認メッセージ（`Do you want to continue? [Y/n]`）を出す。Dockerのビルドは自動実行なので誰も答えられず止まってしまう。`-y` は「全部Yesで答えてね」という自動承認フラグ。

---

### `\` と `&&` の組み合わせ

`\` は「この行はまだ続きますよ」という行継続の記号。実体は1行のコマンドを読みやすく折り返しているだけ。

```dockerfile
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

↑ これは以下と全く同じ意味：

```
RUN apt-get update && apt-get install -y build-essential ffmpeg && rm -rf /var/lib/apt/lists/*
```

**なぜ `&&` でつなぐのか：** Dockerは `RUN` を1行書くたびにレイヤー（層）が1つ増え、イメージが重くなる。`&&` でつなぐと関連する処理を1レイヤーにまとめられる。

---

### `--no-cache-dir` とイメージサイズ削減

`pip install crepe` を実行すると内部で3ステップ動く：

```
① crepe の wheel ファイル（インストーラー）をネットからダウンロード
② それを Python の site-packages/ に展開（← ライブラリ本体。ここに残る）
③ ダウンロードした wheel ファイルを /root/.cache/pip/ に保存（← キャッシュ）
```

キャッシュは「また同じライブラリを再インストールするときのための控え」。商品（ライブラリ本体）は棚に並んでいる。伝票（キャッシュ）は再注文用の控え。

Dockerコンテナは使い捨てなので再インストールは発生しない。伝票だけが場所を取るので `--no-cache-dir` で「キャッシュを保存しないで」と指示してサイズを削減する。

---

### `rm -rf /var/lib/apt/lists/*` とパッケージ一覧ファイル

`apt-get update` は「今インストールできるツールの一覧をサーバーから取ってくる」コマンド。

```
apt-get update 実行
  → Ubuntuの配布サーバーにアクセス
  → 「ffmpeg 6.0がある」「git 2.4がある」... という一覧をダウンロード
  → /var/lib/apt/lists/ に保存
```

`apt-get install ffmpeg` はこの一覧を見て「ffmpegはどのURLにあるか」を確認してダウンロードする。インストールが終わったら一覧ファイルは用済みなので削除する。

**重要：同じ `RUN` の中で削除しないと意味がない。**

```dockerfile
# NG: 別の RUN で消しても前のレイヤーに一覧ファイルが焼き込まれたまま
RUN apt-get update && apt-get install -y ffmpeg
RUN rm -rf /var/lib/apt/lists/*

# OK: 同じ RUN の中で作ってその場で削除する
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

レイヤーは一度確定すると変更できないため「作ったその場で片付ける」必要がある。

---

### Dockerのレイヤーキャッシュ（ビルド高速化）

各命令の結果はキャッシュされ、変更がなければ再実行しない。変化が少ないもの → 変化が多いものの順に書くことでキャッシュが効く。

```dockerfile
COPY requirements.txt .     ← 変化が少ない（ライブラリ追加時だけ変わる）
RUN pip install ...          ← requirements.txtが変わらなければキャッシュが使われる
COPY . .                    ← 変化が多い（コードを1行変えるたびに変わる）
```

コードを1行修正しただけで `pip install` からやり直しにならない工夫。

---

### フロントエンドの `package*.json` のワイルドカード

`*` は「0文字以上の任意の文字列」にマッチする記号。

```
package*.json にマッチするファイル：
  package.json        ← * の部分が空文字（0文字）
  package-lock.json   ← * の部分が「-lock」
```

| ファイル | 役割 |
|---|---|
| `package.json` | 「どんなライブラリが必要か」の宣言。人間が書く |
| `package-lock.json` | 「実際にインストールしたライブラリの正確なバージョン」の記録。`npm install` が自動生成 |

`package-lock.json` があることでチームや本番サーバーでも全く同じバージョンが入る。`COPY package*.json ./` と1行で両方まとめてコピーできる。

---

---

## `requirements.txt` — Pythonライブラリの依存関係

`pip install -r requirements.txt` で一括インストールされるライブラリの一覧。`==` でバージョンを固定することでチームや本番環境で全く同じバージョンが入るようにしている。

### ORM とは

**Object-Relational Mapper** の略。DBのテーブルをPythonのクラスとして扱えるようにする仕組み。

```python
# ORM なし（生SQL）
db.execute("SELECT * FROM users WHERE id = 1")

# ORM あり（SQLAlchemy）
db.query(User).filter(User.id == 1).first()
```

SQL文字列を書く代わりにPythonコードでDB操作を書ける。タイプミスによるSQLエラーが減り、エディタの補完も効く。

### DBマイグレーションツール（alembic）とは

テーブル定義の「変更履歴を管理する」ツール。コードは `git` で管理できるが、DBのテーブル構造はそのままでは管理できない。alembicは変更を履歴ファイルとして保存し `upgrade` / `downgrade` で前後に移動できる。

```
v1: users テーブル作成
v2: hashed_password カラム追加  ← git みたいに差分で管理
v3: user_id を NOT NULL に変更
```

### bcrypt アルゴリズムとは

パスワードのハッシュ化に特化したアルゴリズム。ハッシュ化とは「元に戻せない一方向の変換」で、DBにはパスワード本体を保存しない。ログイン時は「入力値を同じ方法でハッシュ化して一致するか確認する」。

SHA-256など他のハッシュ関数は高速だが、パスワードには逆効果。高速 = 攻撃者が総当たりしやすくなる。bcryptは**意図的に計算を遅く**して総当たり攻撃を現実的でなくしている。

### `[bcrypt]` エクストラとは

`passlib` 単体はハッシュ化の「共通インターフェース」だけを持ち、実際のアルゴリズムは別ライブラリ。

```
passlib           ← 「verify_password()を呼んだら検証する」という枠組み
  └── [bcrypt]   ← bcrypt の具体的な計算実装を追加インストール
```

`passlib[bcrypt]` と書くことでpasslibと一緒にbcryptの実装も入る。`bcrypt==4.0.1` を別行で固定しているのは互換性問題への対処（4.1以降はpasslibのテストで ValueError が発生するため）。

### Pydantic とは

Pythonの**データ検証・型変換ライブラリ**。フロントエンドからJSONが届いたとき「形式は正しいか・必須項目が揃っているか・メールアドレスの形式か」を自動チェックしてくれる。FastAPIと統合されており、リクエストのJSONを自動でクラスに変換・検証する。

```python
class RegisterRequest(BaseModel):
    email: EmailStr   # @がなければ自動でエラー
    password: str     # 文字列でなければ自動でエラー
```

### PyTorch とは

Facebookが開発した**ディープラーニングフレームワーク**。AIモデルの学習・推論を行う計算基盤。DemucsとCrepeはどちらもPyTorchまたはTensorFlowの上で動いている。

```
torch（PyTorch）   ← 数値計算・AI推論の土台（Facebook開発）
  └── Demucs      ← 音源分離AIモデル（PyTorchで動く）

TensorFlow        ← 同じくAI計算基盤（Google開発）
  └── Crepe       ← ピッチ検出AIモデル（TensorFlowで動く）
```

### `torch` と `torchaudio` を別々に入れる理由

役割が分かれているため。

| ライブラリ | 役割 |
|---|---|
| `torch` | PyTorch本体。テンソル（多次元数値配列）の計算・AI推論全般 |
| `torchaudio` | 音声データ専用の拡張。音声ファイルの読み込み・変換・前処理 |

`torchaudio` は `torch` がないと動かない依存関係にある。音声処理に特化した機能は `torch` 本体に入っておらず、Demucsが音声を扱うために `torchaudio` の機能を使うため両方必要。

### ライブラリ役割まとめ

| ライブラリ | 役割 |
|---|---|
| `fastapi` | WebフレームワークAPI本体 |
| `uvicorn` | FastAPIを動かすWebサーバー |
| `python-multipart` | ファイルアップロード処理。`UploadFile` の動作に必要 |
| `sqlalchemy` | ORM |
| `psycopg2-binary` | PythonからPostgreSQLに接続するドライバ（`-binary` はビルド環境不要の版） |
| `redis` | PythonからRedisに接続するライブラリ |
| `alembic` | DBマイグレーションツール |
| `python-jose[cryptography]` | JWT生成・検証（CVEあり、将来PyJWTへ切替予定） |
| `passlib[bcrypt]` | パスワードのハッシュ化インターフェース |
| `bcrypt==4.0.1` | bcrypt実装本体（4.0.1に固定して互換性問題を回避） |
| `pydantic[email]` | リクエストのバリデーション。`[email]` でメールアドレス検証が使える |
| `pydantic-settings` | 環境変数を型付きで管理するpydantic拡張 |
| `librosa` | 音声ファイルの読み込み・音響特徴抽出 |
| `numpy` | 数値計算。音声データは数値の配列なので全処理の土台 |
| `soundfile` | librosaが音声ファイルを読む際に内部で使うデコーダ |
| `resampy` | 音声のリサンプリング（サンプリングレート変換） |
| `demucs` | 音源分離AIモデル（現在スタブ。Phase 7で本番復帰予定） |
| `hmmlearn` | Demucsが内部で使う統計モデルライブラリ |
| `torch` / `torchaudio` | DemucsとCrepeが使うPyTorch本体と音声処理拡張 |
| `tensorflow` | Crepeが使うディープラーニングフレームワーク |

**crepeがここにない理由：** Dockerfileで `--no-deps` で先にインストールしているため。`requirements.txt` に入れると依存関係チェックでhmmlearnと衝突する。

---

---

## `alembic/` — DBマイグレーション管理

### ファイル構成

```
alembic/
├── env.py                                              ← マイグレーション実行の設定ファイル
├── script.py.mako                                      ← 新しいマイグレーションファイルのテンプレート
└── versions/
    ├── 62b066d20808_create_initial_tables.py           ← v1: テーブル作成
    └── a1b2c3d4e5f6_add_hashed_password_to_users.py   ← v2: カラム追加
```

### マイグレーションの全体像

`versions/` の各ファイルが「1回の変更」に対応する。gitのコミット履歴と同じイメージ。

```
None → 62b066d20808 → a1b2c3d4e5f6
         ↑ v1               ↑ v2
   テーブル作成        カラム追加
```

各ファイルに `upgrade()`（進む）と `downgrade()`（戻る）の2つが必ずあり、前後どちらにも移動できる。

### `down_revision` による連鎖

```python
revision: str = 'a1b2c3d4e5f6'       # このマイグレーション自身のID
down_revision: str = '62b066d20808'   # 1つ前のマイグレーションのID
```

`down_revision` で「どのファイルの次か」を繋ぐ。v1 の `down_revision` は `None`（先頭）。Alembicはこの連鎖を辿って順序を把握する。

### nullable とは

「NULLを入れてもいいか」のフラグ。NULLとは「値が存在しない」という状態。

```python
nullable=True   # 値なしでもOK（任意項目）
nullable=False  # 必ず値が必要（必須項目）
```

### 外部キー制約とは

`analysis_results.user_id` は「`users.id` に存在する値しか入れられない」という制約。存在しないユーザーIDを持つ分析結果は作れないようにする。

この制約があるため、テーブルを削除する順番に制限がある。

```python
# NG: users を先に消すと analysis_results が存在しない users.id を参照する状態になりエラー
# OK: 参照している側（analysis_results）を先に消す
drop_table('analysis_results')
drop_table('users')
```

### v2: `server_default=''` について

`nullable=False` のカラムを追加するとき、すでにDBに入っているレコードには値がない。`server_default=''` で「既存レコードには空文字を入れる」と指定することでエラーを防いでいる。

### Pythonインタープリタとは

`python main.py` と打ったとき、ファイルを読んでコードを実行する「翻訳・実行係」のプログラム。コンピュータはPythonのコードをそのまま理解できないため、CPUが理解できる命令（機械語）に変換しながら1行ずつ実行する。

```
main.py（人間が書いたコード）
    ↓ Pythonインタープリタが翻訳・実行
CPUが理解できる命令
```

### `os` と `sys` の違い

| モジュール | 役割 | このファイルでの用途 |
|---|---|---|
| `os` | ファイル・環境変数の操作 | `os.environ.get("DATABASE_URL")` で環境変数を取得 |
| `sys` | Pythonインタープリタ自体の設定・状態 | `sys.path` でimportの検索先ディレクトリを追加 |

`sys.path` は「importするとき、どのディレクトリを探すか」というリスト。`sys.path.insert(0, '/app')` でリストの先頭に追加することで、`env.py` から別ディレクトリにある `models.py` を見つけられるようにしている。

### `from pathlib import Path`

`Path` はファイルパスを扱うクラス。

```python
Path(__file__).resolve().parent.parent
# __file__    → 今実行中のファイル自身のパス（/app/alembic/env.py）
# .resolve()  → 相対パスを絶対パスに変換
# .parent     → 1つ上（/app/alembic）
# .parent     → さらに1つ上（/app）
```

文字列で `"../../"` と書くより意図が明確で、OSによるパスの違いも吸収してくれる。

### `from logging.config import fileConfig`

**logging** はプログラムの動作記録（ログ）を出力する仕組み。`fileConfig` は `alembic.ini` に書かれたログ設定を読み込む関数。マイグレーション実行中に「どのSQLが実行されたか」などをコンソールに表示するために使われる。

### `Base` とは

`database.py` で定義した基底クラス。

```python
# database.py
class Base(DeclarativeBase):
    pass
```

`DeclarativeBase`（SQLAlchemyが提供）を継承した `Base` をさらに継承することで「このクラスはDBのテーブルです」とSQLAlchemyに認識させる。

`Base.metadata` は「Baseを継承した全クラスのテーブル定義の一覧」をまとめたオブジェクト。AlembicはこれをもとにDBの現状と比較して「何が変わったか」を検出する。

### トランザクション（55〜56行目）

```python
with context.begin_transaction():
    context.run_migrations()
```

トランザクションは「複数の操作をひとまとめにして、全部成功か全部なかったことにする」仕組み。途中でエラーが起きたとき一部だけ適用された中途半端な状態になるのを防ぐ。`with` で囲むことで成功なら確定・エラーなら全部取り消しが自動で行われる。

### `# noqa: F401` とは

「この行の警告は無視してね」という指示。`import models` はコード中で直接使っていないため「未使用のimport」として警告が出る。しかしimportするだけで `Base.metadata` にテーブル定義が登録される仕組みのため、実際には必要なimportなので警告を抑制している。

### オフラインモードとオンラインモード

- **オンライン（通常）**: DBに直接接続してその場でテーブルを変更する
- **オフライン**: DBに接続せずSQLファイルだけ生成する。本番DBを直接触る前に「どんなSQLが実行されるか」を確認したいときに使う

---

## `alembic.ini` — alembicの設定ファイル

内容は2つに分かれる。

### ① alembicの基本設定

```ini
script_location = alembic       # マイグレーションファイルが alembic/ にあると指定
file_template = %%(rev)s_%%(slug)s  # ファイル名の形式: リビジョンID_説明文
```

`sqlalchemy.url`（DB接続先）はここには書かない。パスワードをファイルに直書きしないよう `env.py` で環境変数から取得する設計にしているため。

### ② ログの設定

`env.py` の `fileConfig(config.config_file_name)` で読み込まれる部分。

```ini
[logger_alembic]
level = INFO    # alembic自身のログはINFO以上を表示

[logger_sqlalchemy]
level = WARN    # SQLAlchemyのログはWARN以上だけ表示（SQLの詳細は出さない）
```

ログレベルは重要度の段階。

```
DEBUG < INFO < WARN < ERROR
  詳細 ←————————————→ 重大
```

`WARN` にすると通常の動作ログは流れず、警告・エラーだけ表示される。

---

### ビブラート・感情的な荒々しさへの対応について

信頼度フィルタ（`confidence > 0.5`）は「Crepeがそもそも音程を検出できたか」のフィルタで、ビブラートとは無関係。無音・ノイズを除外するためのものなので本実装後も残す。

変えるのはその後の計算。現状は「ブレが少ない＝高スコア」なのでビブラートをかけると低スコアになってしまう。本実装では目的別に処理を分ける設計になる：

```
信頼度フィルタ        → 残す
ピッチ安定性スコア    → 残す（ロングトーン評価など）
ビブラート検出        → 別途追加（周期的なブレをポジティブ評価）
荒々しさ検出          → 別途追加（特定パターンを検出）
```

`techniques.py` がその「別途追加」の担当。

---

## `frontend/src/App.tsx` — 全画面のReactコンポーネント

### ファイル全体の構造

```
App.tsx
├── 型定義（4つ）
│   ├── Screen               — 画面の名前の一覧
│   ├── AuthState            — ログイン中ユーザーの情報
│   ├── AnalysisResult       — 分析結果の形
│   └── Statistics           — 統計情報の形
│
├── UIパーツ（再利用できる小さな部品）
│   ├── ScoreRing            — 円グラフ風のスコア表示
│   ├── TechniqueBar         — 歌唱技法の棒グラフ
│   └── LineChart            — 推移折れ線グラフ
│
├── 画面コンポーネント（画面単位の大きな部品）
│   ├── AuthScreen           — ログイン / 登録画面（共通）
│   ├── UploadScreen         — 音声アップロード画面
│   ├── ResultScreen         — 分析結果画面
│   └── DashboardScreen      — 統計ダッシュボード画面
│
└── App（メイン）
    — 全画面を束ねて「今どの画面を表示するか」を管理する親
```

---

### 型定義

**`type Screen`**

```typescript
type Screen = 'login' | 'register' | 'upload' | 'result' | 'dashboard'
```

`|` は「または」。`Screen` 型はこの5つの文字列のどれか、という意味。これ以外の文字列を代入しようとするとTypeScriptがエラーを出してくれる。

**`interface`**

オブジェクトの形（プロパティ名と型）を定義するTypeScriptの構文。Pythonの `dataclass` や Pydantic の `BaseModel` に近い概念。

```typescript
interface AuthState {
  userId: number   // 数値
  email: string    // 文字列
}
```

**`?`（オプショナル）**

`song_title?: string` の `?` は「あってもなくてもいい」という意味。バックエンドが返さない場合でもエラーにならない。

**ネスト（入れ子）**

オブジェクトの中にオブジェクトが入っている状態。`AnalysisResult` は `result` の中に `techniques` があり、さらに中に `vibrato` などがある。バックエンドが返すJSONの形と合わせることでTypeScriptが補完・型チェックをしてくれる。

---

### `useState` とセッター

`useState` は「この変数が変わったら画面を再描画して」という仕組み。

```typescript
const [email, setEmail] = useState('')
```

React が管理している値と、その値を更新する専用関数のペア。値を変えるときは必ずセッター（`setEmail`）を使う。直接代入しても React は変化を検知できないため画面が更新されない。

```typescript
email = 'test@example.com'    // NG: React が気づかない → 画面そのまま
setEmail('test@example.com')  // OK: React に通知 → 画面が更新される
```

---

### `===` と真偽値への変換

```typescript
const isLogin = mode === 'login'
```

`===` は「完全に等しいか」を比較する演算子。結果は `true` か `false`。

```
mode = 'login'    → true
mode = 'register' → false
```

同じ条件を複数箇所で使うとき、一度変数に入れておくとすっきりする（リーダブルコード）。

---

### `!` 演算子と空文字

`!` は「ではない」。JavaScriptでは空文字 `''` は `false` 扱いなので：

```typescript
!''   → true  （未入力）
!'a'  → false （入力あり）
```

`if (!email || !password)` は「email か password が空なら」という条件。

---

### `??` 演算子（Nullish Coalescing）

```typescript
data.detail ?? 'エラーが発生しました。'
```

左側が `null` または `undefined` なら右側を使う演算子。バックエンドがエラーメッセージ（`detail`）を返してくれたらそれを表示し、返してくれなかったら汎用メッセージを表示する。

---

### UIパーツ — ScoreRing

コンポーネントとは「画面の部品を関数として書いたもの」。`props` は外から渡す引数。

```typescript
<ScoreRing score={75} label="ピッチ精度" color="#c084fc" />
```

SVGの `strokeDasharray` / `strokeDashoffset` という仕組みで円グラフを表現する。円周全体を破線として描き、スコアに応じた長さだけ色をつける。残りは透明にする。

```typescript
const circ = 2 * Math.PI * r       // 円周の長さ（2πr）
const offset = circ - (score / 100) * circ  // 透明にする部分の長さ
```

---

### UIパーツ — TechniqueBar

三項演算子で0除算を防ぎつつ、0〜100の割合を計算してCSSの `width: ${pct}%` で棒グラフの長さを表現する。

```typescript
const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
// max===0 → 0（ゼロ除算防止）
// Math.min(..., 100) → 100を超えたら100に丸める
```

---

### UIパーツ — LineChart

`map` はPythonのリスト内包表記と同じ概念。配列の全要素を変換する。

```typescript
data.map((_, i) => ...)
// _ → 値は使わない（添字だけ必要）という慣習
// i → インデックス（0, 1, 2, ...）
```

`toPath` 関数はSVGのパス文字列を作る。`M` は「移動（Move）」、`L` は「線を引く（Line）」。

---

### AuthScreen — ログイン・登録画面

props が3つ。`onSuccess` と `onToggle` は「関数を渡す」props。

| props | 役割 |
|---|---|
| `mode` | `'login'` か `'register'` か |
| `onSuccess` | ログイン・登録成功時に呼ぶ関数 |
| `onToggle` | 「新規登録」「ログイン」切替ボタン押下時に呼ぶ関数 |

`onSuccess: (auth: AuthState) => void` は「`AuthState` を受け取って何も返さない関数」という型。Pythonで言うと `Callable[[AuthState], None]` に相当。

**handleSubmit の処理フロー：**

```
① setError('') でエラーをリセット
② 未入力チェック → 空なら return で中断
③ 登録時のみパスワード長さチェック
④ setLoading(true) でボタンを「処理中」に
⑤ fetch() で API を呼ぶ（credentials: 'include' で Cookie を送受信）
⑥ 成功 → onSuccess() で親に通知
⑦ finally で setLoading(false)（成功・失敗どちらでも解除）
```

---

**バグ修正：データが1件のときのゼロ除算**

`data.length - 1` が `0` になり `i / 0 = NaN` でグラフが壊れる問題を修正。

```typescript
// 修正後
const xs = data.map((_, i) => pad + (data.length > 1 ? i / (data.length - 1) : 0.5) * (w - pad * 2))
// データ1件のときは中央（0.5）に配置
```

---

### UploadScreen（236〜340行目）

**役割：** 音声ファイルをドラッグ&ドロップまたはクリックで選択してバックエンドに送るUI。

**props と state**

```typescript
function UploadScreen({ onResult }: { onResult: (r: AnalysisResult) => void })
```

- props は1つ：分析完了したら呼ぶ `onResult` 関数
- state は5つ：`dragging`（ドラッグ中か）、`file`（選択済みファイル）、`songTitle`、`artistName`、`loading`、`error`

**`handleFile`（244〜248行目）**

```typescript
const handleFile = (f: File) => {
  const allowed = ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/x-m4a']
  if (!allowed.includes(f.type)) { setError('WAV / MP3 / M4A のみ対応しています'); return }
  setFile(f); setError('')
}
```

- `File` はブラウザが用意している型。`f.name`・`f.type`・`f.size` などのプロパティを持つ
- `f.type` はMIMEタイプ。ブラウザがファイル選択時に自動でセットする
- `.includes()` は「配列にその値が含まれるか」を返すメソッド
- 不正なMIMEタイプならエラーをセットして `return` で中断。以降の `setFile` は実行されない

**`handleDrop`（250〜253行目）**

```typescript
const handleDrop = (e: React.DragEvent) => {
  e.preventDefault(); setDragging(false)
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0])
}
```

- `e.preventDefault()` — ブラウザのデフォルト動作（ドロップしたファイルを別タブで開く）をキャンセルする
- `e.dataTransfer.files` — ドロップされたファイルの一覧。`[0]` で先頭1件を取る

**`handleSubmit`（255〜271行目）**

```typescript
const form = new FormData()
form.append('audio_file', file)
const url = `/api/v1/analysis/upload?song_title=...&artist_name=...`
const res = await fetch(url, { method: 'POST', credentials: 'include', body: form })
```

- `FormData` — ファイルをHTTPで送るためのオブジェクト。音声ファイルのようなバイナリデータはJSONで送れないため使う
- `form.append('audio_file', file)` — バックエンドの `audio_file: UploadFile = File(...)` と名前を合わせる必要がある
- `song_title` / `artist_name` はテキストなのでURLのクエリパラメータとして送る
- `encodeURIComponent()` — URLで使えない文字（スペース・日本語など）を安全な形式に変換するブラウザ組み込み関数（例: `'Mrs. GREEN APPLE'` → `'Mrs.%20GREEN%20APPLE'`）

**UIのドロップゾーンの色切り替え（289行目）**

```typescript
border: `2px dashed ${dragging ? '#c084fc' : file ? '#34d399' : '#2a2a3e'}`,
```

三項演算子を入れ子にして3パターンの色を切り替える：
- ドラッグ中 → 紫
- ファイル選択済み → 緑
- 何もなし → グレー

**楽曲名・アーティスト入力欄（311〜325行目）**

同じ構造の入力欄が2つあるので、データを配列にまとめて `map` で展開している。Reactでリストを描画するとき `key` が必要で、Reactが「どの要素が変わったか」を追跡するために使う。

---

### ResultScreen（345〜400行目）

**役割：** 分析完了した結果を表示する画面。

**props**

| props | 型 | 役割 |
|---|---|---|
| `result` | `AnalysisResult` | 分析結果データ |
| `onBack` | `() => void` | 「戻る」ボタン押下時に呼ぶ関数 |
| `onDashboard` | `() => void` | 「ダッシュボードを見る」ボタン押下時に呼ぶ関数 |

`() => void` は「引数なし・戻り値なし」の関数型。

**`onBack` の命名慣例**

Reactには `onClick`・`onChange` のようにブラウザイベントに `on` をつける命名がある。自作コンポーネントでも「何かが起きたときに呼ばれる関数」には `on〇〇` という名前をつけるのが慣例。`ResultScreen` はただ「戻るが押された」と親（App）に伝えるだけで、どう動くかは親が決める。

**変数への展開（348〜350行目）**

```typescript
const scores = result.result
const techniques = scores.techniques
```

`result.result.techniques.vibrato.count` と毎回書くより短い変数に入れておくことで読みやすくなる。リーダブルコードの考え方。

**フィードバック欄の条件描画（388〜393行目）**

```typescript
{scores.feedback && <div>...</div>}
```

`&&` の短絡評価：左が `undefined` / 空文字なら何も描画されない。`feedback` が `undefined` のときに安全に何も表示しない書き方。

---

### DashboardScreen（405〜490行目）

**役割：** 統計情報をAPIから取得して表示する画面。唯一 `useEffect` でデータ取得を行うコンポーネント。

**`useEffect` でのデータ取得（412〜418行目）**

```typescript
useEffect(() => {
  fetch('/api/v1/analysis/user/statistics', { credentials: 'include' })
    .then(res => { if (!res.ok) throw new Error(...); return res.json() })
    .then((data: Statistics) => setStats(data))
    .catch(e => setError(...))
    .finally(() => setLoading(false))
}, [])
```

- `useEffect` の第2引数 `[]` — 「依存なし＝最初の1回だけ実行」という意味。コンポーネントが画面に表示されたタイミングで自動実行される
- `.then()` / `.catch()` / `.finally()` のチェーンは `async/await` + `try/catch/finally` と同じことをしている。書き方が違うだけ

**条件分岐による表示切り替え（430〜454行目）**

```typescript
{loading && <p>読み込み中...</p>}
{error && <p>{error}</p>}
{stats && stats.history.length > 0 && <LineChart />}          // データあり
{stats && stats.history.length === 0 && !loading && <p>...</p>} // データなし
```

`&&` の短絡評価を組み合わせて「ローディング中」「エラー」「データあり」「データなし」の4パターンを表示し分ける。

**`?.` と `??` の組み合わせ（476〜478行目）**

```typescript
stats?.total_count ?? '-'
```

- `?.`（オプショナルチェーン）— `stats` が `null` のとき `null.total_count` にならず `undefined` を返す
- `??`（Nullish Coalescing）— 左側が `null` / `undefined` なら右側（`'-'`）を使う

APIが返るまで `stats` は `null` なので、データがない間は `-` と表示する。

**成長率のプラス符号（478行目）**

```typescript
stats.growth_rate >= 0 ? `+${stats.growth_rate}` : `${stats.growth_rate}`
```

JavaScriptは正の数に `+` を自動でつけないため、`+5` と表示したいとき明示的に文字列として組み立てる必要がある。

---

### App（メイン）— 513〜543行目の詳細

**`handleAuthSuccess`（513〜516行目）**

```typescript
const handleAuthSuccess = (newAuth: AuthState) => {
  setAuth(newAuth)
  setScreen('upload')
}
```

ログイン・登録成功時に `AuthScreen` から呼ばれる。`auth` はほぼ全画面で使う情報なので最上位の `App` が持つ。子コンポーネントが直接 `setAuth` を呼べないため「成功したら呼んでね」と関数を props で渡す設計。

**`handleLogout`（518〜525行目）**

```typescript
const handleLogout = () => {
  fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' })
    .finally(() => {
      setAuth(null)
      setAnalysisResult(null)
      setScreen('login')
    })
}
```

`.then()` も `.catch()` も書かず `.finally()` だけ使っている。APIが成功しても失敗しても「stateをリセットしてログイン画面に戻す」動作は変わらないため。`setAnalysisResult(null)` もリセットするのは次に別ユーザーでログインしたとき前のユーザーの結果が残らないようにするため。

**`handleResult`（527〜530行目）**

```typescript
const handleResult = (result: AnalysisResult) => {
  setAnalysisResult(result)
  setScreen('result')
}
```

`UploadScreen` から分析結果を受け取って `App` のstateに保存し、結果画面に切り替える。`analysisResult` を `App` が持つことで `DashboardScreen` にも `latestResult` として渡せる。

**変数名のスコープと適切な長さ（リーダブルコード）**

引数 `result` はこの2行の中だけで使われる狭いスコープ。型ヒント `AnalysisResult` もすぐ隣にあるため `result` で十分明確。一方 `App` のstate `analysisResult` は複数画面に渡す広いスコープなので長くて具体的な名前が必要。スコープが小さいほど短い名前でよい、というリーダブルコードの考え方。（`r` のような1文字は「略称」でも不十分で改善が必要）

**`isAuthScreen`（532行目）**

```typescript
const isAuthScreen = screen === 'login' || screen === 'register'
```

同じ条件を2か所で使うため変数にして名前をつける。「今ログイン・登録画面にいるか」という意図が読んで分かる。リーダブルコードの考え方。

**ロゴのクリック制御（537〜542行目）**

```typescript
onClick={() => auth && setScreen('upload')}
style={{ cursor: auth ? 'pointer' : 'default' }}
```

ログイン済みのときだけクリックでアップロード画面へ移動。`cursor` を切り替えて「クリックできる・できない」の見た目の手がかりをユーザーに与えるUXの工夫。

**`minHeight: '100vh'`**

`vh` は「ビューポートの高さの1%」という単位。`100vh` で画面の高さ全体を埋める。

**`justifyContent: 'space-between'`**

Flexboxの設定。子要素を左右の端に振り分ける。左にロゴ、右にナビを配置するために使っている。

## フロントエンド設定ファイル群

**`frontend/Dockerfile`**

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- `COPY package*.json` → `RUN npm install` → `COPY . .` の順番が重要。先にpackage.jsonだけコピーして `npm install` することで、ソースコードを変えてもnode_modulesのキャッシュが効く。全ファイルコピー後に `npm install` するとソース変更のたびに再インストールしてしまう
- `--host 0.0.0.0` — Viteのデフォルトはlocalhostのみ待ち受けるため、コンテナ外（ホストやnginx）からアクセスできない。0.0.0.0で全インターフェースから受け付けるように指定

**`frontend/src/main.tsx`**

フロントエンドのエントリーポイント。`index.html` の `<div id="root">` を取得してReactアプリを描画する。

- `!`（非nullアサーション） — `getElementById` はnullを返す可能性があるが、`index.html` に必ず `id="root"` があるため null にならないと断言するTypeScriptの記法
- `<StrictMode>` — 開発環境でReactの警告を強化するモード。本番ビルドでは自動的に無効になる

**`frontend/index.html`**

ViteがブラウザにHTMLを返すときのテンプレート。`<div id="root">` がReactの描画先。`<title>frontend</title>` はViteの初期値のままだったため `<title>Vocal Analyzer</title>` に修正済み。

**`frontend/package.json`**

- `dev` — Viteの開発サーバーを起動。`docker compose up` で動くのはこれ
- `build` — TypeScriptの型チェック（`tsc -b`）のあとViteでバンドルして `dist/` を生成
- `lint` — ESLintでコードをチェック
- `preview` — `build` で生成した `dist/` をローカルでプレビュー

**ESLintとは**

JavaScriptおよびTypeScriptのコードを静的に解析して「バグになりやすい書き方」や「ルール違反」を検出するツール。実行前にコードの問題を指摘してくれる。`useEffect` の依存配列漏れや未使用変数などを警告する。

**`dist/` とは**

`npm run build` を実行したときにViteがTypeScriptとReactをブラウザが直接読めるJavaScriptに変換して出力するフォルダ。本番デプロイ時はこの中身をサーバーに置く。ソースコードから毎回生成できるため `.gitignore` で除外されている。

**`frontend/vite.config.ts`**

Viteの設定ファイル。`@vitejs/plugin-react` を有効化することでJSX変換やホットリロードが動く。現在は最小限の設定。

**`frontend/tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json`**

TypeScriptの設定が3ファイルに分かれている。

- `tsconfig.json` — ルート設定。他2つを参照するだけ
- `tsconfig.app.json` — Reactアプリ用の設定。`"strict": true` / `"noUnusedLocals": true` / `"noUnusedParameters": true` で厳しめの型チェック
- `tsconfig.node.json` — vite.config.tsのみを対象にしたNode.js環境用の設定

**`frontend/eslint.config.js`**

TypeScript + React向けのESLint設定。`react-hooks` プラグインで `useEffect` の依存配列漏れなどを検出する。`dist/` フォルダは除外済み。

**`frontend/App.css` / `index.css`**

Viteが自動生成したデフォルトのスタイル。`App.tsx` はインラインスタイルで書かれているためほぼ使われていない。将来CSS設計を整理するときに削除または置き換えが必要。

**`frontend/.gitignore`**

Viteが自動生成したフロントエンド用 `.gitignore`。`node_modules/` / `dist/` / ログファイル / エディタ設定などを除外。ルートの `.gitignore` と二重になっている部分もあるが、フロントエンドディレクトリ単体でも独立して使えるようにするための設計。

**`frontend/README.md`**

`npm create vite` 時に自動生成されたViteデフォルトのREADME。プロジェクト固有の内容がなかったため削除済み。

## バックエンド Alembic 関連ファイル

**`backend/api/__init__.py` / `backend/audio/__init__.py`**

コメントのみの1行ファイル。Pythonではディレクトリをパッケージとして認識させるために `__init__.py` が必要。中身は空でも成立する。これがあることで `from backend.api.auth import router` のようなインポートが機能する。

**`backend/alembic/script.py.mako`**

Alembicが `alembic revision --autogenerate` を実行するときに新しいマイグレーションファイルを自動生成するテンプレートファイル。`${message}` や `${up_revision}` は変数で、Alembicが値を埋め込む。自分で編集するものではない。

**`backend/alembic/versions/62b066d20808_create_initial_tables.py` — 初回マイグレーション**

- `down_revision: None` — 前のマイグレーションがない（最初のマイグレーション）という意味
- `upgrade()` で `users` / `analysis_results` テーブルを作成
- `downgrade()` で元に戻す（テーブル削除）
- `op.create_index(op.f('ix_users_email'), ...)` — メールアドレスに一意インデックスを作成。ログイン時の高速検索のため

**`backend/alembic/versions/a1b2c3d4e5f6_add_hashed_password_to_users.py` — 2回目マイグレーション**

- `down_revision: '62b066d20808'` — 初回マイグレーションのIDが入っている。これで「初回の後に適用する」という順序が定義される。Alembicはこのチェーンをたどって順番に実行する
- `upgrade()` で `users` テーブルに `hashed_password` カラムを追加
- `nullable=False` なのに `server_default=''` — 既存の行があるときに `NOT NULL` カラムを追加するための対応。既存行には空文字が自動で入る。SPEC.mdの「デフォルト'' → 将来的に要見直し」の理由がこれ

## `SPEC.md` — 開発者視点の設計書

README.mdが「外から見た説明書」なのに対して、SPEC.mdは「開発者視点の設計書・意思決定の記録」。「なぜこう設計したか」の理由が書かれている。

**プロダクトの目的 / 開発の背景**

既存カラオケ採点システムの問題点（Anti-Patterns）が具体的に書かれている。

- ハードウェア依存 — マイク感度でスコアが変わる
- 棒読みの過大評価 — 機械的に安定しているだけで高得点になる
- 回数主義 — しゃくりを何回使ったかだけで評価している

これらを解決するために作っているという背景。「なんとなく作る」ではなく具体的な課題意識から始まっていることが読み取れる。

**コア評価ロジックの設計方針**

- A. スコアマトリクス — 合計点1つではなく「基本忠実度・表現の不自然さ・音楽的ダイナミクス」の3軸で評価する設計。棒読み検出は「ピッチ分散が極端に小さい かつ 技法数がゼロ → 減点」というロジック
- B. 技法密度分析 — 「何回使ったか」ではなく「フレーズの中で適切な密度で使えているか」で評価する方針
- C. テキストフィードバック — まずルールベース（テンプレート文章）で実装し、将来LLMに差し替えられる設計にする。コストと安定性を両立する判断

**既知の問題・技術的負債**

| 問題 | 重大度 |
|---|---|
| `GET /analysis/{id}` に認証チェックがない | 🔴 高（Phase 6前に修正予定） |
| タイミング攻撃によるユーザー列挙の可能性 | 🟠 中 |
| ロックアウトのRedis操作が非atomic | 🟠 中 |
| `python-jose` にCVEが報告済み | 🟠 中 |

**AI活用の方針**

Claude Codeをどう使うかの原則がまとめてある。「自信満々な回答ほど疑う」「一度に大きな作業をさせない」「最終判断は常に自分がする」など、AIと協力するときの心構えが書かれている。

## `README.md` — プロジェクトの顔

GitHubでリポジトリを開いたときに最初に表示されるファイル。「このプロジェクトは何か・どう使うか」を初めて見た人に伝える役割。CLAUDE.mdが「Claudeへの指示書」なのに対して、README.mdは「人間への説明書」。

**各セクションの役割**

- `実装済みの機能 / 開発予定の機能` — 今できることと将来できることを分けて記載。スクリーンショットもあり、コードを読まなくても何のアプリか伝わる
- `技術スタック` — 使用技術の一覧。採用理由まで書く必要はなく「何を使っているか」でよい
- `セットアップ` — `git clone` から `docker compose up` まで3ステップ。前提条件はDockerのインストールのみ
- `APIエンドポイント` — フロントエンド開発者や外部から使う人向けの参照用ドキュメント
- `セキュリティとプライバシー` — 音声データを保存しないことやJWTの扱いなど、ユーザーにとって重要なプライバシー方針
- `開発ロードマップ` — Phase 1〜9の進捗一覧

**バグ修正**

セットアップのURLが誤っていた。`docker-compose.yml` のポートマッピングは `"8080:8000"`（ホスト側8080番）なのに `http://localhost:8000` と書かれていた。`http://localhost:8080` に修正済み。

## `CLAUDE.md` — Claude Code専用の引き継ぎドキュメント

会話を新しく始めるたびにClaudeはコードの記憶をリセットするが、CLAUDE.mdはプロジェクトルートに置くことでClaudeが毎回自動で読み込むファイル。「このプロジェクトはこういうものです、こう動いてください」という指示書の役割を果たす。

**各セクションの役割**

- `## Claude Codeへの指示` — Claudeの振る舞いに関するルール。「推測と確実な情報を区別する」「存在しないAPIを使わない」など。これがあることで会話が変わるたびに同じお願いを繰り返さなくて済む
- `## 技術スタック` / `## ポート構成` — 前提知識の共有。Claudeがコードを読むときの文脈になる
- `## 完了済みフェーズ` — どこまで実装が終わっているかの地図。的外れな提案を防ぐ
- `## 現在の状態` — ブランチ名・最終確認日など今この瞬間のスナップショット。作業のたびに更新が必要
- `## 決定済みの仕様・注意事項` — コードを読んだだけでは分からない「なぜこうなっているか」の理由。たとえば「Crepe採用: 精度重視のためlibrosa.pyinへの変更はしない」はコードを見ても理由がわからないため、ここに書くことで誤った変更提案を防ぐ
- `## 次にやるべきこと` — 次のフェーズの計画と技術的負債の一覧
- `## ファイル構成` — 重要ファイルの一覧と役割。Claudeがファイルを探すときの道しるべ
- `## ログ` — 日付付きの変更履歴。「なぜこの変更をしたか」の理由ベースの記録

## `.env.example` — 環境変数のテンプレート

`.env` は秘密情報を書くファイルで `.gitignore` で除外されているため、リポジトリをクローンした人の手元には存在しない。`.env.example` は「こういう変数が必要ですよ」というテンプレートとしてGitに入れておくファイル。実際の値（本物の秘密キーなど）は書かず、ダミー値や説明を書いておく。

**各変数の意味**

- `DATABASE_URL` — PostgreSQLへの接続文字列。形式は `postgresql://ユーザー名:パスワード@ホスト名:ポート/DB名`。`@db` の `db` はDockerの内部ネットワーク上のホスト名
- `REDIS_URL` — Redisへの接続文字列。`redis` はDockerの内部ネットワーク上のホスト名
- `SECRET_KEY=your-secret-key-here` — JWTの署名に使う秘密キー。`your-secret-key-here` はダミー値で実際に使う際は強力なランダム文字列に差し替える
- `ALGORITHM=HS256` — JWTの署名アルゴリズム。`auth_utils.py` で `os.environ.get("ALGORITHM", "HS256")` と読んでいる
- `ACCESS_TOKEN_EXPIRE_MINUTES=30` — JWTの有効期限（分）。`auth_utils.py` で `os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30)` と読んでいる
- `DEBUG=true` — デバッグモードのフラグ。現在の `main.py` では読み込まれておらず、将来用に書いてある変数

**本番環境での注意**

`DATABASE_URL` と `REDIS_URL` には開発用のデフォルト値がそのまま書かれている。`.env.example` はGitに入るファイルなので本来はダミー値にすべき。本番デプロイ時には環境変数またはAWS Secrets Managerなどのシークレット管理ツールで実際の接続情報を注入すること。SPEC.mdのセキュリティセクションとCLAUDE.mdの技術的負債セクションに方針を記載済み。

## `.gitignore` — Gitの除外設定

書いたパターンに一致するファイル・ディレクトリは `git add` しても無視され、リポジトリに含まれない。

**環境変数**

`.env` — `SECRET_KEY` などの秘密情報を書くファイル。Gitに入れるとGitHubに公開されて秘密情報が漏れるため必ず除外する。

**Python**

- `__pycache__/` / `*.pyc` / `*.pyo` — Pythonが実行時に自動生成するキャッシュファイル。ソースコードから毎回生成されるので管理不要
- `.venv/` / `venv/` — 仮想環境ディレクトリ。`requirements.txt` があれば再現できるので管理不要

補足: Python3では `.pyc` は `__pycache__/` の中に生成されるため `__pycache__/` だけで十分。両方書いても害はないが冗長。

**Node**

- `node_modules/` — `npm install` でインストールしたパッケージ。`package.json` があれば再現できる。サイズも巨大になるため除外必須
- `dist/` — `npm run build` でViteが生成するビルド成果物。ソースから毎回生成できるので管理不要

**Docker**

`postgres_data/` — プロジェクトルートにDBデータディレクトリが万が一できてしまったときのための除外指定。DBデータをGitに入れると容量が巨大になり機密データが漏れるリスクがある。

**OS**

- `.DS_Store` — macOSがフォルダを開いたときに自動生成するメタデータファイル
- `Thumbs.db` — Windowsがサムネイル情報を保存するファイル

チームメンバーのOSが違っても余計なファイルがGitに入らないようにするための除外指定。

**一時ファイル（音声）**

`*.wav` / `*.mp3` / `*.m4a` / `tmp/` — 著作権保護の設計方針（録音音声ファイルは保存しない）に基づき、開発中のテスト用音声ファイルが誤ってGitに入らないようにするための除外指定。

---

## Phase 6: テスト（pytest）

### テストの全体方針

音声分析の精度検証（Crepe・librosa）はスタブ段階のため対象外。**認証・認可・入力バリデーション・正常系の主要フローを優先する。**

```
backend/tests/
├── conftest.py          ← テスト全体で使う共通の準備・後片付け
├── test_auth_utils.py   ← auth_utils.py の単体テスト（JWT・パスワード・ロックアウト）
└── test_api_auth.py     ← 認証APIエンドポイントのテスト
```

**単体テスト（Unit Test）** — 1つの関数だけを取り出して「この入力を渡したらこの出力が返るか」を確認するテスト。

**APIテスト（Integration Test）** — FastAPI の全体（ルーティング → バリデーション → DB保存 → レスポンス）を通しで確認するテスト。

**pytest** — `test_` で始まる関数を自動で見つけて実行し、`assert` でチェックするPythonのテストフレームワーク。

```python
def test_足し算():
    result = 1 + 1
    assert result == 2   # 2 でなければテスト失敗
```

---

### `backend/tests/conftest.py` — テスト共通設定

pytest が自動で読み込む「テスト全体で使う共通の準備・後片付けファイル」。

**テストの2大課題と解決策**

| 課題 | 問題 | 解決策 |
|---|---|---|
| DB | 本番のPostgreSQLにテストデータを入れたくない | SQLiteのインメモリDB（テスト専用・毎回リセット）を使う |
| Redis | テスト中に本物のRedisに繋げたくない | `fakeredis`（偽のRedis）で置き換える |

**SQLite とは**

PostgreSQL と同じリレーショナルDBだが、サーバーが不要なファイル型DB。`sqlite:///:memory:` と指定するとファイルすら作らずメモリ上だけに存在する。テスト終了と同時にデータも消える。

**fakeredis とは**

偽物のRedisサーバーをPythonのメモリ上に作るライブラリ。本物のRedisサーバーなしで `redis-py` の全APIが使える。

**pytest の `fixture`（フィクスチャ）とは**

テストの準備と後片付けを自動でやってくれる仕組み。`yield` が「準備 / テスト / 後片付け」の境界線。

```python
@pytest.fixture
def db():
    # ─── 準備 ───
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    yield session  # ← テストに渡してここで一時停止

    # ─── 後片付け ───（テスト完了後に自動実行）
    session.close()
    Base.metadata.drop_all(bind=engine)
```

**ファイル全体の構造理解**

| 行 | 内容 |
|---|---|
| 22〜28行目 | SQLiteのインメモリDBに繋ぐための設定（`engine` と `TestingSessionLocal`）。この時点ではDBに何も起きていない |
| 31〜40行目 | `db` fixture — テスト1件ごとに「テーブル作成 → テスト実行 → テーブル削除」を自動でやる動作 |
| 43〜59行目 | `fake_redis` fixture — 本物のRedisをfakeredisに一時的に差し替えて、テスト終了後に元に戻す |
| 62〜71行目 | `client` fixture — `db`・`fake_redis`・`TestClient` の3つを組み合わせた統合版。APIを叩くテスト用 |

`db` と `fake_redis` は独立した部品として作ってある。「DBだけ使うテスト（Redisは不要）」では `db` fixture 単体で呼べる。

**セッションファクトリとは**

「セッションを作る工場」。`sessionmaker(...)` の戻り値はクラス（設定済みのセッション生成器）で、`()` で呼び出すとセッションが1つ作られる。

```python
TestingSessionLocal = sessionmaker(...)  # 工場の設計図（設定）
session = TestingSessionLocal()          # 工場から出てきた製品（セッション）
```

**`check_same_thread=False` とは**

SQLite 特有の設定。デフォルトでは1スレッドからしかアクセスできない制限があり、FastAPIのテスト環境ではこれが問題になるため明示的に無効化している。

**`patch` とは**

`unittest.mock.patch` は「テストの間だけ、特定の変数を別のものに差し替えて、テストが終わったら元に戻す」仕組み。

```python
with patch("auth_utils._redis", fake_r):
    # このブロック内だけ _redis が fakeredis になる
    check_lockout("test@example.com")
# ブロックを出たら元の redis に戻る
```

**`dependency_overrides`（依存関係のすり替え）とは**

FastAPI の `Depends(get_db)` をテスト用DBに差し替える仕組み。本番は `get_db` を呼んでPostgreSQLに繋ぐが、テスト中はSQLiteに変える。テストが終わったら `dependency_overrides.clear()` で元に戻す。

**`TestClient` とは**

サーバーを起動せずにFastAPIアプリをHTTPリクエストで叩けるクライアント。内部では `httpx` の `ASGITransport` を使い、ネットワーク通信なしでASGIアプリを直接インプロセスで呼び出す。`requests`（別ライブラリ）はASGIアプリへの直接呼び出しに対応していないため、httpxが必要。

**Lua スクリプトの fake_eval について**

`record_login_failure` は `_redis.eval(Luaスクリプト, ...)` を呼んでいる。`fakeredis` のデフォルトはLuaスクリプトの実行に対応していないため、やること（INCR + EXPIRE）と同じ処理をPythonで書いて `eval` メソッドを差し替えている。fakeredisのバージョンによっては不要になる可能性があるため、実際に動かしてエラーにならなければ削除する。

---

### `assert` とは

「この条件が True でなければテスト失敗にする」という Python のキーワード。pytest は `assert` が失敗（`AssertionError` が発生）したテスト関数を「FAILED」として記録する。

```python
assert res.status_code == 201   # 201 でなければ AssertionError → テスト失敗
assert "access_token" in res.cookies  # cookies に "access_token" がなければ失敗
```

`assert` が1行も失敗しなければそのテスト関数は「PASSED」になる。

---

### HTTP ステータスコード一覧

| コード | 名前 | 意味 | このプロジェクトでの用途 |
|---|---|---|---|
| **200** | OK | 正常 | GET /me, POST /login 成功 |
| **201** | Created | 作成成功 | POST /register 成功 |
| **204** | No Content | 成功・返すデータなし | POST /logout 成功 |
| **400** | Bad Request | リクエストの内容が不正 | パスワード8文字未満、非対応ファイル形式 |
| **401** | Unauthorized | 認証失敗・未認証 | 誤パスワード、未ログイン |
| **403** | Forbidden | 認可失敗（ログインしているが権限なし） | 他人の分析結果にアクセス |
| **404** | Not Found | リソースが存在しない | 存在しない分析IDを指定 |
| **409** | Conflict | 競合（すでに存在する） | 重複メールアドレスで登録 |
| **422** | Unprocessable Entity | バリデーションエラー | FastAPIが自動で返す（必須項目の欠落など）。テスト対象外 |
| **429** | Too Many Requests | リクエスト過多 | ログイン試行回数上限 |

401 と 403 の違い：401 は「そもそも誰かわからない（未ログイン）」、403 は「ログインはしているが権限がない」。

---

### `backend/tests/test_api_auth.py` — 認証APIのテスト

#### ヘルパー関数

```python
def _register(client, email="test@example.com", password="password123"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})

def _login(client, email="test@example.com", password="password123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})
```

- `client.post(url, json=data)` — TestClient に POST リクエストを送る。`json=` に辞書を渡すと自動で JSON に変換する
- `email="test@..."` はデフォルト引数。省略すると左の値が使われる。変えたいときだけ上書きする
- `_` で始まる名前は「このファイルの内部だけで使う補助関数」という慣例。pytest が `test_` で始まる関数だけをテストとして収集するため、ヘルパーは `_` で始める
- 複数のテストで登録・ログイン処理を書き直さずに済む（DRY の考え方）

#### TestClient でのリクエストとレスポンスの確認方法

| 記述 | 意味 |
|---|---|
| `client.post(url, json=data)` | POST リクエストを送る |
| `client.get(url)` | GET リクエストを送る |
| `res.status_code` | レスポンスの HTTP ステータスコード（200, 401 など） |
| `res.json()` | レスポンスボディを JSON → 辞書に変換したもの |
| `res.json()["email"]` | レスポンスの `email` フィールドを取り出す |
| `res.cookies` | **このレスポンスで** Set-Cookie されたクッキーの一覧 |
| `client.cookies` | **TestClient が保持している**クッキーの一覧（リクエスト間で自動維持） |
| `res.headers["set-cookie"]` | Set-Cookie ヘッダーの生の文字列（`httponly` 属性の確認に使う） |

TestClient をコンテキストマネージャ（`with TestClient(...) as c:`）で使うと、クッキーがリクエスト間で**自動的に維持**される。登録後に `/me` を呼ぶと `access_token` クッキーが自動で付く。

#### `"access_token"` は自分たちが決めた名前

`auth.py` でクッキー名を決めているのは自分たちのコード。

```python
response.set_cookie(key="access_token", value=token, ...)
```

`"access_token" in res.cookies` は「このレスポンスで `access_token` という名前のクッキーが発行されたか」を確認している。

#### テスト一覧と意図

**POST /register**

| テスト | 確認すること |
|---|---|
| `test_register_success` | 201 が返るか・メールアドレスがレスポンスに含まれるか・クッキーが発行されるか |
| `test_register_duplicate_email` | 同じメールアドレスで2回登録すると 409 が返るか |
| `test_register_short_password` | 8文字未満のパスワードで 400 が返るか |

**POST /login**

| テスト | 確認すること |
|---|---|
| `test_login_success` | 200 が返るか・クッキーが発行されるか |
| `test_login_wrong_password` | 間違ったパスワードで 401 が返るか |
| `test_login_nonexistent_email` | DB に存在しないメールアドレスで 401 が返るか（「未入力」ではなく「登録されていない」） |
| `test_login_same_error_message_for_wrong_password_and_nonexistent` | 誤パスワードと存在しないメールのエラーメッセージが**同一**か（ユーザー列挙攻撃対策） |
| `test_login_lockout_after_five_failures` | 5回失敗した後の6回目が 429 になるか |
| `test_login_clears_lockout_on_success` | ログイン成功後にロックアウトカウンターが削除されるか |

**GET /me**

| テスト | 確認すること |
|---|---|
| `test_me_authenticated` | ログイン済みで 200 とメールアドレスが返るか |
| `test_me_unauthenticated` | クッキーなしで 401 が返るか |

**POST /logout**

| テスト | 確認すること |
|---|---|
| `test_logout_clears_cookie` | 204 が返るか・ログアウト後に /me が 401 になるか |

#### ロックアウトのカウンターと 429 の関係

auth.py のログイン処理順：

```
1回目: check_lockout(count=0, OK) → 失敗 → record(count=1) → 401
2回目: check_lockout(count=1, OK) → 失敗 → record(count=2) → 401
...
5回目: check_lockout(count=4, OK) → 失敗 → record(count=5) → 401
6回目: check_lockout(count=5, LOCKED) → 429  ← ここで弾かれる
```

`check_lockout` はログイン処理の**最初**に呼ばれる。5回失敗した後の6回目が 429 になる。

#### `for _ in range(5):` の `_`

```python
for _ in range(5):
    _login(client, password="wrong")
```

`range(5)` は `[0, 1, 2, 3, 4]` を生成する。`for i in range(5):` のように書くとループ変数 `i` が作られるが、ここでは **5回繰り返したいだけ**でループ変数の値を使わない。`_` は「意図的に使わない」という Python の慣例。使わない変数を `i` と書くとエディタが「未使用の変数」と警告するため `_` で抑制する。

#### `test_login_clears_lockout_on_success` での fake_redis 直接参照

```python
def test_login_clears_lockout_on_success(client, fake_redis):
    _register(client)
    for _ in range(4):
        _login(client, password="wrong")
    _login(client)  # 正しいパスワードで成功 → clear_lockout() が内部で呼ばれる
    assert fake_redis.get("login_fail:test@example.com") is None
```

- API のレスポンスだけでは「カウンターが消えた」は確認できないため、fakeredis を**直接覗いて確認**する
- `client` と `fake_redis` を両方引数に書くと、pytest が**同じ fakeredis インスタンス**を両方に渡す。そのためテスト関数内から `fake_redis.get(...)` でカウンターの状態を確認できる

#### test_logout の仕組み

`delete_cookie` はサーバーが `Set-Cookie: access_token=; Max-Age=0` をレスポンスに付ける。TestClient がこれを処理してクッキーを削除するので、次の `/me` リクエストにはクッキーが付かず 401 が返る。

#### base_url="https://testserver" が必要な理由

auth.py で `set_cookie(..., secure=True)` を指定している。`Secure` 属性は「HTTPS でしか送らない」クッキーを意味する。TestClient のデフォルト URL は `http://testserver`（HTTP）なので、httpx が「HTTP だから Secure クッキーは送らない」と判断してリクエストにクッキーが付かなくなる。`base_url="https://testserver"` にすることで TestClient が HTTPS として扱い、クッキーが正しく送受信される。実際にはサーバーを起動していないため、本物の HTTPS 通信ではなく「URL のスキームが `https` である」という情報だけを使って制御している。

#### httpOnly 属性の確認テスト

SPEC.md には「httpOnly Cookie がセットされるか」という確認項目がある。クッキーの存在確認だけでは不十分で、`httponly` 属性があるかも確認する必要がある。

```python
assert "httponly" in res.headers["set-cookie"].lower()
```

`res.headers["set-cookie"]` で Set-Cookie ヘッダーの生の文字列（例: `access_token=eyJ...; HttpOnly; Secure; ...`）を取り出し、`httponly` という文字列が含まれるかを確認する。`.lower()` で小文字に統一してから確認するのは、サーバーが `HttpOnly` と `httponly` どちらで返しても対応するため。`test_login_success` に追加済み。

---

### `backend/tests/test_api_analysis.py` — 分析APIのテスト

#### なぜ `audio_analyzer.analyze()` をモックするのか

`analyze()` は Crepe（AIモデル）+ librosa を使う。テストで本物を実行すると：
- 重い（数秒かかる）
- 本物の音声ファイルが必要
- TensorFlow の初期化が走る

テストの目的は「APIのルーティング・認証・DB保存・レスポンス形式が正しいか」。分析エンジン自体の正しさはここでは確認しない。なので `analyze()` をモックしてダミーデータを返す。

#### `_MOCK_ANALYSIS` — ダミーデータの構造（16〜22行目）

```python
_MOCK_ANALYSIS = {
    "pitch_accuracy": 75.0,
    "rhythm_score": 0.0,
    "techniques": {},
    "vocal_range": {"lowest": None, "highest": None, "range_semitones": 0},
    "feedback": "テストフィードバック",
}
```

`analyzer.py` の `analyze()` が返す辞書と**キーの名前を合わせる**必要がある。`_save_to_db()` が `analysis_data.get("pitch_accuracy")` のようにキー名を指定して取り出すため、キーが違うと `None` が保存されてしまう。

モジュールの先頭（関数の外）に置くことで、ファイル内の全テストから参照できる。

#### `_create_minimal_wav()` — WAV ファイルをメモリで作る（24〜32行目）

```python
def _create_minimal_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)      # モノラル（ステレオは2）
        wav_file.setsampwidth(2)      # 16bit（1サンプル = 2バイト）
        wav_file.setframerate(44100)  # サンプリングレート 44100Hz
        wav_file.writeframes(b"\x00" * 200)
    return buf.getvalue()
```

- `io.BytesIO()` はメモリ上のバッファ。ファイルのように読み書きできるがディスクに何も書かない。`io` は Python 標準ライブラリ
- `wave` は Python 標準の WAV ファイル操作ライブラリ。`"wb"` は「書き込みモード（write binary）」。`buf` にファイルの代わりに渡すことでメモリ上に書く
- WAV ファイルには「チャンネル数・ビット深度・サンプリングレート」というヘッダー情報が必要。`setnchannels` / `setsampwidth` / `setframerate` でそれぞれ設定する
- 中身（音声データ）はゼロ（無音）でよく、librosa が読める形式かどうかだけが重要
- `wav_file.writeframes(b"\x00" * 200)` で 200 フレームぶんのゼロデータを書き込む
- `buf.getvalue()` でバッファに書き込まれた全バイト列を返す。戻り値の型ヒント `-> bytes` は「バイト列を返す」という宣言

#### `_register_and_login()`（34〜35行目）

```python
def _register_and_login(client, email="test@example.com", password="password123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
```

戻り値（`return`）が**ない**。これはレスポンスを確認せず「登録してクッキーをセットするだけ」の目的で呼ぶためで、後続のテストで認証が必要な操作をするための前準備。`test_api_auth.py` の `_register` は `return` しているが、こちらは「分析テストの準備」に特化したヘルパーなので戻り値不要。

#### `_upload()`（38〜44行目）

```python
def _upload(client, filename="test.wav", content_type="audio/wav", content=None):
    if content is None:
        content = _create_minimal_wav()
    return client.post(
        "/api/v1/analysis/upload",
        files={"audio_file": (filename, content, content_type)},
    )
```

- `content=None` はデフォルトで「省略されたら WAV を自動生成する」パターン。大きいファイルのテストや別形式のテストなど「自分でデータを渡したい場合」だけ `content=` を指定する

**`files=` でファイルを送る**

`files=` は JSON ではなくファイルを送るときのパラメータ。タプルの構造は `(ファイル名, バイト列, MIMEタイプ)`。

```python
files={"audio_file": ("test.wav", file_content, "audio/wav")}
#              ↑フィールド名   ↑ファイル名    ↑中身   ↑MIMEタイプ
```

バックエンドの `audio_file: UploadFile = File(...)` と辞書のキー名（`"audio_file"`）を一致させる必要がある。名前が違うとサーバーがファイルを受け取れずエラーになる。

#### `patch` の書き方（58〜60行目）

```python
with patch("api.analysis.audio_analyzer.analyze", return_value=dict(_MOCK_ANALYSIS)):
    res = _upload(client)
```

- `"api.analysis.audio_analyzer.analyze"` — `api/analysis.py` の中にあるグローバル変数 `audio_analyzer`（`AudioAnalyzer` のインスタンス）の `.analyze` メソッドを指定する。`api.analysis` はモジュールパス（ファイルの場所）、`audio_analyzer` はそのファイルの中の変数名、`analyze` はそのメソッド名
- `return_value=dict(_MOCK_ANALYSIS)` — `analyze()` が呼ばれたとき、実際の処理をせずこの辞書を返す
- `dict(_MOCK_ANALYSIS)` は `_MOCK_ANALYSIS` のシャローコピー。`_run_analysis()` の中で `result["song_title"] = song_title` と辞書を書き換えるため、元の `_MOCK_ANALYSIS` が変更されないようにコピーを渡す。コピーしないと2回目以降のテストで `_MOCK_ANALYSIS` に `song_title` が残って意図しない状態になる
- `with` ブロックを抜けると `analyze` は元の本物の処理に戻る

#### `test_upload_file_too_large`（52〜55行目）

```python
def test_upload_file_too_large(client):
    _register_and_login(client)
    oversized = b"\x00" * (50 * 1024 * 1024 + 1)
    res = _upload(client, content=oversized)
    assert res.status_code == 400
```

- `b"\x00" * (50 * 1024 * 1024 + 1)` — 50MB + 1バイト = 52,428,801バイトのゼロ埋めデータ。`_validate_file_size()` の条件 `len(content) > max_size` を満たすために 1バイト超過させている
- `content=` を指定しているので WAV の自動生成は行われない。`content_type` はデフォルト `"audio/wav"` のため、ファイル形式チェックは通り、サイズチェックで 400 が返る

#### `test_get_analysis_success`（63〜68行目）

```python
def test_get_analysis_success(client):
    _register_and_login(client)
    with patch("api.analysis.audio_analyzer.analyze", return_value=dict(_MOCK_ANALYSIS)):
        analysis_id = _upload(client).json()["analysis_id"]

    res = client.get(f"/api/v1/analysis/{analysis_id}")
    assert res.status_code == 200
    assert res.json()["analysis_id"] == analysis_id
```

- `_upload(client).json()["analysis_id"]` — アップロードのレスポンスから `analysis_id` を取り出して変数に入れる。1行でつなげて書けるのはメソッドチェーンのため
- `patch` ブロックは `_upload` の呼び出しだけを囲んでいる。その後の GET リクエストには分析処理は走らないので `patch` は不要
- `f"/api/v1/analysis/{analysis_id}"` の `f""` はf文字列。`{}` の中に変数を書くと文字列に埋め込まれる（例: `analysis_id=5` なら `"/api/v1/analysis/5"` になる）

#### `test_get_analysis_unauthenticated`（70〜76行目）

```python
def test_get_analysis_unauthenticated(client):
    _register_and_login(client)
    with patch(...):
        analysis_id = _upload(client).json()["analysis_id"]

    client.post("/api/v1/auth/logout")
    res = client.get(f"/api/v1/analysis/{analysis_id}")
    assert res.status_code == 401
```

「アップロードしたが、その後ログアウトしてからアクセスすると 401」という流れ。登録→アップロードしてデータを作ってから、ログアウトして未認証状態にして確認する。

#### 2ユーザーを使う 403 テスト（78〜86行目）

```python
def test_get_analysis_other_user_returns_403(client):
    _register_and_login(client, email="user_a@example.com")
    with patch(...):
        analysis_id = _upload(client).json()["analysis_id"]

    client.post("/api/v1/auth/logout")
    _register_and_login(client, email="user_b@example.com")
    res = client.get(f"/api/v1/analysis/{analysis_id}")
    assert res.status_code == 403
```

同じ `client` を使ってユーザーを切り替えている：
1. User A でログインしてアップロード → `analysis_id` を取得
2. ログアウト（クッキーを削除）
3. User B で登録・ログイン（クッキーが User B のものに変わる）
4. User A の `analysis_id` に User B でアクセス → 403

これで「他人のデータに触れられないか（認可）」を確認できる。

#### テスト一覧と意図

**POST /upload**

| テスト | 確認すること |
|---|---|
| `test_upload_unauthenticated` | 未認証で 401 が返るか |
| `test_upload_invalid_file_type` | 非対応MIMEタイプで 400 が返るか |
| `test_upload_file_too_large` | 50MB超過で 400 が返るか |
| `test_upload_success` | 認証済み・有効ファイルで 200 と `analysis_id` が返るか |

**GET /{analysis_id}**

| テスト | 確認すること |
|---|---|
| `test_get_analysis_success` | 自分の分析結果が正しく返るか |
| `test_get_analysis_unauthenticated` | 未認証で 401 が返るか |
| `test_get_analysis_not_found` | 存在しない ID で 404 が返るか |
| `test_get_analysis_other_user_returns_403` | 他ユーザーの結果 ID で 403 が返るか |

**GET /user/statistics**

| テスト | 確認すること |
|---|---|
| `test_get_statistics_authenticated` | 認証済みで `history` / `total_count` が含まれるか |
| `test_get_statistics_unauthenticated` | 未認証で 401 が返るか |

## `nginx/default.conf` — リバースプロキシの設定

`server { }` が1つのサーバー定義で、その中に `location { }` が2つある。

**`listen 80;`**

nginxが80番ポートで接続を待ち受ける。`docker-compose.yml` の `ports: "80:80"` に対応。

**`location / { }` — フロントエンドへの転送**

`/` はすべてのURLにマッチする（最も広い条件）。`/api` にマッチしなかったリクエストがここに来る。

- `proxy_pass http://frontend:5173` — frontendサービスのVite開発サーバーに転送
- `proxy_http_version 1.1` / `Upgrade` / `Connection 'upgrade'` — ViteのホットリロードはWebSocketを使っているため必要。これがないとファイル変更時にブラウザが自動更新されない
- `proxy_set_header Host $host` — 元のリクエストのホスト名を転送先にそのまま渡す

**`location /api { }` — バックエンドへの転送**

URLが `/api` で始まるリクエストをbackendサービスのポート8000（FastAPI）に転送する。URLパスはそのまま引き継がれるため `/api/v1/analysis/upload` は `http://backend:8000/api/v1/analysis/upload` に転送される。

- `proxy_set_header X-Real-IP $remote_addr` — クライアントの本来のIPアドレスをバックエンドに伝える。nginxが中継役なので何もしないとバックエンドには「nginxのIPからリクエストが来た」と見えてしまう。nginxのIPが使われると全ユーザーが同じIPに見えるため、`auth_utils.py` のロックアウト（5回失敗で15分ブロック）が1人の失敗で全ユーザーをブロックしてしまう
- `proxy_read_timeout 300` / `proxy_connect_timeout 300` / `proxy_send_timeout 300` — 音声分析は処理に時間がかかるためタイムアウトを300秒（5分）に延ばしている。デフォルトは60秒

**疑問と回答:**
- Q: `X-Real-IP` がないとなぜよくないの？
- A: nginxのIPを渡すと全ユーザーが同じIPに見えてしまう。ロックアウット機能が1人の失敗で全ユーザーをブロックする事態になる。中継地点のIPを渡すと他のユーザーにも干渉するため `X-Real-IP` で本物のクライアントIPを渡す必要がある

## `docker-compose.yml` — 複数サービスの起動設定

`docker-compose up` を1回叩くだけで frontend / backend / db / redis / nginx の5サービスが連携して起動する。各サービスの定義を1ファイルにまとめている。

**`build: context:` と `image:` の違い**

| 書き方 | 意味 |
|---|---|
| `build: context: ./frontend` | 指定ディレクトリの `Dockerfile` を使って自分でイメージをビルドする |
| `image: postgres:15` | Docker Hub（公開イメージ置き場）から既製のイメージをダウンロードして使う |

`build: context: ./frontend` と書くと、DockerはそのディレクトリにあるDockerfileを自動的に探して使う。`image:` を使う場合はDockerfileを自分で書く必要はない。

**`ports:` — ポートマッピング**

`"8080:8000"` の左がホスト（自分のPC）、右がコンテナ内部のポート。`http://localhost:8080` でアクセスするとコンテナの8000番に届く。

**`volumes:` — マウント**

コンテナはデフォルトではホスト側のファイルが見えない独立した環境。マウントとはホスト側のディレクトリ/ファイルをコンテナ内の特定パスに「接続」する操作。

```yaml
- ./frontend:/app
```

ホスト `./frontend` とコンテナ内 `/app` が同じファイルを指すようになる。ホスト側でファイルを編集すると即コンテナ側にも反映される（ホットリロードが効く理由）。

```yaml
- /app/node_modules
```

`node_modules` はコンテナ内のものを使う（ホスト側のもので上書きしない）という指定。

**`environment:` — 環境変数**

コンテナ内の `os.environ` で読める値を設定する。`DATABASE_URL` の `@db:5432` の `db` はDockerの内部ネットワーク上のホスト名（サービス名がそのままホスト名になる）。`SECRET_KEY=${SECRET_KEY}` はホスト側の環境変数を参照する。`.env` ファイルか `export SECRET_KEY=...` で設定しておく必要がある。

**`depends_on:` — 起動順序**

`depends_on: backend` と書くと backend が起動してから frontend を起動する。`db` と `redis` より先に `backend` が起動するとエラーになるため、依存関係を明示する。

**DBの環境変数（初回起動時の自動作成）**

```yaml
POSTGRES_USER: postgres
POSTGRES_PASSWORD: postgres
POSTGRES_DB: vocal_analyzer
```

PostgreSQL公式イメージはこれらの環境変数を受け取ると、初回起動時に `CREATE USER` と `CREATE DATABASE` を自動実行する。コンテナはゼロから起動するため、DBユーザーとDBを自動で用意する仕組みが必要になる。

**named volume（名前付きボリューム）とは**

マウントには2種類ある：

| | bind mount | named volume |
|---|---|---|
| 例 | `./frontend:/app` | `postgres_data:/var/lib/postgresql/data` |
| 保存場所 | ホスト上の指定パス | Dockerが管理する専用領域 |
| 用途 | ソースコード共有（開発用） | DBデータの永続化 |

named volumeはDockerが管理する専用領域（WSL2では `/var/lib/docker/volumes/` 以下）に保存される。コンテナを削除してもデータが残り、`docker compose up` で再起動したとき前回のデータが再利用できる。

ファイルの末尾にある：

```yaml
volumes:
  postgres_data:
```

これは「`postgres_data` という名前のボリュームをDockerの管理対象として登録する」という宣言。宣言しておくことで `docker volume ls` で確認でき、`docker compose down` してもデータが消えない。名前付きボリュームは事前宣言が必要なルール。

**named volumeのセキュリティ**

- 他のコンテナやプロセスからは基本的にアクセスできない（そのボリュームをマウントしたコンテナのみ読み書き可能）
- ホストに侵入されたらデータにアクセスされるリスクはある
- ボリューム内のファイルは暗号化されていない（平文）
- 本番環境では暗号化ディスク（AWS EBSなど）を使うのが一般的

**リバースプロキシ（nginx）**

ブラウザとサーバーの間に立って、リクエストを適切なサービスに振り分ける役割。

```
ブラウザ → nginx（80番）
                 ├── /api/... → backend（8000番）に転送
                 └── /        → frontend（5173番）に転送
```

ユーザーからは `http://localhost` 1つに見えるが、裏ではnginxが仕分けをしている。nginxの設定は `./nginx/default.conf` をコンテナ内のnginxが設定ファイルを読む場所（`/etc/nginx/conf.d/default.conf`）にマウントして反映させる。

**疑問と回答:**
- Q: DBパスワードがハードコードされているのは問題ないの？
- A: ローカル開発専用の構成としてはよくある書き方。ただし本番環境では `POSTGRES_PASSWORD` をAWS Secrets Managerなどのシークレット管理ツールまたは環境変数で注入する必要がある。`SECRET_KEY` が `${SECRET_KEY}` で外部注入されているのに対して `POSTGRES_PASSWORD` がハードコードされている点は一貫性がないため、SPEC.mdのセキュリティセクションに本番対応の注記を追記した。

## `python-jose` → `PyJWT` への移行（Phase 5.5→6 の準備）

`python-jose` にCVE-2024-33663（ECDSA署名検証の脆弱性）が報告されており、`PyJWT` へ切り替えた。

### CVEとは

CVE（Common Vulnerabilities and Exposures）はセキュリティ上の脆弱性に振られる識別番号。番号を検索するとどんな脆弱性かを調べられる。

### PyJWT が推奨される理由

| | python-jose | PyJWT |
|---|---|---|
| メンテナンス | 停滞気味 | 活発 |
| 信頼性 | CVE報告あり | Django・Flask公式でも採用 |
| API互換性 | — | ほぼ同じ書き方で移行可能 |

### 変更内容

**`requirements.txt`**
```
# Before
python-jose[cryptography]==3.3.0

# After
PyJWT==2.12.1
```

**`auth_utils.py`**
```python
# Before
from jose import JWTError, jwt
except (JWTError, KeyError, ValueError):

# After
import jwt
except (jwt.InvalidTokenError, KeyError, ValueError):
```

`jwt.encode()` / `jwt.decode()` の書き方はどちらも同じで変更不要。

### バージョン選定の考え方

- セキュリティ問題が起点の移行なので、最新安定版（2.12.1）を選ぶ
- 古いバージョンを固定すると、そのバージョン自体に別の脆弱性があった場合に意味がなくなる
- プロジェクト全体が `==` で固定する方針なので `==` で合わせる

### PyPI名とimport名の違い

Pythonでは `pip install` するときの名前（PyPI名）と `import` するときの名前が異なるケースがある：

| pip install | import |
|---|---|
| `PyJWT` | `import jwt` |
| `Pillow` | `import PIL` |
| `scikit-learn` | `import sklearn` |

---

## SQLiteインメモリDBとStaticPool

### 問題：`no such table` エラー

`conftest.py` で `Base.metadata.create_all(bind=engine)` を実行してもテスト実行時に `no such table: users` エラーが発生した。

原因は SQLite の `sqlite:///:memory:` の仕様にある。

**SQLiteインメモリDBは接続ごとに別のDBが作られる。**

```
接続A（create_all）→ テーブル作成された空のDB
接続B（TestingSessionLocal）→ 別の空のDB（テーブルがない）
```

`create_all` でテーブルを作っても、`TestingSessionLocal()` が開く接続には別の空のDBが見えるため "no such table" になる。

### 解決：StaticPool

`StaticPool` はエンジン内のすべての接続が**同じ1つのSQLite接続を使いまわす**ようにするオプション。

```python
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # 全接続が同一のDB接続を共有する
)
```

これにより「インメモリDBが1つ存在し、全員がそれを共有する」状態になる。ディスクには何も書かない。

各テスト後に `Base.metadata.drop_all(bind=engine)` でテーブルを全削除するため、テスト間の独立性は維持される。

### deprecated（非推奨）と removed（削除済み）の違い

| 状態 | 意味 | 動作 |
|---|---|---|
| **deprecated** | 将来削除する予定。今はまだ動く | 警告が出るが実行される |
| **removed** | 削除済み | `ImportError` / `AttributeError` が発生して動かない |

Python の `crypt` 標準ライブラリモジュールは Python 3.12 で deprecated になり、3.13 で removed になった。passlib は内部でこのモジュールを `from crypt import crypt as _crypt` でインポートしているため、Python 3.13 環境ではモジュールロード自体が失敗する。

---

## passlib → bcrypt 直接利用への移行

### 移行の背景

- passlib のメンテナンスが停滞しており、Python 3.13 対応が見込めない
- passlib は `crypt` 標準ライブラリ（Python 3.13 で削除済み）をモジュールロード時にインポートする
- bcrypt はすでに `requirements.txt` に入っており、passlib を外してもアルゴリズム自体は変わらない

### bcrypt の直接API

```python
import bcrypt

# ハッシュ化
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# 検証
bcrypt.checkpw(plain_password.encode(), hashed_password.encode())  # True / False
```

| 引数 | 説明 |
|---|---|
| `password.encode()` | 文字列 → バイト列に変換（bcrypt は bytes しか受け取らない） |
| `bcrypt.gensalt()` | ランダムなソルト（毎回異なる）を生成。同じパスワードでも毎回異なるハッシュになる |
| `.decode()` | バイト列 → 文字列に変換してDBに保存できる形にする |

### passlib との比較

| | passlib | bcrypt 直接 |
|---|---|---|
| コード量 | `CryptContext` の設定が必要 | import だけで使える |
| 柔軟性 | 複数アルゴリズムの切り替えが容易 | bcrypt 固定 |
| Python 3.13 | 非対応（crypt モジュール依存） | 問題なし |

### `DUMMY_HASH` の変更

タイミング攻撃対策のダミーハッシュも bcrypt で生成するよう変更した。

```python
# Before（passlib）
DUMMY_HASH = pwd_context.hash("dummy")

# After（bcrypt 直接）
DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()
```

`b"dummy"` はバイトリテラル（バイト列の文字列リテラル）。`"dummy".encode()` と同じ意味。

`PyJWT` をインストールしても `import PyJWT` ではなく `import jwt` と書く。
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
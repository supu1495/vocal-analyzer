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
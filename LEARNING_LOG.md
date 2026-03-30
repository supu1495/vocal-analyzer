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


"""
.env の秘密情報を生成するスクリプト
.env.example を読み、秘密情報の行だけランダムな値に置き換えて画面（標準出力）に出す
今の .env を誤って消さないよう、.env を直接書き換えることはしない

使い方:
  python3 scripts/gen_secrets.py              # .env の雛形を丸ごと出す（新しく環境を作るとき）
  python3 scripts/gen_secrets.py SECRET_KEY   # 指定した項目の行だけ出す（今の .env の値を差し替えるとき）
"""

import secrets
import sys
from pathlib import Path

_ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"

# 項目名 → 生成するバイト数（16進数で出すので、文字数はバイト数の2倍になる）
# 16進数（0-9a-f）だけなので、DATABASE_URL / REDIS_URL やコマンド引数に埋め込んでも壊れない
_SECRET_BYTES = {
    "SECRET_KEY": 32,         # 64文字 = 256bit（RFC 7518 §3.2: HS256 の鍵は 256bit 以上）
    "POSTGRES_PASSWORD": 16,  # 32文字
    "REDIS_PASSWORD": 16,     # 32文字
}


def _exit_with_error(message: str) -> None:
    print(f"エラー: {message}", file=sys.stderr)
    sys.exit(1)


def _generate_line(name: str) -> str:
    return f"{name}={secrets.token_hex(_SECRET_BYTES[name])}"


def _key_of(line: str) -> str | None:
    """「KEY=値」の行なら KEY を返す。コメント行・空行は None"""
    if line.lstrip().startswith("#") or "=" not in line:
        return None
    return line.split("=", 1)[0].strip()


def render_env_template() -> str:
    """.env.example の秘密情報の行だけを生成した値に置き換えた文字列を返す"""
    example_lines = _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()

    # .env.example に項目がないと、雛形から何も言わずに抜け落ちるので止める
    found_keys = {_key_of(line) for line in example_lines}
    missing = [name for name in _SECRET_BYTES if name not in found_keys]
    if missing:
        _exit_with_error(f".env.example に {', '.join(missing)} の行がありません")

    output_lines = []
    for line in example_lines:
        if _key_of(line) in _SECRET_BYTES:
            line = _generate_line(_key_of(line))
        output_lines.append(line)
    return "\n".join(output_lines) + "\n"


def main() -> None:
    requested = sys.argv[1:]
    if not requested:
        print(render_env_template(), end="")
        return

    unknown = [name for name in requested if name not in _SECRET_BYTES]
    if unknown:
        _exit_with_error(
            f"生成できない項目です: {', '.join(unknown)}"
            f"（指定できるのは {', '.join(_SECRET_BYTES)}）"
        )
    for name in requested:
        print(_generate_line(name))


if __name__ == "__main__":
    main()

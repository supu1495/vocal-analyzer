"""
音声分析APIエンドポイント
音声ファイルのアップロード・分析結果の取得・統計情報の取得を担当する
"""

# asyncio: ffprobe の実行を別スレッドに逃がすため（upload_audio は async def なので、そのまま待つと backend 全体が止まる）
import asyncio
import logging
import os
# subprocess: 録音の長さを ffprobe（コンテナに入っている外部プログラム）で測るため
import subprocess
import uuid
# datetime: 日付を作る関数の引数の型 ／ timezone: SQLite から返るタイムゾーンなしの日時を UTC とみなすため
from datetime import datetime, timezone
# ZoneInfo: 統計の日付を日本時間（Asia/Tokyo）にするため（upload_limits.py と同じ書き方）
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from audio.errors import INTERNAL, INVALID_FORMAT, NO_VOICE, TIMEOUT
from celery_app import celery_app
from task_failures import get_failure_reason
from tasks import analyze_audio_task
from auth_utils import get_current_user, get_task_owner, save_task_owner
from database import get_db
from models import AnalysisResult, User
from upload_limits import (
    acquire_analysis_slot,
    count_daily_upload,
    daily_limit_retry_after,
    daily_upload_limit,
    release_analysis_slot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# 共有ボリュームの一時ファイル置き場
_UPLOAD_DIR = "/tmp/vocal_analyzer"

# アップロード上限とストリーミング読み込みのチャンクサイズ
# Cloudflare（Free・Pro）は1回のリクエストが100MBまで。multipart の区切りの分も見て余裕を取る（#13）
_MAX_FILE_SIZE = 90 * 1024 * 1024  # 90MB
_CHUNK_SIZE = 1024 * 1024           # 1MB

# 楽曲名・アーティスト名の上限（DB は255文字。分析が終わった後の保存で失敗しないよう、受け付け時に断る）
_MAX_TEXT_LENGTH = 70

# 形式の1次フィルタ。MIME はブラウザや OS で名前が違う（audio/x-wav・audio/m4a 等）ため、拡張子が合っていても通す
# どちらも偽装できるので、中身は _validate_audio_magic_bytes で確かめる
_ALLOWED_CONTENT_TYPES = {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/m4a"}
_ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a"}

# 分析できる録音の長さの上限（#13）。分析は録音の約1.3倍かかり、celery_app.py の時間制限はこれに合わせる
_MAX_DURATION_SECONDS = 10 * 60
# ffprobe が壊れたファイルで固まったときに打ち切るまでの秒数。普通は1秒かからない
_FFPROBE_TIMEOUT_SECONDS = 30

_UNREADABLE_AUDIO_DETAIL = "音声ファイルを読み込めませんでした。別の形式で試してください。"

# 統計の日付は日本時間で区切る（DB は UTC で保存している。upload_limits.py の1日の回数と同じ区切り）
# upload_limits.py の _JST はファイルの中だけで使う約束（名前が _ で始まる）なので、借りずに同じ定義を書く
_JST = ZoneInfo("Asia/Tokyo")

# 分析が失敗したときに利用者に見せる文言（reason は audio/errors.py）
_FAILURE_MESSAGES = {
    INVALID_FORMAT: "音声ファイルを読み込めませんでした。別の形式で試してください。",
    NO_VOICE: "歌声を検出できませんでした。歌声が入った録音か確かめてください。",
    TIMEOUT: "分析に時間がかかりすぎたため中止しました。短い録音で試してください。",
    INTERNAL: "分析中にエラーが発生しました。",
}


@router.post("/upload")
async def upload_audio(
    audio_file: UploadFile = File(...),
    song_title: str = "",
    artist_name: str = "",
    current_user: User = Depends(get_current_user),
):
    """
    音声ファイルをアップロードして分析タスクをキューに登録する

    - audio_file: 音声ファイル（WAV/MP3/M4A）
    - song_title: 楽曲名（任意）
    - artist_name: アーティスト名（任意）
    - 戻り値: task_id（ステータス確認に使用）
    - 同時に分析できるのは1人1件。分析中なら 429
    - 1日（日本時間0時区切り）の回数に上限がある。超えたら 429（Retry-After: 次の0時までの秒数）
    - 免責事項に同意していなければ 403
    """
    # フロントで免責事項を出すだけだと API を直接呼べば通るので、ここでも確かめる
    if not current_user.disclaimer_accepted:
        logger.warning("Upload rejected (disclaimer not accepted): user_id=%d", current_user.id)
        raise HTTPException(status_code=403, detail="利用を始める前に、免責事項への同意が必要です。")

    _validate_text_lengths(song_title, artist_name)
    _validate_audio_type(audio_file)

    retry_after = daily_limit_retry_after(current_user.id)
    if retry_after is not None:
        logger.warning(
            "Upload rejected (daily limit reached): user_id=%d retry_after=%d",
            current_user.id, retry_after,
        )
        raise HTTPException(
            status_code=429,
            detail=f"今日のアップロード上限（{daily_upload_limit()}回）に達しました。日本時間の0時以降にお試しください。",
            headers={"Retry-After": str(retry_after)},
        )

    if not acquire_analysis_slot(current_user.id):
        logger.warning("Upload rejected (analysis in progress): user_id=%d", current_user.id)
        raise HTTPException(
            status_code=429,
            detail="分析中の音声があります。終わってから次をアップロードしてください。",
        )

    logger.info(
        "Upload received: user_id=%d extension=%s content_type=%s",
        current_user.id, _file_extension(audio_file), audio_file.content_type,
    )

    tmp_path = None
    try:
        tmp_path = await _stream_to_shared_volume(audio_file)
        await _validate_audio_duration(tmp_path)
        task = analyze_audio_task.delay(tmp_path, song_title, artist_name, current_user.id)
    except Exception:
        # タスクに登録できなかったときは、分析中の印をここで外す（登録後は tasks.py の finally で外す）
        release_analysis_slot(current_user.id)
        # 保存まで済んだファイルは、ここで消す（登録後は tasks.py が消す）。書き途中のファイルは _stream_to_shared_volume が消す
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # 数えるのはタスクに登録できたときだけ（弾かれたファイルは数えない）
    count_daily_upload(current_user.id)
    save_task_owner(task.id, current_user.id)
    logger.info("Task queued: task_id=%s user_id=%d", task.id, current_user.id)

    return {
        "task_id": task.id,
        "status": "processing",
    }


@router.get("/status/{task_id}")
def get_analysis_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    タスクの進捗を確認する

    - task_id: アップロード時に返された task_id
    - 戻り値: status（PENDING / SUCCESS / FAILURE）と analysis_id（完了時のみ）
    - 失敗時は reason（invalid_format / no_voice / timeout / internal）と、利用者向けの detail も返す
    - 本人のタスクでなければ 404（他人のタスク・存在しないタスクを区別せず、存在を推測させない）
    """
    owner_id = get_task_owner(task_id)
    if owner_id != current_user.id:
        if owner_id is not None:
            logger.warning(
                "Forbidden task status access: requester_id=%d task_id=%s owner_id=%d",
                current_user.id, task_id, owner_id,
            )
        raise HTTPException(status_code=404, detail="分析タスクが見つかりません。")

    # アプリを明示的に渡さないと DisabledBackend を見に行って AttributeError になる
    result = celery_app.AsyncResult(task_id)

    if result.status == "SUCCESS":
        return {"status": "SUCCESS", "analysis_id": result.result}

    if result.status == "FAILURE":
        # 記録が無い（worker の強制終了など）・知らない値のときは internal として返す
        reason = get_failure_reason(task_id)
        if reason not in _FAILURE_MESSAGES:
            reason = INTERNAL
        return {"status": "FAILURE", "reason": reason, "detail": _FAILURE_MESSAGES[reason]}

    return {"status": result.status}


def _to_jst_date_label(created_at: datetime) -> str:
    """分析した日時を、グラフに出す日本時間の「月/日」にする"""
    # PostgreSQL はタイムゾーン付きの日時を返すので、そのまま日本時間に変換できる
    # テストの SQLite はタイムゾーンを持たない日時を返す。保存したのは UTC なので、UTC とみなす
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at.astimezone(_JST).strftime("%m/%d")


@router.get("/user/statistics")
def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ログインユーザーの分析結果統計を返す

    ダッシュボード画面のグラフ・サマリー表示に使用する
    """
    results = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.user_id == current_user.id)
        .order_by(AnalysisResult.created_at.asc())
        .all()
    )

    history = [
        {
            "date": _to_jst_date_label(record.created_at),
            "pitch": round(record.pitch_accuracy) if record.pitch_accuracy is not None else 0,
            "rhythm": round(record.rhythm_score) if record.rhythm_score is not None else 0,
        }
        for record in results
    ]

    pitch_values = [h["pitch"] for h in history]
    growth_rate = _calculate_growth_rate(pitch_values)

    return {
        "history": history,
        "total_count": len(history),
        "best_pitch": max(pitch_values) if pitch_values else 0,
        "growth_rate": growth_rate,
    }


@router.get("/{analysis_id}")
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    指定IDの分析結果を取得する

    - analysis_id: ステータス確認で返された analysis_id
    - ログインユーザー自身の分析結果のみ取得可能
    """
    result = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="分析結果が見つかりません。")
    if result.user_id != current_user.id:
        logger.warning(
            "Forbidden access attempt: requester_id=%d analysis_id=%d owner_id=%d",
            current_user.id, analysis_id, result.user_id,
        )
        raise HTTPException(status_code=403, detail="この分析結果へのアクセス権限がありません。")

    return {
        "analysis_id": result.id,
        "song_title": result.song_title,
        "artist_name": result.artist_name,
        "result": {
            "pitch_accuracy": result.pitch_accuracy,
            "rhythm_score": result.rhythm_score,
            "techniques": result.techniques,
            "vocal_range": result.vocal_range,
            "score_matrix": {
                "total_score": result.total_score,
                "faithfulness_score": result.faithfulness_score,
                "technique_score": result.technique_score,
                "naturalness_penalty": result.naturalness_penalty,
            },
            "feedback": result.feedback,
        },
    }


# ── プライベート関数 ──────────────────────────────────────────────────────────


def _validate_text_lengths(song_title: str, artist_name: str) -> None:
    """楽曲名・アーティスト名が _MAX_TEXT_LENGTH 文字以下か確かめる（ファイルを受け取る前に断るため最初に呼ぶ）"""
    too_long = [
        label
        for label, value in (("楽曲名", song_title), ("アーティスト名", artist_name))
        if len(value) > _MAX_TEXT_LENGTH
    ]
    if too_long:
        logger.warning(
            "Upload rejected (text too long): song_title_len=%d artist_name_len=%d",
            len(song_title), len(artist_name),
        )
        raise HTTPException(
            status_code=400,
            detail=f"{'・'.join(too_long)}は{_MAX_TEXT_LENGTH}文字以下にしてください。",
        )


def _validate_audio_type(audio_file: UploadFile) -> None:
    """Content-Type か拡張子で1次フィルタする（どちらも偽装可能なため後段の magic bytes 検証と併用する）"""
    if (
        audio_file.content_type not in _ALLOWED_CONTENT_TYPES
        and _file_extension(audio_file) not in _ALLOWED_EXTENSIONS
    ):
        logger.warning(
            "Upload rejected (invalid content-type): extension=%s content_type=%s",
            _file_extension(audio_file), audio_file.content_type,
        )
        raise HTTPException(
            status_code=400,
            detail="対応していないファイル形式です。WAV/MP3/M4Aのみ対応しています。",
        )


def _file_extension(audio_file: UploadFile) -> str:
    """ログ用の拡張子（例: ".m4a"）。ファイル名には本人の名前などが入りうるため、名前そのものはログに出さない"""
    return os.path.splitext(audio_file.filename or "")[1].lower()


def _validate_audio_magic_bytes(head: bytes) -> None:
    """ファイル先頭バイト（magic bytes）で音声形式を検証する。

    Content-Type はブラウザが付ける任意のヘッダで偽装可能なため、ファイルの実体
    から判別する。WAV/MP3/M4A 以外は拒否する。
    """
    if len(head) < 12:
        logger.warning("Upload rejected (file too small): bytes=%d", len(head))
        raise HTTPException(status_code=400, detail="ファイルが破損しているか小さすぎます。")

    # WAV: "RIFF" + サイズ(4byte) + "WAVE"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return
    # MP3: ID3v2 タグ付き
    if head[:3] == b"ID3":
        return
    # MP3: 裸の MPEG オーディオフレーム sync (0xFFEx〜0xFFFx)
    if head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return
    # M4A: ISO Base Media File Format。offset 4 から "ftyp"
    if head[4:8] == b"ftyp":
        return

    logger.warning("Upload rejected (magic bytes mismatch)")
    raise HTTPException(
        status_code=400,
        detail="ファイル内容が WAV/MP3/M4A のいずれにも一致しません。",
    )


async def _stream_to_shared_volume(audio_file: UploadFile) -> str:
    """
    アップロードファイルをチャンク単位で共有ボリュームに書き込む。

    _MAX_FILE_SIZE を超えた時点で書き込みを中止し、書き途中のファイルを削除して拒否する。
    最初のチャンクで magic bytes 検証を行い、Content-Type 偽装に対する追加防御とする。
    メモリ使用量を _CHUNK_SIZE 程度に抑えるためファイル全体を一括で読み込まない。

    ファイル名衝突を避けるため UUID をプレフィックスに付ける。
    """
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    # 利用者のファイル名から取る拡張子は、知っているものだけ残す（MIME だけで通ったファイルは拡張子なし）
    # 拡張子が無ければ separator.py の _to_wav が ffmpeg で WAV に変換するので、分析には影響しない
    extension = _file_extension(audio_file)
    suffix = extension if extension in _ALLOWED_EXTENSIONS else ""
    tmp_path = os.path.join(_UPLOAD_DIR, f"{uuid.uuid4()}{suffix}")

    total = 0
    first_chunk = True
    try:
        with open(tmp_path, "wb") as f:
            while chunk := await audio_file.read(_CHUNK_SIZE):
                if first_chunk:
                    _validate_audio_magic_bytes(chunk[:16])
                    first_chunk = False
                total += len(chunk)
                if total > _MAX_FILE_SIZE:
                    logger.warning(
                        "Upload rejected (size exceeded): bytes=%d limit=%d",
                        total, _MAX_FILE_SIZE,
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"ファイルが大きすぎます（上限 {_MAX_FILE_SIZE // (1024 * 1024)}MB）。"
                            "長い曲は m4a や mp3 で送ってください。"
                        ),
                    )
                f.write(chunk)
        return tmp_path
    except Exception:
        # 中止時は書き途中のファイルを残さない
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _probe_duration_seconds(path: str) -> float:
    """ffprobe で録音の長さ（秒）を測る。読めないときは HTTPException(400)

    引数はリストで渡し、shell を通さない（ファイル名がコマンドとして解釈されないように）。
    path は _stream_to_shared_volume が作った絶対パスなので、"-" で始まってオプションと取り違えられることもない
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=_FFPROBE_TIMEOUT_SECONDS,
        )
        # 長さが分からない形式では "N/A" が返り、float() が ValueError を投げる
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        # stderr には曲のタグ情報などが入りうるため、終了コードだけをログに出す（separator.py と同じ）
        logger.warning("Upload rejected (ffprobe failed): returncode=%d", e.returncode)
    except subprocess.TimeoutExpired:
        # timeout を超えると subprocess.run が子プロセスを kill してからこの例外を投げる
        logger.warning("Upload rejected (ffprobe timeout): timeout=%d", _FFPROBE_TIMEOUT_SECONDS)
    except ValueError:
        logger.warning("Upload rejected (duration unknown)")
    raise HTTPException(status_code=400, detail=_UNREADABLE_AUDIO_DETAIL)


async def _validate_audio_duration(path: str) -> None:
    """録音が _MAX_DURATION_SECONDS 以下か確かめる。超えたら HTTPException(400)

    ffprobe（最大 _FFPROBE_TIMEOUT_SECONDS 秒）を別スレッドで動かし、その間もほかのリクエストを処理できるようにする
    """
    duration = await asyncio.to_thread(_probe_duration_seconds, path)
    if duration > _MAX_DURATION_SECONDS:
        logger.warning(
            "Upload rejected (too long): duration=%.1f limit=%d", duration, _MAX_DURATION_SECONDS,
        )
        raise HTTPException(
            status_code=400,
            detail=f"録音が長すぎます（上限 {_MAX_DURATION_SECONDS // 60}分）。{_MAX_DURATION_SECONDS // 60}分以内に切って送ってください。",
        )


def _calculate_growth_rate(pitch_values: list[float]) -> int:
    """
    最初と最後のピッチスコアから成長率（%）を計算する
    データが2件未満の場合は0を返す
    """
    if len(pitch_values) < 2 or pitch_values[0] == 0:
        return 0
    growth = ((pitch_values[-1] - pitch_values[0]) / pitch_values[0]) * 100
    return round(growth)

import { API_BASE } from './types'

// API 呼び出しの共通処理（#13）
// - API_BASE と credentials: 'include'（Cookie の JWT を送る）を毎回付ける
// - ログインしたあとの操作で 401 が返ったら、App が登録した処理でログイン画面に戻す
// - エラーの文言を backend の detail から作る

export const SESSION_EXPIRED_MESSAGE = 'ログインの有効期限が切れました。再ログインしてください。'

// 401 を受けたときに呼ぶ処理。App が起動時に登録する
let sessionExpiredHandler: (() => void) | null = null

export function setSessionExpiredHandler(handler: (() => void) | null) {
  sessionExpiredHandler = handler
}

type ApiFetchOptions = RequestInit & {
  // ログインしていなくても 401 が返りうる呼び出し（/me・ログイン・ログアウト）で true にする
  // true のときは 401 でもログイン画面に戻す処理を呼ばず、Response をそのまま返す
  skipSessionExpired?: boolean
}

export async function apiFetch(path: string, options: ApiFetchOptions = {}): Promise<Response> {
  const { skipSessionExpired = false, ...init } = options
  const res = await fetch(`${API_BASE}${path}`, { ...init, credentials: 'include' })
  if (res.status === 401 && !skipSessionExpired) {
    sessionExpiredHandler?.()
    // 呼び出し元の続きの処理（結果の確認など）を止めるため、例外にする
    throw new Error(SESSION_EXPIRED_MESSAGE)
  }
  return res
}

// 422 の detail の loc（例: ["body", "email"]）の最後を、画面の欄の名前にする
const FIELD_LABELS: Record<string, string> = {
  email: 'メールアドレス',
  password: 'パスワード',
  invite_code: '招待コード',
  audio_file: '音声ファイル',
  song_title: '楽曲名',
  artist_name: 'アーティスト名',
}

function fieldLabel(loc: unknown): string {
  const field = Array.isArray(loc) ? loc[loc.length - 1] : undefined
  return (typeof field === 'string' && FIELD_LABELS[field]) || '入力内容'
}

// エラーのレスポンスから、画面に出す文言を作る
// - detail が文字列（HTTPException）ならそのまま
// - detail が配列（FastAPI の 422）なら、問題のある欄をまとめて「〇〇・〇〇を確認してください」
// - JSON でない（Cloudflare の 413 の HTML など）・detail が無いときは fallback か番号
export async function errorMessage(res: Response, fallback?: string): Promise<string> {
  const data = await res.json().catch(() => null)
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    // 同じ欄に複数のエラーがあっても1回だけ出す
    const labels = [...new Set(detail.map(item => fieldLabel(item?.loc)))]
    return `${labels.join('・')}を確認してください。`
  }
  return fallback ?? `サーバーエラー: ${res.status}`
}

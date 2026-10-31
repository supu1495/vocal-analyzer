import { useState, useEffect, type CSSProperties } from 'react'
import { API_BASE, type AuthState } from '../types'

// ログイン制限の解除時刻（ミリ秒）を保存するキー。再読み込みしても制限表示を復元するため
const LOCKED_UNTIL_KEY = 'vocal-analyzer-login-locked-until'
// サーバーが Retry-After を返さなかったときに使うロック時間（サーバー側の15分に合わせる）
const DEFAULT_LOCKOUT_SECONDS = 15 * 60

// localStorage はプライベートブラウズ等で使えないことがあるため、失敗しても画面は動かす
function loadLockedUntil(): number | null {
  try {
    const lockedUntil = Number(localStorage.getItem(LOCKED_UNTIL_KEY))
    if (lockedUntil > Date.now()) return lockedUntil
    localStorage.removeItem(LOCKED_UNTIL_KEY)
  } catch {
    // 読めなければ制限なしとして始める（実際の制限はサーバーがかける）
  }
  return null
}

function saveLockedUntil(lockedUntil: number) {
  try {
    localStorage.setItem(LOCKED_UNTIL_KEY, String(lockedUntil))
  } catch {
    // 保存できなければ再読み込みで表示が消えるだけ
  }
}

function clearLockedUntil() {
  try {
    localStorage.removeItem(LOCKED_UNTIL_KEY)
  } catch {
    // 消せなくても次回の読み込み時に期限切れとして扱われる
  }
}

// Retry-After（秒）から解除時刻を求める。表示（分単位）と実際の解除がずれないよう分に切り上げる
function lockedUntilFromRetryAfter(retryAfterHeader: string | null): number {
  const retryAfter = Number(retryAfterHeader)
  const seconds = retryAfter > 0 ? retryAfter : DEFAULT_LOCKOUT_SECONDS
  const ONE_MINUTE_MS = 60 * 1000
  return Math.ceil((Date.now() + seconds * 1000) / ONE_MINUTE_MS) * ONE_MINUTE_MS
}

function formatClockTime(time: number): string {
  return new Date(time).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
}

export function AuthScreen({
  mode,
  onSuccess,
  onToggle,
}: {
  mode: 'login' | 'register'
  onSuccess: (auth: AuthState) => void
  onToggle: () => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // 初回表示時に localStorage から復元する（再読み込みで制限表示が消えないように）
  const [lockedUntil, setLockedUntil] = useState<number | null>(loadLockedUntil)
  const locked = lockedUntil !== null

  const isLogin = mode === 'login'

  useEffect(() => {
    if (lockedUntil === null) return
    const timer = setTimeout(() => {
      clearLockedUntil()
      setLockedUntil(null)
    }, lockedUntil - Date.now())
    return () => clearTimeout(timer)
  }, [lockedUntil])

  const handleSubmit = async () => {
    setError('')
    if (!email || !password) {
      setError('メールアドレスとパスワードを入力してください。')
      return
    }
    if (!isLogin && !inviteCode.trim()) {
      setError('招待コードを入力してください。')
      return
    }
    if (!isLogin && password.length < 8) {
      setError('パスワードは8文字以上で設定してください。')
      return
    }
    setLoading(true)
    try {
      const endpoint = isLogin ? `${API_BASE}/api/v1/auth/login` : `${API_BASE}/api/v1/auth/register`
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        // 招待コードはコピー時に前後の空白・改行が入りやすく、1文字でも違うと 403 になるため trim する
        body: JSON.stringify(isLogin ? { email, password } : { email, password, invite_code: inviteCode.trim() }),
      })
      const data = await res.json()
      if (res.status === 429) {
        const until = lockedUntilFromRetryAfter(res.headers.get('Retry-After'))
        saveLockedUntil(until)
        setLockedUntil(until)
        setError(data.detail ?? 'ログイン試行回数が上限を超えました。しばらくしてから再試行してください。')
        return
      }
      if (!res.ok) throw new Error(data.detail ?? 'エラーが発生しました。')
      onSuccess({ userId: data.user_id, email: data.email, disclaimerAccepted: data.disclaimer_accepted })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'エラーが発生しました。')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle: CSSProperties = {
    width: '100%', padding: '12px 14px', background: '#0d0d1a',
    border: '1px solid #2a2a3e', borderRadius: '10px',
    color: 'white', fontSize: '14px', outline: 'none', boxSizing: 'border-box',
  }

  return (
    <div style={{ maxWidth: '400px', margin: '0 auto', padding: '80px 20px 40px' }}>
      <div style={{ marginBottom: '40px', textAlign: 'center' }}>
        <p style={{ color: '#c084fc', fontSize: '12px', letterSpacing: '0.2em', marginBottom: '12px' }}>VOCAL ANALYZER</p>
        <h1 style={{ fontSize: '26px', fontWeight: '800', color: 'white', marginBottom: '8px' }}>
          {isLogin ? 'ログイン' : 'アカウント作成'}
        </h1>
        <p style={{ color: '#555', fontSize: '13px' }}>
          {isLogin ? 'メールアドレスとパスワードでログインしてください。' : '招待コードを受け取った方のみ登録できます。'}
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '20px' }}>
        <div>
          <label style={{ color: '#666', fontSize: '11px', letterSpacing: '0.1em', display: 'block', marginBottom: '6px' }}>
            メールアドレス
          </label>
          <input
            type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="user@example.com" style={inputStyle}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          />
        </div>
        <div>
          <label style={{ color: '#666', fontSize: '11px', letterSpacing: '0.1em', display: 'block', marginBottom: '6px' }}>
            パスワード{!isLogin && '（8文字以上）'}
          </label>
          <input
            type="password" value={password} onChange={e => setPassword(e.target.value)}
            placeholder="••••••••" style={inputStyle}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          />
        </div>
        {!isLogin && (
          <div>
            <label style={{ color: '#666', fontSize: '11px', letterSpacing: '0.1em', display: 'block', marginBottom: '6px' }}>
              招待コード
            </label>
            {/* type="text": 貼り付けたコードが正しいか目で確かめられるように */}
            <input
              type="text" value={inviteCode} onChange={e => setInviteCode(e.target.value)}
              autoComplete="off" spellCheck={false} style={inputStyle}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            />
          </div>
        )}
      </div>

      {error && <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '16px', textAlign: 'center' }}>{error}</p>}

      <button
        onClick={handleSubmit} disabled={loading || locked}
        style={{
          width: '100%', padding: '14px',
          background: loading || locked ? '#1e1e2e' : 'linear-gradient(135deg, #c084fc, #818cf8)',
          border: 'none', borderRadius: '12px',
          color: loading || locked ? '#444' : 'white', fontSize: '15px', fontWeight: '700',
          cursor: loading || locked ? 'not-allowed' : 'pointer', transition: 'all 0.2s ease', marginBottom: '20px',
        }}
      >
        {locked ? `⏱ ログイン制限中（${formatClockTime(lockedUntil)} まで）` : loading ? '処理中...' : isLogin ? 'ログイン →' : '登録する →'}
      </button>

      <p style={{ textAlign: 'center', color: '#555', fontSize: '13px' }}>
        {isLogin ? 'アカウントがない方は' : 'すでにアカウントをお持ちの方は'}{' '}
        <span onClick={onToggle} style={{ color: '#c084fc', cursor: 'pointer', textDecoration: 'underline' }}>
          {isLogin ? '新規登録' : 'ログイン'}
        </span>
      </p>
    </div>
  )
}

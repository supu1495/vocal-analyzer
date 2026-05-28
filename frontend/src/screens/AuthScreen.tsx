import { useState, useEffect, type CSSProperties } from 'react'
import { API_BASE, type AuthState } from '../types'

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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [locked, setLocked] = useState(false)

  const isLogin = mode === 'login'

  useEffect(() => {
    if (!locked) return
    const LOCKOUT_MS = 15 * 60 * 1000
    const timer = setTimeout(() => setLocked(false), LOCKOUT_MS)
    return () => clearTimeout(timer)
  }, [locked])

  const handleSubmit = async () => {
    setError('')
    if (!email || !password) {
      setError('メールアドレスとパスワードを入力してください。')
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
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (res.status === 429) {
        setLocked(true)
        setError(data.detail ?? 'ログイン試行回数が上限を超えました。15分後に再試行してください。')
        return
      }
      if (!res.ok) throw new Error(data.detail ?? 'エラーが発生しました。')
      onSuccess({ userId: data.user_id, email: data.email })
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
          {isLogin ? 'メールアドレスとパスワードでログインしてください。' : 'メールアドレスとパスワードを登録してください。'}
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
        {locked ? '⏱ ログイン制限中（15分）' : loading ? '処理中...' : isLogin ? 'ログイン →' : '登録する →'}
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

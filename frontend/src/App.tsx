import { useState, useEffect } from 'react'
import { type Screen, type AuthState, type AnalysisResult } from './types'
import { apiFetch, setSessionExpiredHandler, SESSION_EXPIRED_MESSAGE } from './api'
import { AuthScreen } from './screens/AuthScreen'
import { UploadScreen } from './screens/UploadScreen'
import { ResultScreen } from './screens/ResultScreen'
import { DashboardScreen } from './screens/DashboardScreen'
import { DisclaimerScreen } from './screens/DisclaimerScreen'
import { VersionWarning } from './components/VersionWarning'

const AUTH_HINT_KEY = 'vocal-analyzer-auth-hint'

export default function App() {
  const [auth, setAuth] = useState<AuthState | null>(null)
  const [screen, setScreen] = useState<Screen>('login')
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  // ログイン画面の上に出す案内（ログインしたあとの操作で 401 が返ったときだけ入れる）
  const [authNotice, setAuthNotice] = useState('')

  // ログインしたあとの操作で 401 が返ったら、ログイン画面に戻して再ログインを案内する
  // 使うのは state の setter だけ（再描画で変わらない）なので、登録は最初の1回でよい
  useEffect(() => {
    setSessionExpiredHandler(() => {
      localStorage.removeItem(AUTH_HINT_KEY)
      setAuth(null)
      setAnalysisResult(null)
      setAuthNotice(SESSION_EXPIRED_MESSAGE)
      setScreen('login')
    })
    return () => setSessionExpiredHandler(null)
  }, [])

  useEffect(() => {
    if (localStorage.getItem(AUTH_HINT_KEY) !== 'yes') return

    // ログインしていない人には必ず 401 が返るので、期限切れの案内は出さず、ふつうのログイン画面のままにする
    apiFetch('/api/v1/auth/me', { skipSessionExpired: true })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data) {
          setAuth({ userId: data.user_id, email: data.email, disclaimerAccepted: data.disclaimer_accepted })
          setScreen('upload')
        } else {
          localStorage.removeItem(AUTH_HINT_KEY)
        }
      })
      .catch(() => {})
  }, [])

  const handleAuthSuccess = (newAuth: AuthState) => {
    localStorage.setItem(AUTH_HINT_KEY, 'yes')
    setAuthNotice('')
    setAuth(newAuth)
    setScreen('upload')
  }

  const handleLogout = () => {
    // 期限が切れたあとのログアウトも 401 になるが、どちらにしてもログイン画面に戻すので案内は出さない
    apiFetch('/api/v1/auth/logout', { method: 'POST', skipSessionExpired: true })
      .catch(() => {})
      .finally(() => {
        localStorage.removeItem(AUTH_HINT_KEY)
        setAuth(null)
        setAnalysisResult(null)
        setScreen('login')
      })
  }

  const handleResult = (result: AnalysisResult) => {
    setAnalysisResult(result)
    setScreen('result')
  }

  const handleDisclaimerAccepted = () => {
    setAuth(current => current && { ...current, disclaimerAccepted: true })
  }

  const isAuthScreen = screen === 'login' || screen === 'register'
  // 未同意のあいだは、どの画面を選んでも免責事項を出す（backend も未同意の upload を 403 で拒否する）
  const needsDisclaimer = auth !== null && !auth.disclaimerAccepted && !isAuthScreen

  return (
    // 縦の flex にして、<main> がヘッダーより下の残りの高さを全部使えるようにする（入力のかたまりを縦の真ん中に置くため）
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#080812', color: 'white' }}>
      <VersionWarning />
      {/* 下の線は画面いっぱいに引き、中身は共通の枠（--frame-width）に入れる */}
      <header style={{ borderBottom: '1px solid #0d0d1a' }}>
        <div style={{ maxWidth: 'var(--frame-width)', height: 'var(--header-height)', margin: '0 auto', padding: '0 var(--frame-gutter)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span
            onClick={() => auth && setScreen('upload')}
            style={{ color: '#c084fc', fontWeight: '800', fontSize: 'var(--logo-size)', cursor: auth ? 'pointer' : 'default', letterSpacing: '0.05em' }}
          >
            ◈ VOCAL ANALYSIS
          </span>

          {auth && !isAuthScreen ? (
            <nav style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {[{ id: 'upload', label: '分析' }, { id: 'dashboard', label: '統計' }].map(({ id, label }) => (
                <button key={id} onClick={() => setScreen(id as Screen)} style={{
                  background: screen === id ? 'rgba(192,132,252,0.15)' : 'none',
                  border: screen === id ? '1px solid rgba(192,132,252,0.3)' : '1px solid transparent',
                  borderRadius: '8px', color: screen === id ? '#c084fc' : '#555',
                  padding: '0.4em 1em', cursor: 'pointer', fontSize: 'var(--caption-size)', transition: 'all 0.2s',
                }}>{label}</button>
              ))}
              <span style={{ color: '#333', margin: '0 4px' }}>|</span>
              <span style={{ color: '#444', fontSize: 'var(--caption-size)' }}>{auth.email}</span>
              <button onClick={handleLogout} style={{ background: 'none', border: '1px solid #2a2a3e', borderRadius: '8px', color: '#555', padding: '0.4em 1em', cursor: 'pointer', fontSize: 'var(--caption-size)' }}>
                ログアウト
              </button>
            </nav>
          ) : <div />}
        </div>
      </header>

      {/* 各画面は、この枠の中で自分の幅にして中央に寄せる。縦の flex なので、.centered-block の画面は縦の真ん中に来る */}
      <main style={{ flex: 1, width: '100%', maxWidth: 'var(--frame-width)', margin: '0 auto', padding: '0 var(--frame-gutter)', display: 'flex', flexDirection: 'column' }}>
        {screen === 'login' && <AuthScreen mode="login" notice={authNotice} onSuccess={handleAuthSuccess} onToggle={() => { setAuthNotice(''); setScreen('register') }} />}
        {screen === 'register' && <AuthScreen mode="register" onSuccess={handleAuthSuccess} onToggle={() => setScreen('login')} />}
        {needsDisclaimer && <DisclaimerScreen onAccepted={handleDisclaimerAccepted} />}
        {!needsDisclaimer && screen === 'upload' && auth && <UploadScreen onResult={handleResult} />}
        {!needsDisclaimer && screen === 'result' && auth && analysisResult && (
          <ResultScreen result={analysisResult} onBack={() => setScreen('upload')} onDashboard={() => setScreen('dashboard')} />
        )}
        {!needsDisclaimer && screen === 'dashboard' && auth && (
          <DashboardScreen latestResult={analysisResult} onBack={() => setScreen(analysisResult ? 'result' : 'upload')} />
        )}
      </main>
    </div>
  )
}

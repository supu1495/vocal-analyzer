import { useState, useEffect } from 'react'
import { API_BASE, type Screen, type AuthState, type AnalysisResult } from './types'
import { AuthScreen } from './screens/AuthScreen'
import { UploadScreen } from './screens/UploadScreen'
import { ResultScreen } from './screens/ResultScreen'
import { DashboardScreen } from './screens/DashboardScreen'

const AUTH_HINT_KEY = 'vocal-analyzer-auth-hint'

export default function App() {
  const [auth, setAuth] = useState<AuthState | null>(null)
  const [screen, setScreen] = useState<Screen>('login')
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)

  useEffect(() => {
    if (localStorage.getItem(AUTH_HINT_KEY) !== 'yes') return

    fetch(`${API_BASE}/api/v1/auth/me`, { credentials: 'include' })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data) {
          setAuth({ userId: data.user_id, email: data.email })
          setScreen('upload')
        } else {
          localStorage.removeItem(AUTH_HINT_KEY)
        }
      })
      .catch(() => {})
  }, [])

  const handleAuthSuccess = (newAuth: AuthState) => {
    localStorage.setItem(AUTH_HINT_KEY, 'yes')
    setAuth(newAuth)
    setScreen('upload')
  }

  const handleLogout = () => {
    fetch(`${API_BASE}/api/v1/auth/logout`, { method: 'POST', credentials: 'include' })
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

  const isAuthScreen = screen === 'login' || screen === 'register'

  return (
    <div style={{ minHeight: '100vh', background: '#080812', color: 'white', fontFamily: "'Noto Sans JP', 'Hiragino Sans', sans-serif" }}>
      <header style={{ borderBottom: '1px solid #0d0d1a', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span
          onClick={() => auth && setScreen('upload')}
          style={{ color: '#c084fc', fontWeight: '800', fontSize: '16px', cursor: auth ? 'pointer' : 'default', letterSpacing: '0.05em' }}
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
                padding: '6px 14px', cursor: 'pointer', fontSize: '13px', transition: 'all 0.2s',
              }}>{label}</button>
            ))}
            <span style={{ color: '#333', margin: '0 4px' }}>|</span>
            <span style={{ color: '#444', fontSize: '12px' }}>{auth.email}</span>
            <button onClick={handleLogout} style={{ background: 'none', border: '1px solid #2a2a3e', borderRadius: '8px', color: '#555', padding: '6px 12px', cursor: 'pointer', fontSize: '12px' }}>
              ログアウト
            </button>
          </nav>
        ) : <div />}
      </header>

      <main>
        {screen === 'login' && <AuthScreen mode="login" onSuccess={handleAuthSuccess} onToggle={() => setScreen('register')} />}
        {screen === 'register' && <AuthScreen mode="register" onSuccess={handleAuthSuccess} onToggle={() => setScreen('login')} />}
        {screen === 'upload' && auth && <UploadScreen onResult={handleResult} />}
        {screen === 'result' && auth && analysisResult && (
          <ResultScreen result={analysisResult} onBack={() => setScreen('upload')} onDashboard={() => setScreen('dashboard')} />
        )}
        {screen === 'dashboard' && auth && (
          <DashboardScreen latestResult={analysisResult} onBack={() => setScreen(analysisResult ? 'result' : 'upload')} />
        )}
      </main>
    </div>
  )
}

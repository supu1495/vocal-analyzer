import { useState, useEffect, type CSSProperties } from 'react'

// --- 型定義 ---
type Screen = 'login' | 'register' | 'upload' | 'result' | 'dashboard'

interface AuthState {
  token: string
  userId: number
  email: string
}

interface AnalysisResult {
  analysis_id: string
  status: string
  song_title?: string
  artist_name?: string
  result: {
    pitch_accuracy: number
    rhythm_score: number
    techniques: {
      vibrato: { count: number; avg_frequency: number; avg_depth: number }
      kobushi: { count: number; timestamps: number[] }
      fall: { count: number; avg_depth: number }
      shakuri: { count: number; avg_height: number }
      long_tone: { count: number; avg_duration: number }
    }
    vocal_range?: { min_note: string; max_note: string; range_semitones: number }
    feedback?: string
  }
}

interface Statistics {
  history: { date: string; pitch: number; rhythm: number }[]
  total_count: number
  best_pitch: number
  growth_rate: number
}

// --- ローカルストレージキー ---
const AUTH_KEY = 'vocal_analyzer_auth'

function loadAuth(): AuthState | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveAuth(auth: AuthState) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth))
}

function clearAuth() {
  localStorage.removeItem(AUTH_KEY)
}

// --- 認証付きfetchヘルパー ---
function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` }
}

// --- UIパーツ ---

function ScoreRing({ score, label, color }: { score: number; label: string; color: string }) {
  const r = 36
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={r} fill="none" stroke="#1e1e2e" strokeWidth="8" />
        <circle
          cx="44" cy="44" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 44 44)"
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
        <text x="44" y="49" textAnchor="middle" fill="white" fontSize="16" fontWeight="700">
          {Math.round(score)}
        </text>
      </svg>
      <span style={{ color: '#888', fontSize: '12px', letterSpacing: '0.1em' }}>{label}</span>
    </div>
  )
}

function TechniqueBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ color: '#ccc', fontSize: '13px' }}>{label}</span>
        <span style={{ color: color, fontSize: '13px', fontWeight: '600' }}>{value}</span>
      </div>
      <div style={{ height: '4px', background: '#1e1e2e', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, background: color,
          borderRadius: '2px', transition: 'width 1s ease'
        }} />
      </div>
    </div>
  )
}

function LineChart({ data }: { data: Statistics['history'] }) {
  const w = 340; const h = 100; const pad = 20
  const maxVal = 100
  const xs = data.map((_, i) => pad + (i / (data.length - 1)) * (w - pad * 2))
  const yPitch = data.map(d => h - pad - ((d.pitch / maxVal) * (h - pad * 2)))
  const yRhythm = data.map(d => h - pad - ((d.rhythm / maxVal) * (h - pad * 2)))
  const toPath = (ys: number[]) =>
    ys.map((y, i) => `${i === 0 ? 'M' : 'L'} ${xs[i]} ${y}`).join(' ')
  return (
    <svg width={w} height={h} style={{ overflow: 'visible' }}>
      {[25, 50, 75].map(v => (
        <line key={v} x1={pad} x2={w - pad}
          y1={h - pad - (v / 100) * (h - pad * 2)}
          y2={h - pad - (v / 100) * (h - pad * 2)}
          stroke="#2a2a3e" strokeWidth="1" />
      ))}
      <path d={toPath(yPitch)} fill="none" stroke="#c084fc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d={toPath(yRhythm)} fill="none" stroke="#34d399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={xs[i]} cy={yPitch[i]} r="3" fill="#c084fc" />
          <circle cx={xs[i]} cy={yRhythm[i]} r="3" fill="#34d399" />
          <text x={xs[i]} y={h - 2} textAnchor="middle" fill="#555" fontSize="10">{d.date}</text>
        </g>
      ))}
    </svg>
  )
}

// =====================
// ログイン / 登録画面
// =====================
function AuthScreen({
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

  const isLogin = mode === 'login'

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
      const endpoint = isLogin ? '/api/v1/auth/login' : '/api/v1/auth/register'
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'エラーが発生しました。')
      const auth: AuthState = { token: data.access_token, userId: data.user_id, email: data.email }
      saveAuth(auth)
      onSuccess(auth)
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
        onClick={handleSubmit} disabled={loading}
        style={{
          width: '100%', padding: '14px',
          background: loading ? '#1e1e2e' : 'linear-gradient(135deg, #c084fc, #818cf8)',
          border: 'none', borderRadius: '12px',
          color: loading ? '#444' : 'white', fontSize: '15px', fontWeight: '700',
          cursor: loading ? 'not-allowed' : 'pointer', transition: 'all 0.2s ease', marginBottom: '20px',
        }}
      >
        {loading ? '処理中...' : isLogin ? 'ログイン →' : '登録する →'}
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

// =====================
// 画面1: アップロード
// =====================
function UploadScreen({ token, onResult }: { token: string; onResult: (r: AnalysisResult) => void }) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [songTitle, setSongTitle] = useState('')
  const [artistName, setArtistName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleFile = (f: File) => {
    const allowed = ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/x-m4a']
    if (!allowed.includes(f.type)) { setError('WAV / MP3 / M4A のみ対応しています'); return }
    setFile(f); setError('')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0])
  }

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true); setError('')
    try {
      const form = new FormData()
      form.append('audio_file', file)
      const url = `/api/v1/analysis/upload?song_title=${encodeURIComponent(songTitle)}&artist_name=${encodeURIComponent(artistName)}`
      const res = await fetch(url, { method: 'POST', headers: authHeaders(token), body: form })
      if (!res.ok) throw new Error(`サーバーエラー: ${res.status}`)
      const data: AnalysisResult = await res.json()
      onResult({ ...data, song_title: songTitle, artist_name: artistName })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '分析に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: '560px', margin: '0 auto', padding: '40px 20px' }}>
      <div style={{ marginBottom: '48px' }}>
        <p style={{ color: '#c084fc', fontSize: '12px', letterSpacing: '0.2em', marginBottom: '8px' }}>VOCAL ANALYZER</p>
        <h1 style={{ fontSize: '32px', fontWeight: '800', color: 'white', lineHeight: 1.2, marginBottom: '12px' }}>
          あなたの歌声を<br />分析しましょう
        </h1>
        <p style={{ color: '#666', fontSize: '14px' }}>カラオケ録音をアップロードして、AIが歌唱力を詳細分析します</p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('fileInput')?.click()}
        style={{
          border: `2px dashed ${dragging ? '#c084fc' : file ? '#34d399' : '#2a2a3e'}`,
          borderRadius: '16px', padding: '48px 24px', textAlign: 'center', cursor: 'pointer',
          background: dragging ? 'rgba(192,132,252,0.05)' : 'rgba(255,255,255,0.02)',
          transition: 'all 0.2s ease', marginBottom: '24px',
        }}
      >
        <input id="fileInput" type="file" accept=".wav,.mp3,.m4a,audio/*" style={{ display: 'none' }}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
        <div style={{ fontSize: '36px', marginBottom: '12px' }}>{file ? '🎵' : '🎤'}</div>
        {file ? (
          <>
            <p style={{ color: '#34d399', fontWeight: '600', marginBottom: '4px' }}>{file.name}</p>
            <p style={{ color: '#555', fontSize: '13px' }}>{(file.size / 1024 / 1024).toFixed(1)} MB</p>
          </>
        ) : (
          <>
            <p style={{ color: '#aaa', marginBottom: '4px' }}>音声ファイルをドロップ</p>
            <p style={{ color: '#555', fontSize: '13px' }}>または クリックして選択（WAV / MP3 / M4A）</p>
          </>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '24px' }}>
        {[
          { label: '楽曲名', value: songTitle, setter: setSongTitle, placeholder: 'Feeling' },
          { label: 'アーティスト', value: artistName, setter: setArtistName, placeholder: 'Mrs. GREEN APPLE' },
        ].map(({ label, value, setter, placeholder }) => (
          <div key={label}>
            <label style={{ color: '#666', fontSize: '11px', letterSpacing: '0.1em', display: 'block', marginBottom: '6px' }}>
              {label}（任意）
            </label>
            <input value={value} onChange={(e) => setter(e.target.value)} placeholder={placeholder}
              style={{ width: '100%', padding: '10px 12px', background: '#0d0d1a', border: '1px solid #2a2a3e',
                borderRadius: '8px', color: 'white', fontSize: '14px', outline: 'none', boxSizing: 'border-box' }} />
          </div>
        ))}
      </div>

      {error && <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '16px', textAlign: 'center' }}>{error}</p>}

      <button onClick={handleSubmit} disabled={!file || loading} style={{
        width: '100%', padding: '16px',
        background: file && !loading ? 'linear-gradient(135deg, #c084fc, #818cf8)' : '#1e1e2e',
        border: 'none', borderRadius: '12px',
        color: file && !loading ? 'white' : '#444', fontSize: '16px', fontWeight: '700',
        cursor: file && !loading ? 'pointer' : 'not-allowed', transition: 'all 0.2s ease', letterSpacing: '0.05em',
      }}>
        {loading ? '分析中...' : '分析を開始する →'}
      </button>
    </div>
  )
}

// =====================
// 画面2: 分析結果
// =====================
function ResultScreen({ result, onBack, onDashboard }: {
  result: AnalysisResult; onBack: () => void; onDashboard: () => void
}) {
  const r = result.result
  const t = r.techniques
  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', padding: '40px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
        <div>
          <p style={{ color: '#c084fc', fontSize: '12px', letterSpacing: '0.2em', marginBottom: '4px' }}>ANALYSIS RESULT</p>
          <h2 style={{ color: 'white', fontSize: '22px', fontWeight: '800', marginBottom: '2px' }}>
            {result.song_title || '無題の録音'}
          </h2>
          {result.artist_name && <p style={{ color: '#666', fontSize: '13px' }}>{result.artist_name}</p>}
        </div>
        <button onClick={onBack} style={{ background: 'none', border: '1px solid #2a2a3e', borderRadius: '8px', color: '#666', padding: '8px 16px', cursor: 'pointer', fontSize: '13px' }}>← 戻る</button>
      </div>

      <div style={{
        background: 'linear-gradient(135deg, rgba(192,132,252,0.1), rgba(129,140,248,0.05))',
        border: '1px solid rgba(192,132,252,0.2)', borderRadius: '16px', padding: '32px', marginBottom: '20px',
        display: 'flex', justifyContent: 'space-around', alignItems: 'center'
      }}>
        <ScoreRing score={r.pitch_accuracy} label="ピッチ精度" color="#c084fc" />
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: '#555', fontSize: '24px', marginBottom: '8px' }}>✦</div>
          <p style={{ color: '#888', fontSize: '11px', letterSpacing: '0.1em' }}>総合評価</p>
          <p style={{ color: 'white', fontSize: '28px', fontWeight: '800' }}>
            {Math.round((r.pitch_accuracy + r.rhythm_score) / 2)}
          </p>
        </div>
        <ScoreRing score={r.rhythm_score} label="リズム感" color="#34d399" />
      </div>

      <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #1e1e2e', borderRadius: '16px', padding: '24px', marginBottom: '20px' }}>
        <p style={{ color: '#888', fontSize: '11px', letterSpacing: '0.15em', marginBottom: '20px' }}>TECHNIQUES</p>
        <TechniqueBar label="ビブラート" value={t.vibrato.count} max={20} color="#c084fc" />
        <TechniqueBar label="こぶし" value={t.kobushi.count} max={20} color="#f472b6" />
        <TechniqueBar label="フォール" value={t.fall.count} max={20} color="#60a5fa" />
        <TechniqueBar label="しゃくり" value={t.shakuri.count} max={20} color="#fb923c" />
        <TechniqueBar label="ロングトーン" value={t.long_tone.count} max={20} color="#34d399" />
      </div>

      {r.feedback && (
        <div style={{ background: 'rgba(192,132,252,0.05)', border: '1px solid rgba(192,132,252,0.15)', borderRadius: '16px', padding: '20px', marginBottom: '20px' }}>
          <p style={{ color: '#c084fc', fontSize: '11px', letterSpacing: '0.15em', marginBottom: '10px' }}>FEEDBACK</p>
          <p style={{ color: '#ccc', fontSize: '14px', lineHeight: '1.6' }}>{r.feedback}</p>
        </div>
      )}

      <button onClick={onDashboard} style={{ width: '100%', padding: '14px', background: 'rgba(255,255,255,0.04)', border: '1px solid #2a2a3e', borderRadius: '12px', color: '#aaa', fontSize: '14px', cursor: 'pointer', transition: 'all 0.2s' }}>
        統計ダッシュボードを見る →
      </button>
    </div>
  )
}

// =====================
// 画面3: 統計ダッシュボード
// =====================
function DashboardScreen({ token, latestResult, onBack }: {
  token: string; latestResult: AnalysisResult | null; onBack: () => void
}) {
  const [stats, setStats] = useState<Statistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/v1/analysis/user/statistics', { headers: authHeaders(token) })
      .then(res => { if (!res.ok) throw new Error(`サーバーエラー: ${res.status}`); return res.json() })
      .then((data: Statistics) => setStats(data))
      .catch(e => setError(e instanceof Error ? e.message : '統計の取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [token])

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', padding: '40px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <p style={{ color: '#c084fc', fontSize: '12px', letterSpacing: '0.2em', marginBottom: '4px' }}>DASHBOARD</p>
          <h2 style={{ color: 'white', fontSize: '22px', fontWeight: '800' }}>歌唱力の推移</h2>
        </div>
        <button onClick={onBack} style={{ background: 'none', border: '1px solid #2a2a3e', borderRadius: '8px', color: '#666', padding: '8px 16px', cursor: 'pointer', fontSize: '13px' }}>← 戻る</button>
      </div>

      {loading && <p style={{ color: '#555', textAlign: 'center' }}>読み込み中...</p>}
      {error && <p style={{ color: '#f87171', textAlign: 'center' }}>{error}</p>}

      {stats && stats.history.length > 0 && (
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #1e1e2e', borderRadius: '16px', padding: '24px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '12px', height: '3px', background: '#c084fc', borderRadius: '2px' }} />
              <span style={{ color: '#888', fontSize: '12px' }}>ピッチ精度</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '12px', height: '3px', background: '#34d399', borderRadius: '2px' }} />
              <span style={{ color: '#888', fontSize: '12px' }}>リズム感</span>
            </div>
          </div>
          <LineChart data={stats.history} />
        </div>
      )}

      {stats && stats.history.length === 0 && !loading && (
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #1e1e2e', borderRadius: '16px', padding: '40px', marginBottom: '20px', textAlign: 'center' }}>
          <p style={{ color: '#555', fontSize: '14px' }}>まだ分析データがありません。</p>
          <p style={{ color: '#444', fontSize: '12px', marginTop: '8px' }}>音声をアップロードすると推移グラフが表示されます。</p>
        </div>
      )}

      {latestResult && (
        <div style={{ background: 'linear-gradient(135deg, rgba(192,132,252,0.08), rgba(52,211,153,0.05))', border: '1px solid rgba(192,132,252,0.15)', borderRadius: '16px', padding: '20px', marginBottom: '20px' }}>
          <p style={{ color: '#888', fontSize: '11px', letterSpacing: '0.15em', marginBottom: '16px' }}>LATEST SESSION</p>
          <div style={{ display: 'flex', justifyContent: 'space-around' }}>
            {[
              { label: 'ピッチ精度', value: Math.round(latestResult.result.pitch_accuracy), color: '#c084fc' },
              { label: 'リズム感', value: Math.round(latestResult.result.rhythm_score), color: '#34d399' },
              { label: '総合', value: Math.round((latestResult.result.pitch_accuracy + latestResult.result.rhythm_score) / 2), color: '#60a5fa' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ textAlign: 'center' }}>
                <p style={{ color, fontSize: '28px', fontWeight: '800', marginBottom: '4px' }}>{value}</p>
                <p style={{ color: '#666', fontSize: '12px' }}>{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
        {[
          { label: '総分析回数', value: stats?.total_count ?? '-', unit: '回' },
          { label: '最高ピッチ', value: stats?.best_pitch ?? '-', unit: 'pt' },
          { label: '成長率', value: stats ? `+${stats.growth_rate}` : '-', unit: '%' },
        ].map(({ label, value, unit }) => (
          <div key={label} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #1e1e2e', borderRadius: '12px', padding: '16px', textAlign: 'center' }}>
            <p style={{ color: 'white', fontSize: '22px', fontWeight: '800', marginBottom: '4px' }}>
              {value}<span style={{ fontSize: '12px', color: '#666' }}>{unit}</span>
            </p>
            <p style={{ color: '#555', fontSize: '11px' }}>{label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// =====================
// メインApp
// =====================
export default function App() {
  const [auth, setAuth] = useState<AuthState | null>(loadAuth)
  const [screen, setScreen] = useState<Screen>(() => (loadAuth() ? 'upload' : 'login'))
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)

  useEffect(() => {
    if (!auth && screen !== 'login' && screen !== 'register') setScreen('login')
  }, [auth, screen])

  const handleAuthSuccess = (newAuth: AuthState) => {
    setAuth(newAuth)
    setScreen('upload')
  }

  const handleLogout = () => {
    clearAuth()
    setAuth(null)
    setAnalysisResult(null)
    setScreen('login')
  }

  const handleResult = (r: AnalysisResult) => {
    setAnalysisResult(r)
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
          ◈ VOCAL AI
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
        {screen === 'upload' && auth && <UploadScreen token={auth.token} onResult={handleResult} />}
        {screen === 'result' && auth && analysisResult && (
          <ResultScreen result={analysisResult} onBack={() => setScreen('upload')} onDashboard={() => setScreen('dashboard')} />
        )}
        {screen === 'dashboard' && auth && (
          <DashboardScreen token={auth.token} latestResult={analysisResult} onBack={() => setScreen(analysisResult ? 'result' : 'upload')} />
        )}
      </main>
    </div>
  )
}

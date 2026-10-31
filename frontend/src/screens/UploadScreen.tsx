import { useState, useEffect } from 'react'
import { API_BASE, type AnalysisResult } from '../types'

export function UploadScreen({ onResult }: { onResult: (r: AnalysisResult) => void }) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [songTitle, setSongTitle] = useState('')
  const [artistName, setArtistName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [pollCount, setPollCount] = useState(0)

  useEffect(() => {
    if (!loading) return
    const style = document.createElement('style')
    style.id = 'va-spin'
    style.textContent = '@keyframes va-spin { to { transform: rotate(360deg); } }'
    document.head.appendChild(style)
    return () => { document.getElementById('va-spin')?.remove() }
  }, [loading])

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
    setLoading(true); setError(''); setPollCount(0)
    try {
      const form = new FormData()
      form.append('audio_file', file)
      const url = `${API_BASE}/api/v1/analysis/upload?song_title=${encodeURIComponent(songTitle)}&artist_name=${encodeURIComponent(artistName)}`
      const res = await fetch(url, { method: 'POST', credentials: 'include', body: form })
      if (!res.ok) {
        // 429（分析中・回数上限）などはサーバーのメッセージを出す。detail が文字列でない（422 等）・JSON でないときは番号だけ出す
        const data = await res.json().catch(() => null)
        throw new Error(typeof data?.detail === 'string' ? data.detail : `サーバーエラー: ${res.status}`)
      }
      const { task_id } = await res.json()

      let analysisId: number | null = null
      const POLL_MAX = 120
      for (let i = 0; i < POLL_MAX; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000))
        setPollCount(i + 1)
        const statusRes = await fetch(`${API_BASE}/api/v1/analysis/status/${task_id}`, { credentials: 'include' })
        if (!statusRes.ok) throw new Error(`ステータス確認エラー: ${statusRes.status}`)
        const statusData = await statusRes.json()
        if (statusData.status === 'SUCCESS') {
          analysisId = statusData.analysis_id
          break
        } else if (statusData.status === 'FAILURE') {
          throw new Error('分析中にエラーが発生しました')
        }
      }

      if (analysisId === null) throw new Error('分析がタイムアウトしました')

      const resultRes = await fetch(`${API_BASE}/api/v1/analysis/${analysisId}`, { credentials: 'include' })
      if (!resultRes.ok) throw new Error(`結果取得エラー: ${resultRes.status}`)
      const data: AnalysisResult = await resultRes.json()
      onResult({ ...data, song_title: songTitle, artist_name: artistName })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '分析に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    const dots = '.'.repeat((pollCount % 3) + 1)
    return (
      <div style={{ maxWidth: '560px', margin: '0 auto', padding: '80px 20px', textAlign: 'center' }}>
        <p style={{ color: '#c084fc', fontSize: '12px', letterSpacing: '0.2em', marginBottom: '48px' }}>VOCAL ANALYZER</p>

        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '40px' }}>
          <svg width="72" height="72" viewBox="0 0 72 72" style={{ animation: 'va-spin 1.2s linear infinite' }}>
            <defs>
              <linearGradient id="spinGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#c084fc" />
                <stop offset="100%" stopColor="#818cf8" />
              </linearGradient>
            </defs>
            <circle cx="36" cy="36" r="28" fill="none" stroke="#1e1e2e" strokeWidth="6" />
            <circle
              cx="36" cy="36" r="28" fill="none"
              stroke="url(#spinGrad)" strokeWidth="6" strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 28 * 0.75} ${2 * Math.PI * 28 * 0.25}`}
            />
          </svg>
        </div>

        <h2 style={{ color: 'white', fontSize: '26px', fontWeight: '800', marginBottom: '12px' }}>
          分析中{dots}
        </h2>
        <p style={{ color: '#555', fontSize: '13px', marginBottom: '32px' }}>
          AIが歌声を解析しています（最大10分かかる場合があります）
        </p>

        {(songTitle || artistName) && (
          <div style={{
            display: 'inline-block', background: 'rgba(255,255,255,0.02)',
            border: '1px solid #1e1e2e', borderRadius: '12px', padding: '14px 24px', marginBottom: '32px',
          }}>
            {songTitle && <p style={{ color: '#aaa', fontSize: '14px', marginBottom: artistName ? '2px' : 0 }}>{songTitle}</p>}
            {artistName && <p style={{ color: '#555', fontSize: '12px' }}>{artistName}</p>}
          </div>
        )}

        {pollCount > 0 && (
          <p style={{ color: '#333', fontSize: '12px' }}>{pollCount * 5}秒経過 / 最大600秒</p>
        )}
      </div>
    )
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
      <p style={{ color: '#555', fontSize: '12px', textAlign: 'center', marginTop: '12px' }}>
        録音ファイルは分析後すぐに削除され、保存されません。
      </p>
    </div>
  )
}

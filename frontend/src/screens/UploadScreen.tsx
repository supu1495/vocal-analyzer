import { useRef, useState } from 'react'
import { type AnalysisResult } from '../types'
import { apiFetch, errorMessage } from '../api'

// 送る前の確認（#13）。最終判断は backend（api/analysis.py）がするので、値はそちらとそろえる
// 形式は MIME か拡張子のどちらかが合えば通す（MIME はブラウザや OS で名前が違うため）。中身は backend が magic bytes で確かめる
const ALLOWED_CONTENT_TYPES = ['audio/wav', 'audio/x-wav', 'audio/mpeg', 'audio/mp4', 'audio/x-m4a', 'audio/m4a']
const ALLOWED_EXTENSIONS = ['.wav', '.mp3', '.m4a']
const MAX_FILE_MB = 90             // _MAX_FILE_SIZE。Cloudflare の1回100MBまでに余裕を取った値
const MAX_DURATION_SECONDS = 10 * 60  // _MAX_DURATION_SECONDS
const MAX_TEXT_LENGTH = 70         // _MAX_TEXT_LENGTH（楽曲名・アーティスト名）

// 結果の確認は、分析中の印の期限（upload_limits.py の34分 = 時間制限17分 ＋ 前の1件の17分）まで続ける
const POLL_INTERVAL_SECONDS = 5
const POLL_MAX_MINUTES = 34
const POLL_MAX = (POLL_MAX_MINUTES * 60) / POLL_INTERVAL_SECONDS  // 408回

// 長さの読み取りが、これだけ待っても終わらなければ「わからない」とする
const DURATION_READ_TIMEOUT_MS = 5000

function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot === -1 ? '' : name.slice(dot).toLowerCase()
}

// ブラウザで音声を読み、長さ（秒）を返す。読めない・長さが出ない（Infinity 等）・時間切れなら null
// null のときは画面では止めず、backend の ffprobe に任せる
function readDurationSeconds(file: File): Promise<number | null> {
  return new Promise(resolve => {
    const url = URL.createObjectURL(file)
    const audio = new Audio()
    let settled = false
    const finish = (seconds: number | null) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      URL.revokeObjectURL(url)
      resolve(seconds)
    }
    const timer = setTimeout(() => finish(null), DURATION_READ_TIMEOUT_MS)
    audio.preload = 'metadata'
    audio.onloadedmetadata = () => finish(Number.isFinite(audio.duration) ? audio.duration : null)
    audio.onerror = () => finish(null)
    audio.src = url
  })
}

// 送る前に断る理由。問題がなければ null
async function rejectReason(f: File): Promise<string | null> {
  if (!ALLOWED_CONTENT_TYPES.includes(f.type) && !ALLOWED_EXTENSIONS.includes(fileExtension(f.name))) {
    return 'WAV / MP3 / M4A のみ対応しています。'
  }
  if (f.size > MAX_FILE_MB * 1024 * 1024) {
    return `ファイルが大きすぎます（上限 ${MAX_FILE_MB}MB）。長い曲は m4a や mp3 で送ってください。`
  }
  const duration = await readDurationSeconds(f)
  if (duration !== null && duration > MAX_DURATION_SECONDS) {
    const limitMinutes = MAX_DURATION_SECONDS / 60
    return `録音が長すぎます（上限 ${limitMinutes}分）。${limitMinutes}分以内に切って送ってください。`
  }
  return null
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  return minutes > 0 ? `${minutes}分${seconds % 60}秒` : `${seconds}秒`
}

export function UploadScreen({ onResult }: { onResult: (r: AnalysisResult) => void }) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [checking, setChecking] = useState(false)
  const [songTitle, setSongTitle] = useState('')
  const [artistName, setArtistName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [pollCount, setPollCount] = useState(0)
  // 何回目に選んだファイルか。長さの読み取り中に別のファイルを選んだとき、古い結果で上書きしないため
  const latestPickRef = useRef(0)
  // 長さの確認中は、前に選んだファイルが残っていても送らせない
  const canSubmit = file !== null && !loading && !checking

  const handleFile = async (f: File) => {
    const pick = ++latestPickRef.current
    setChecking(true); setError('')
    const reason = await rejectReason(f)
    if (pick !== latestPickRef.current) return
    setChecking(false)
    if (reason) {
      // 断ったファイルを選んだままに見えないよう、選択を外す
      setFile(null); setError(reason)
      return
    }
    setFile(f)
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
      const path = `/api/v1/analysis/upload?song_title=${encodeURIComponent(songTitle)}&artist_name=${encodeURIComponent(artistName)}`
      const res = await apiFetch(path, { method: 'POST', body: form })
      // 400（形式・サイズ・長さ・文字数）・429（分析中・回数上限）などはサーバーのメッセージを出す
      if (!res.ok) throw new Error(await errorMessage(res))
      const { task_id } = await res.json()
      // task_id が無いまま進むと /status/undefined を問い合わせ続ける（9/30 の 404 の件）
      if (typeof task_id !== 'string' || task_id === '') throw new Error('分析を受け付けられませんでした。もう一度お試しください。')

      let analysisId: number | null = null
      for (let i = 0; i < POLL_MAX; i++) {
        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_SECONDS * 1000))
        setPollCount(i + 1)
        const statusRes = await apiFetch(`/api/v1/analysis/status/${task_id}`)
        if (!statusRes.ok) throw new Error(await errorMessage(statusRes))
        const statusData = await statusRes.json()
        if (statusData.status === 'SUCCESS') {
          analysisId = statusData.analysis_id
          break
        } else if (statusData.status === 'FAILURE') {
          // 失敗の理由（声が検出できない・形式不正・時間切れ など）ごとのサーバーの文言を出す。古い backend で detail が無いときは今までの文言
          throw new Error(typeof statusData.detail === 'string' ? statusData.detail : '分析中にエラーが発生しました')
        }
      }

      // 画面が確認をやめても、worker の分析は続き、終われば結果は保存される（統計に出る）
      if (analysisId === null) {
        throw new Error(`${POLL_MAX_MINUTES}分待っても分析が終わりませんでした。分析が終われば統計に反映されます。`)
      }

      const resultRes = await apiFetch(`/api/v1/analysis/${analysisId}`)
      if (!resultRes.ok) throw new Error(await errorMessage(resultRes))
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
      <div className="centered-block" style={{ maxWidth: 'var(--form-width)', textAlign: 'center' }}>
        <p style={{ color: '#c084fc', fontSize: 'var(--caption-size)', letterSpacing: '0.2em', margin: '0 0 var(--block-gap)' }}>VOCAL ANALYZER</p>

        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--block-gap)' }}>
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

        <h2 style={{ color: 'white', fontSize: 'var(--heading-size)', fontWeight: '800', margin: '0 0 0.3em' }}>
          分析中{dots}
        </h2>
        <p style={{ color: '#555', fontSize: 'var(--body-size)', margin: '0 0 0.5em' }}>
          AIが歌声を解析しています。録音の長さの1.3倍ほどかかります（10分の曲で約13分）
        </p>
        {/* worker は1件ずつ処理する（--concurrency=1、#32）ため */}
        <p style={{ color: '#555', fontSize: 'var(--caption-size)', margin: '0 0 var(--block-gap)' }}>
          ほかの人の分析が先にあると、順番待ちで長くなることがあります
        </p>

        {(songTitle || artistName) && (
          <div style={{
            display: 'inline-block', background: 'rgba(255,255,255,0.02)',
            border: '1px solid #1e1e2e', borderRadius: '12px', padding: '0.8em 1.5em', marginBottom: 'var(--block-gap)',
          }}>
            {songTitle && <p style={{ color: '#aaa', fontSize: 'var(--body-size)', margin: artistName ? '0 0 2px' : 0 }}>{songTitle}</p>}
            {artistName && <p style={{ color: '#555', fontSize: 'var(--caption-size)', margin: 0 }}>{artistName}</p>}
          </div>
        )}

        {pollCount > 0 && (
          <p style={{ color: '#333', fontSize: 'var(--caption-size)', margin: 0 }}>{formatElapsed(pollCount * POLL_INTERVAL_SECONDS)}経過 / 最大{POLL_MAX_MINUTES}分</p>
        )}
      </div>
    )
  }

  return (
    <div className="centered-block" style={{ maxWidth: 'var(--form-width)' }}>
      <div style={{ marginBottom: 'var(--block-gap)' }}>
        <p style={{ color: '#c084fc', fontSize: 'var(--caption-size)', letterSpacing: '0.2em', margin: '0 0 0.6em' }}>VOCAL ANALYZER</p>
        <h1 style={{ fontSize: 'var(--heading-size)', fontWeight: '800', color: 'white', lineHeight: 1.2, margin: '0 0 0.3em' }}>
          あなたの歌声を<br />分析しましょう
        </h1>
        <p style={{ color: '#666', fontSize: 'var(--body-size)', margin: 0 }}>カラオケ録音をアップロードして、AIが歌唱力を詳細分析します</p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('fileInput')?.click()}
        style={{
          border: `2px dashed ${dragging ? '#c084fc' : file ? '#34d399' : '#2a2a3e'}`,
          // 高さは画面の縦に合わせて固定し、中身（アイコンと文字）は枠の縦の真ん中に置く
          height: 'var(--dropzone-height)', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
          borderRadius: '16px', padding: '0 24px', textAlign: 'center', cursor: 'pointer',
          background: dragging ? 'rgba(192,132,252,0.05)' : 'rgba(255,255,255,0.02)',
          transition: 'all 0.2s ease', marginBottom: 'var(--field-gap)',
        }}
      >
        <input id="fileInput" type="file" accept=".wav,.mp3,.m4a,audio/*" style={{ display: 'none' }}
          onChange={(e) => {
            const picked = e.target.files?.[0]
            // 選択を空に戻す。同じファイルを選び直すとブラウザは change を出さないため、断られたあとに選び直せなくなる
            e.target.value = ''
            if (picked) handleFile(picked)
          }} />
        <div style={{ fontSize: 'var(--heading-size)', marginBottom: '0.3em' }}>{file ? '🎵' : '🎤'}</div>
        {file ? (
          <>
            <p style={{ color: '#34d399', fontWeight: '600', fontSize: 'var(--body-size)', margin: '0 0 0.25em' }}>{file.name}</p>
            <p style={{ color: '#555', fontSize: 'var(--label-size)', margin: 0 }}>{(file.size / 1024 / 1024).toFixed(1)} MB</p>
          </>
        ) : (
          <>
            <p style={{ color: '#aaa', fontSize: 'var(--body-size)', margin: '0 0 0.25em' }}>音声ファイルをドロップ</p>
            <p style={{ color: '#555', fontSize: 'var(--label-size)', margin: 0 }}>または クリックして選択（WAV / MP3 / M4A・{MAX_DURATION_SECONDS / 60}分・{MAX_FILE_MB}MB まで）</p>
          </>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--field-gap)', marginBottom: 'var(--field-gap)' }}>
        {[
          { label: '楽曲名', value: songTitle, setter: setSongTitle, placeholder: 'Feeling' },
          { label: 'アーティスト', value: artistName, setter: setArtistName, placeholder: 'Mrs. GREEN APPLE' },
        ].map(({ label, value, setter, placeholder }) => (
          <div key={label}>
            <label style={{ color: '#666', fontSize: 'var(--label-size)', letterSpacing: '0.1em', display: 'block', marginBottom: '0.4em' }}>
              {label}（任意）
            </label>
            {/* backend も70文字を超えたら 400 にする。JS は絵文字を2文字と数えるので、backend より先に止まることはあっても逆はない */}
            <input value={value} onChange={(e) => setter(e.target.value)} placeholder={placeholder} maxLength={MAX_TEXT_LENGTH}
              style={{ width: '100%', height: 'var(--input-height)', padding: '0 0.9em', background: '#0d0d1a', border: '1px solid #2a2a3e',
                borderRadius: '10px', color: 'white', fontSize: 'var(--body-size)', outline: 'none' }} />
          </div>
        ))}
      </div>

      {error && <p style={{ color: '#f87171', fontSize: 'var(--label-size)', margin: '0 0 var(--field-gap)', textAlign: 'center' }}>{error}</p>}

      <button onClick={handleSubmit} disabled={!canSubmit} style={{
        width: '100%', height: 'var(--button-height)',
        background: canSubmit ? 'linear-gradient(135deg, #c084fc, #818cf8)' : '#1e1e2e',
        border: 'none', borderRadius: '12px',
        color: canSubmit ? 'white' : '#444', fontSize: 'var(--body-size)', fontWeight: '700',
        cursor: canSubmit ? 'pointer' : 'not-allowed', transition: 'all 0.2s ease', letterSpacing: '0.05em',
      }}>
        {loading ? '分析中...' : checking ? 'ファイルを確かめています...' : '分析を開始する →'}
      </button>
      {/* ボタンのすぐ下に置く */}
      <p style={{ color: '#555', fontSize: 'var(--caption-size)', textAlign: 'center', margin: '1em 0 0' }}>
        録音ファイルは分析後すぐに削除され、保存されません。
      </p>
    </div>
  )
}

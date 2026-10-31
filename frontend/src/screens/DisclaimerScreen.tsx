import { useState } from 'react'
import { API_BASE } from '../types'

const NOTICES = [
  '本システムの分析結果はあくまで参考情報です。医学的診断や専門的な判断には使用できません。',
  '声や歌唱に関する詳細な相談は、専門家（ボイストレーナー、医師など）にご相談ください。',
  '本システムの利用により生じたいかなる損害についても、運営者は一切の責任を負いかねます。',
]

// 免責事項に同意するまで、アップロードなどの画面の代わりに表示する
export function DisclaimerScreen({ onAccepted }: { onAccepted: () => void }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleAccept = async () => {
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/disclaimer`, { method: 'POST', credentials: 'include' })
      if (!res.ok) throw new Error(`サーバーエラー: ${res.status}`)
      onAccepted()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'エラーが発生しました。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: '560px', margin: '0 auto', padding: '80px 20px 40px' }}>
      <h1 style={{ fontSize: '26px', fontWeight: '600', letterSpacing: '0.08em', color: 'white', marginBottom: '32px', textAlign: 'center' }}>免責事項</h1>

      <ul style={{ background: '#0d0d1a', border: '1px solid #2a2a3e', borderRadius: '12px', padding: '20px 20px 20px 40px', margin: '0 0 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {NOTICES.map(notice => (
          <li key={notice} style={{ color: '#ccc', fontSize: '14px', lineHeight: 1.7 }}>{notice}</li>
        ))}
      </ul>

      {error && <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '16px', textAlign: 'center' }}>{error}</p>}

      <button
        onClick={handleAccept} disabled={loading}
        style={{
          width: '100%', padding: '14px',
          background: loading ? '#1e1e2e' : 'linear-gradient(135deg, #c084fc, #818cf8)',
          border: 'none', borderRadius: '12px',
          color: loading ? '#444' : 'white', fontSize: '15px', fontWeight: '700',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? '処理中...' : '同意して始める →'}
      </button>
    </div>
  )
}

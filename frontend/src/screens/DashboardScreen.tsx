import { useState, useEffect } from 'react'
import { API_BASE, calcTotalScore, type AnalysisResult, type Statistics } from '../types'
import { LineChart } from '../components/LineChart'

export function DashboardScreen({ latestResult, onBack }: {
  latestResult: AnalysisResult | null; onBack: () => void
}) {
  const [stats, setStats] = useState<Statistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/analysis/user/statistics`, { credentials: 'include' })
      .then(res => { if (!res.ok) throw new Error(`サーバーエラー: ${res.status}`); return res.json() })
      .then((data: Statistics) => setStats(data))
      .catch(e => setError(e instanceof Error ? e.message : '統計の取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [])

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
              { label: '総合', value: calcTotalScore(latestResult.result.pitch_accuracy, latestResult.result.rhythm_score), color: '#60a5fa' },
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
          { label: '成長率', value: stats ? (stats.growth_rate >= 0 ? `+${stats.growth_rate}` : `${stats.growth_rate}`) : '-', unit: '%' },
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

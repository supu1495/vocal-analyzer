import { type AnalysisResult, calcTotalScore } from '../types'
import { ScoreRing } from '../components/ScoreRing'
import { TechniqueBar } from '../components/TechniqueBar'

export function ResultScreen({ result, onBack, onDashboard }: {
  result: AnalysisResult; onBack: () => void; onDashboard: () => void
}) {
  const scores = result.result
  const techniques = scores.techniques
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
        <ScoreRing score={scores.pitch_accuracy} label="ピッチ精度" color="#c084fc" />
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: '#555', fontSize: '24px', marginBottom: '8px' }}>✦</div>
          <p style={{ color: '#888', fontSize: '11px', letterSpacing: '0.1em' }}>総合評価</p>
          <p style={{ color: 'white', fontSize: '28px', fontWeight: '800' }}>
            {calcTotalScore(scores.pitch_accuracy, scores.rhythm_score)}
          </p>
        </div>
        <ScoreRing score={scores.rhythm_score} label="リズム感" color="#34d399" />
      </div>

      <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #1e1e2e', borderRadius: '16px', padding: '24px', marginBottom: '20px' }}>
        <p style={{ color: '#888', fontSize: '11px', letterSpacing: '0.15em', marginBottom: '20px' }}>TECHNIQUES</p>
        <TechniqueBar label="ビブラート" value={techniques.vibrato.count} max={20} color="#c084fc" />
        <TechniqueBar label="こぶし" value={techniques.kobushi.count} max={20} color="#f472b6" />
        <TechniqueBar label="フォール" value={techniques.fall.count} max={20} color="#60a5fa" />
        <TechniqueBar label="しゃくり" value={techniques.shakuri.count} max={20} color="#fb923c" />
        <TechniqueBar label="ロングトーン" value={techniques.long_tone.count} max={20} color="#34d399" />
      </div>

      {scores.feedback && (
        <div style={{ background: 'rgba(192,132,252,0.05)', border: '1px solid rgba(192,132,252,0.15)', borderRadius: '16px', padding: '20px', marginBottom: '20px' }}>
          <p style={{ color: '#c084fc', fontSize: '11px', letterSpacing: '0.15em', marginBottom: '10px' }}>FEEDBACK</p>
          <p style={{ color: '#ccc', fontSize: '14px', lineHeight: '1.6' }}>{scores.feedback}</p>
        </div>
      )}

      <button onClick={onDashboard} style={{ width: '100%', padding: '14px', background: 'rgba(255,255,255,0.04)', border: '1px solid #2a2a3e', borderRadius: '12px', color: '#aaa', fontSize: '14px', cursor: 'pointer', transition: 'all 0.2s' }}>
        統計ダッシュボードを見る →
      </button>
    </div>
  )
}

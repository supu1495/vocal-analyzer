export function ScoreRing({ score, label, color }: { score: number; label: string; color: string }) {
  const r = 36
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  return (
    // 横に並んだ箱が狭いときは、88px より小さく縮む（flex の中で縮めるには minWidth: 0 が要る）
    <div style={{ flex: '0 1 88px', minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
      <svg viewBox="0 0 88 88" style={{ display: 'block', width: '100%', maxWidth: '88px', height: 'auto' }}>
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

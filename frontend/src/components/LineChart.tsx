import type { Statistics } from '../types'

export function LineChart({ data }: { data: Statistics['history'] }) {
  const w = 340; const h = 100; const pad = 20
  const maxVal = 100
  const xs = data.map((_, i) => pad + (data.length > 1 ? i / (data.length - 1) : 0.5) * (w - pad * 2))
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

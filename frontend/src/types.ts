export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type Screen = 'login' | 'register' | 'upload' | 'result' | 'dashboard'

export interface AuthState {
  userId: number
  email: string
  disclaimerAccepted: boolean
}

// GET /api/v1/analysis/{analysis_id} のレスポンス（backend/api/analysis.py の get_analysis）に合わせる
// 中身を作っているのは backend/audio/analyzer.py（vocal_range・score_matrix）と backend/audio/techniques.py（techniques）
export interface AnalysisResult {
  analysis_id: number
  // DB の列は NOT NULL（未入力は空文字）
  song_title: string
  artist_name: string
  result: {
    pitch_accuracy: number
    rhythm_score: number
    techniques: {
      vibrato: { count: number; avg_frequency: number; avg_depth: number }
      kobushi: { count: number; timestamps: number[] }
      fall: { count: number; avg_depth: number }
      shakuri: { count: number; avg_height: number }
      long_tone: { count: number; avg_tone_seconds: number; avg_stability: number }
    }
    // 声が見つからないと音名は null になる。DB の列も null を許すので、全体が null のこともある
    vocal_range: { lowest: string | null; highest: string | null; range_semitones: number } | null
    // DB の列が null を許すため、すべて null のことがある（画面に出すのは #16）
    score_matrix: {
      total_score: number | null
      faithfulness_score: number | null
      technique_score: number | null
      naturalness_penalty: number | null
    }
    feedback: string | null
  }
}

// 技法バーの最大値。採点の「満点ライン」（この回数で技法の点が満点になる）と同じ値にする
// backend/audio/analyzer.py の _calculate_score_matrix と必ずそろえる。満点ラインを超えた回数はバーいっぱいで止まる
// 範囲（少ない／適正／多すぎ）の表示は #16
export const TECHNIQUE_FULL_MARKS = {
  vibrato: 20,
  shakuri: 20,
  kobushi: 5,
  fall: 5,
  long_tone: 3,
} as const

export interface Statistics {
  history: { date: string; pitch: number; rhythm: number }[]
  total_count: number
  best_pitch: number
  growth_rate: number
}

export function calcTotalScore(pitchAccuracy: number, rhythmScore: number): number {
  return Math.round((pitchAccuracy + rhythmScore) / 2)
}

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type Screen = 'login' | 'register' | 'upload' | 'result' | 'dashboard'

export interface AuthState {
  userId: number
  email: string
  disclaimerAccepted: boolean
}

export interface AnalysisResult {
  analysis_id: number
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

export interface Statistics {
  history: { date: string; pitch: number; rhythm: number }[]
  total_count: number
  best_pitch: number
  growth_rate: number
}

export function calcTotalScore(pitchAccuracy: number, rhythmScore: number): number {
  return Math.round((pitchAccuracy + rhythmScore) / 2)
}

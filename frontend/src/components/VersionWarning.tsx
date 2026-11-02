import { useState, useEffect } from 'react'
import { API_BASE } from '../types'

const FRONTEND_COMMIT = __APP_COMMIT__
const UNKNOWN_COMMIT = 'unknown'

// 画面に出すときだけ短くする（比べるときは40文字のまま）
const shortCommit = (commit: string) => commit.slice(0, 7)

// フロント（Cloudflare が push のたびに自動でビルド）と backend（自宅 PC で手動更新）の
// ビルド元のコミットが違うときに、画面の一番上に小さな帯を出す
export function VersionWarning() {
  const [backendCommit, setBackendCommit] = useState<string | null>(null)

  useEffect(() => {
    // 開発中（npm run dev）は比べない。backend は作業中のファイルで動いており、コミットIDが当てにならないため
    if (import.meta.env.DEV) return

    fetch(`${API_BASE}/health`)
      .then(res => res.ok ? res.json() : null)
      // commit を返さない古い backend も unknown として警告の対象にする
      .then(data => { if (data) setBackendCommit(data.commit ?? UNKNOWN_COMMIT) })
      // backend に届かないときは出さない（ログインなど他の画面のエラーで気づけるため）
      .catch(() => {})
  }, [])

  if (backendCommit === null) return null

  const isMatched = backendCommit === FRONTEND_COMMIT && FRONTEND_COMMIT !== UNKNOWN_COMMIT
  if (isMatched) return null

  return (
    <div role="status" style={{ background: 'rgba(251,191,36,0.1)', borderBottom: '1px solid rgba(251,191,36,0.3)', color: '#fbbf24', fontSize: '12px', padding: '6px 24px', textAlign: 'center' }}>
      フロントと API のバージョンが違います（フロント {shortCommit(FRONTEND_COMMIT)} / API {shortCommit(backendCommit)}）。
      正しく動かない場合があります
    </div>
  )
}

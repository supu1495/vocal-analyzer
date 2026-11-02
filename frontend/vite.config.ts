import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    // ビルド元のコミットID（40文字）を JS に埋め込む。backend の /health の commit と比べてずれを警告する
    // WORKERS_CI_COMMIT_SHA は Cloudflare のビルド環境が渡す。それ以外でビルドしたときは unknown
    __APP_COMMIT__: JSON.stringify(process.env.WORKERS_CI_COMMIT_SHA ?? 'unknown'),
  },
  server: {
    // ローカル開発時に /api/* を Docker Compose の backend サービスに転送する
    // localhost:5173 経由でアクセスしたとき VITE_API_BASE_URL が未設定でも API が叩けるようにする
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})

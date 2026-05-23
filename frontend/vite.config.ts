import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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

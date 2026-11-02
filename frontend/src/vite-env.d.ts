/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// vite.config.ts の define でビルド時に埋め込むコミットID
declare const __APP_COMMIT__: string

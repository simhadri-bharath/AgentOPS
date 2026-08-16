import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Backend port is configurable: 8000 is often already taken, and a hardcoded
// target makes that failure look like a broken frontend.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.BACKEND_URL || 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
      },
    },
  }
})

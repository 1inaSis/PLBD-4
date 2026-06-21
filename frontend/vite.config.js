import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // Requêtes REST → FastAPI :8000
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      // WebSocket → FastAPI :8000
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  // npm run preview (production systemd) — même proxy que dev
  preview: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8000',  ws: true },
    },
  },
})
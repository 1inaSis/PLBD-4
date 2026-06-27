import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'

// Charge les certs HTTPS si disponibles (déploiement Pi)
// Sur la machine de dev (Windows), retourne undefined → HTTP normal
function httpsConfig() {
  try {
    return {
      key:  fs.readFileSync('/home/touaregs/PLBD-4/certs/key.pem'),
      cert: fs.readFileSync('/home/touaregs/PLBD-4/certs/cert.pem'),
    }
  } catch {
    return undefined
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8000',  ws: true },
    },
  },
  // npm run preview (production systemd) — HTTPS si certs présents
  preview: {
    https: httpsConfig(),
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8000',  ws: true },
    },
  },
})

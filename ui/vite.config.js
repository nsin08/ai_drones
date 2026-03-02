import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:5000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
      '/ws': { target: proxyTarget, ws: true, changeOrigin: true },
      '/socket.io': { target: proxyTarget, ws: true, changeOrigin: true },
    },
  },
})

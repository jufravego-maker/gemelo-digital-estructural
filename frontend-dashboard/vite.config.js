import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En desarrollo, /api y /ws se redirigen al backend FastAPI local.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Permite abrir el servidor de desarrollo desde GitHub Codespaces
    allowedHosts: ['.app.github.dev'],
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // Librerías pesadas en chunks separados (mejor caché del navegador)
        manualChunks: {
          maplibre: ['maplibre-gl'],
          three: ['three'],
          echarts: ['echarts'],
          react: ['react', 'react-dom'],
        },
      },
    },
  },
})

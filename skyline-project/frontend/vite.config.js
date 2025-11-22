import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // This proxy forwards any request starting with /api to the backend
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // Backend address inside the container
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''), // Removes '/api' before sending to backend
      },
    },
  },
})
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/artists':   'http://localhost:8000',
      '/dashboard': 'http://localhost:8000',
      '/feedback':  'http://localhost:8000',
      '/explain':   'http://localhost:8000',
      '/discover':  'http://localhost:8000',
    },
  },
})

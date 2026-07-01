import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/docs': 'http://localhost:8000',
      '/suggest': 'http://localhost:8000',
      '/orgs': 'http://localhost:8000',
      '/widget': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
    },
  },
})

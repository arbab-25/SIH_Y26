import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    // Inject API base URL at build time from VITE_API_BASE_URL env var
    // Falls back to empty string so axios baseURL handles it
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})

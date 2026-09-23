import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // PWA per Phase 4: installable + offline shell. The offline scan QUEUE
    // itself lives in IndexedDB (src/utils/offlineQueue.ts) and syncs on
    // reconnect; the service worker only guarantees the app shell loads.
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['logo.jpeg', 'favicon.svg'],
      manifest: {
        name: 'CODE MAZE — Legal Metrology Compliance',
        short_name: 'CODE MAZE',
        description:
          'Scan packaged commodity labels and get deterministic, rule-cited compliance verdicts under the Legal Metrology (Packaged Commodities) Rules, 2011.',
        theme_color: '#12355B',
        background_color: '#F8FAFC',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: '/pwa-icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/pwa-icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,jpeg,woff2}'],
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            // Rule Book content is statutory reference data: cache it so the
            // Rule Book page works in the field with patchy connectivity.
            urlPattern: /\/api\/v1\/rules.*$/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'rules-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 86400 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
  define: {
    // Inject API base URL at build time from VITE_API_BASE_URL env var
    // Falls back to empty string so axios baseURL handles it
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('recharts')) return 'charts'
          if (id.includes('axios') || id.includes('idb')) return 'network'
          if (id.includes('@tanstack')) return 'query'
          if (id.includes('i18next')) return 'i18n'
          if (id.includes('react')) return 'react'
          return undefined
        },
      },
    },
  },
})

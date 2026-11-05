import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/@pdf-lib/standard-fonts/')) return 'pdf-fonts'
          if (id.includes('/node_modules/pdf-lib/')) return 'pdf-generation'
          if (id.includes('/node_modules/@supabase/')) return 'supabase-client'
        },
      },
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: [],
      manifest: {
        name: 'Partes Diarios',
        short_name: 'Partes',
        description: 'Carga y seguimiento de partes diarios de trabajo agrícola.',
        lang: 'es-AR',
        start_url: './',
        scope: './',
        display: 'standalone',
        background_color: '#f3f0e8',
        theme_color: '#17372a',
        icons: [],
      },
      workbox: {
        navigateFallback: 'index.html',
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
      },
    }),
  ],
})


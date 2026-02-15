import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const isMock = process.env.VITE_MOCK === '1'

export default defineConfig(async () => {
  const plugins = [react()]

  if (isMock) {
    const { default: mockServerPlugin } = await import('./src/mock-server')
    plugins.push(mockServerPlugin())
  }

  return {
    plugins,
    server: {
      port: 5173,
      // Only proxy to real backend when NOT in mock mode
      ...(!isMock && {
        proxy: {
          '/api': {
            target: 'http://localhost:8080',
            ws: true,
          },
          '/health': 'http://localhost:8080',
          '/static': 'http://localhost:8080',
        },
      }),
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  }
})

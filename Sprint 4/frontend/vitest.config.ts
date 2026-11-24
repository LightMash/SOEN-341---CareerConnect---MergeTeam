import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Component tests (npm test). Kept separate from vite.config.ts so the dev
// server and production build are unchanged.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})

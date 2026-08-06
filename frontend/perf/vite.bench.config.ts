/**
 * Dev-server config for the live-table benchmark only.
 *
 * Deliberately isolated from the main dev server on TWO axes:
 *   - its own port, so the user's running server is untouched;
 *   - its own `cacheDir` OUTSIDE node_modules, because a worktree symlinks
 *     `frontend/node_modules` to the main checkout and two Vite instances
 *     sharing `node_modules/.vite` clobber each other's optimize cache —
 *     mismatched `?v=` hashes end up loading two copies of React
 *     ("Cannot read properties of null (reading 'useContext')").
 */

import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  root: path.resolve(__dirname, '..'),
  cacheDir: path.resolve(__dirname, '../../.vite-bench-cache'),
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '../src'),
    },
  },
  server: {
    port: 5199,
    strictPort: true,
  },
})

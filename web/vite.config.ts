/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';

/** Emits precache-manifest.json (every built file) for the hand-written service worker in public/sw.js. */
function precacheManifest(): Plugin {
  return {
    name: 'll-precache-manifest',
    apply: 'build',
    generateBundle(_opts, bundle) {
      const files = Object.keys(bundle).filter((f) => !f.endsWith('.map') && f !== 'index.html');
      this.emitFile({ type: 'asset', fileName: 'precache-manifest.json', source: JSON.stringify(files) });
    },
  };
}

export default defineConfig({
  plugins: [react(), precacheManifest()],
  server: { port: 5173, strictPort: true, host: true },
  build: { chunkSizeWarningLimit: 1600 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});

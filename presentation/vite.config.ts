import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// The deck talks to the API through this proxy, so the API's CORS list never matters.
// API_TARGET overrides the default (e.g. API_TARGET=http://127.0.0.1:8101 npm run dev).
const API_TARGET = process.env.API_TARGET ?? 'http://localhost:8000';
const proxy = { '/api': { target: API_TARGET, changeOrigin: true } };

export default defineConfig({
  server: { port: 4400, strictPort: true, proxy, fs: { allow: [resolve(__dirname, '..')] } },
  preview: { port: 4400, strictPort: true, proxy },
  build: {
    target: 'es2022',
    rollupOptions: { input: { main: resolve(__dirname, 'index.html'), notes: resolve(__dirname, 'notes.html') } },
  },
});

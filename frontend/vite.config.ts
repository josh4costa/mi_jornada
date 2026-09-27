import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [react(), {
    name: 'versioned-service-worker',
    apply: 'build',
    closeBundle() {
      const assets = readdirSync(resolve('dist/assets')).map(name => `/assets/${name}`);
      const hash = createHash('sha256');
      const source = readFileSync(resolve('public/sw.js'), 'utf8');
      hash.update(source);
      for (const asset of ['/index.html', ...assets]) hash.update(readFileSync(resolve(`dist${asset}`)));
      const precache = ['/', '/index.html', '/manifest.json', '/icon.svg', ...assets];
      writeFileSync(resolve('dist/sw.js'), source.replace('__BUILD_VERSION__', hash.digest('hex').slice(0, 16)).replace(/\/\* __PRECACHE__ \*\/ \[[^;]+\]/, JSON.stringify(precache)));
    },
  }],
  build: {
    rollupOptions: { output: { manualChunks: { maps: ['leaflet'], vendor: ['react', 'react-dom', 'react-router-dom'] } } },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});

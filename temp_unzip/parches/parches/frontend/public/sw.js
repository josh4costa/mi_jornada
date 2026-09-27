/**
 * public/sw.js  —  CORREGIDO
 *
 * PROBLEMA CRÍTICO DE DESPLIEGUE: la versión anterior servía '/' e '/index.html'
 * desde caché primero y nunca limpiaba cachés viejas. Tras cada `docker compose up
 * --build`, los técnicos seguían recibiendo el index.html viejo, que apunta a bundles
 * con hash que ya no existen -> pantalla en blanco hasta borrar datos del navegador.
 *
 * Estrategia corregida:
 *  - Navegación (HTML): red primero, caché como respaldo offline.
 *  - Estáticos con hash (/assets/*): caché primero (son inmutables).
 *  - API: nunca se toca.
 *  - activate: borra cachés de versiones anteriores + clients.claim().
 *
 * Sube CACHE_VERSION en cada despliegue (o inyéctalo en el build).
 */
const CACHE_VERSION = 'v2';
const CACHE_NAME = `mi-jornada-${CACHE_VERSION}`;
const OFFLINE_URLS = ['/', '/index.html', '/manifest.json', '/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(OFFLINE_URLS)).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  // 1) Navegación: red primero para recibir siempre el index.html nuevo.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('/index.html', copy));
          return response;
        })
        .catch(() => caches.match('/index.html').then((r) => r || caches.match('/'))),
    );
    return;
  }

  // 2) Estáticos: caché primero (los assets de Vite llevan hash en el nombre).
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request)
        .then((response) => {
          if (response.ok && response.type === 'basic') {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached);
    }),
  );
});

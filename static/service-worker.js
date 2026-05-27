const CACHE_NAME = 'auto-fill-cache-v2';
const urlsToCache = [
  '/static/style.css',
  '/static/script.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600&display=swap'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  // Only cache GET requests for static assets
  if (event.request.method !== 'GET' || event.request.mode === 'navigate') {
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});

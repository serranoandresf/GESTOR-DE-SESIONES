const V = "gestor-movil-v1";
const ARCHIVOS = ["./", "index.html", "manifest.webmanifest", "icono-192.png", "icono-512.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(V).then(c => c.addAll(ARCHIVOS))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== V).map(x => caches.delete(x))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(V).then(ca => ca.put(e.request, c)); return r; }).catch(() => caches.match(e.request)));
});

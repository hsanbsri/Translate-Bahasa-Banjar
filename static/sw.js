// Service worker: membuat aplikasi bisa dipasang (PWA) dan tampilannya tetap terbuka saat luring.
// Strategi "jaringan dulu": selalu ambil versi terbaru dari server; cache hanya dipakai bila
// jaringan putus. Panggilan /api/ tidak pernah di-cache (terjemahan selalu dari server).

const CACHE = "penerjemah-banjar-v1";
const KERANGKA = [
  "/",
  "/index.html",
  "/style.css",
  "/app.js",
  "/manifest.webmanifest",
  "/ikon/ikon-192.png",
  "/ikon/ikon-512.png",
  "/ikon/favicon-32.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(KERANGKA)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((kunci) => Promise.all(kunci.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) {
    return; // biarkan browser menangani langsung
  }
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok) {
          const salinan = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, salinan));
        }
        return r;
      })
      .catch(() =>
        caches.match(e.request, { ignoreSearch: true }).then((r) => r || caches.match("/"))
      )
  );
});

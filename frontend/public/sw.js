self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() => new Response("<h1 style='font-family:sans-serif'>Solid Clean Ltd</h1><p style='font-family:sans-serif'>You're offline. Please reconnect to use the dashboard.</p>", { headers: { "Content-Type": "text/html" } })));
});

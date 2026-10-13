/*
 * SERVICE WORKER (fase 7, 2026-10-12) — instalable en celular y tablet y la
 * aplicación abre aunque se caiga el internet.
 *
 * - Solo maneja peticiones del MISMO origen (la aplicación). La API vive en
 *   otro origen (el backend) y NUNCA se guarda en caché: los datos del
 *   restaurante siempre son los del servidor, nunca una copia vieja.
 * - Navegación: primero la red; sin red, la última versión de la app.
 * - /assets/ (nombres con hash, nunca cambian): primero la caché.
 * - Cambiar VERSION borra las cachés viejas al activarse.
 */
const VERSION = "js-restaurante-v1";

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(["/", "/manifest.webmanifest", "/favicon.svg"])));
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys().then((claves) => Promise.all(claves.filter((c) => c !== VERSION).map((c) => caches.delete(c)))).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const { request } = evento;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    evento.respondWith(
      fetch(request)
        .then((respuesta) => {
          const copia = respuesta.clone();
          caches.open(VERSION).then((cache) => cache.put("/", copia));
          return respuesta;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/iconos/")) {
    evento.respondWith(
      caches.match(request).then(
        (guardada) =>
          guardada ||
          fetch(request).then((respuesta) => {
            if (respuesta.ok) {
              const copia = respuesta.clone();
              caches.open(VERSION).then((cache) => cache.put(request, copia));
            }
            return respuesta;
          })
      )
    );
  }
});

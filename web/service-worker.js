/* Service Worker de MobiAire Materno (PWA).
   Estrategia que respeta las reglas de datos del proyecto:
   - CÁSCARA (HTML/CSS/JS/iconos/manifest): cache-first, para abrir sin red.
   - API (/api/*): SIEMPRE a la red (network-only), nunca se cachea, para no
     mostrar aire viejo como actual. Si no hay red, se responde un error claro
     y la interfaz muestra su estado "sin conexión" (no inventa valores).
   Preparado para una futura integración de push (Sprint 4): el 'push' y
   'notificationclick' están esbozados pero inactivos (sin credenciales FCM). */

"use strict";

const VERSION = "mobiaire-v3";
// La cáscara es el rediseño móvil (/ sirve prototipo/index.html + /app-movil.js).
// Leaflet (CDN) se cachea en tiempo de ejecución; /api/* NUNCA se cachea.
const CASCARA = [
  "/",
  "/app-movil.js",
  "/recomendaciones.json",
  "/manifest.webmanifest",
  "/img/embarazada.png",
  "/iconos/icono.svg",
  "/iconos/icono-192.png",
  "/iconos/icono-512.png",
];

// Instala: precachea la cáscara.
self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(VERSION).then((c) => c.addAll(CASCARA)).then(() => self.skipWaiting())
  );
});

// Activa: borra cachés de versiones anteriores.
self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys().then((claves) =>
      Promise.all(claves.filter((k) => k !== VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: API siempre a la red; resto cache-first con respaldo de red.
self.addEventListener("fetch", (evento) => {
  const req = evento.request;
  if (req.method !== "GET") return;                 // solo GET (el backend es de solo lectura)
  const url = new URL(req.url);

  // Datos de aire: NUNCA desde caché (no mostrar datos desactualizados como vigentes).
  if (url.pathname.startsWith("/api/")) {
    evento.respondWith(
      fetch(req).catch(() =>
        new Response(JSON.stringify({ error: "Sin conexión: no se pudo consultar el dato más reciente." }),
          { status: 503, headers: { "Content-Type": "application/json; charset=utf-8" } })
      )
    );
    return;
  }

  // Cáscara: cache-first; si no está, red y se guarda; si todo falla, index offline.
  evento.respondWith(
    caches.match(req).then((cacheada) =>
      cacheada || fetch(req).then((resp) => {
        if (resp && resp.ok && resp.type === "basic") {
          const copia = resp.clone();
          caches.open(VERSION).then((c) => c.put(req, copia));
        }
        return resp;
      }).catch(() =>
        req.mode === "navigate" ? caches.match("/index.html") : Response.error()
      )
    )
  );
});

/* ---- Base para notificaciones push (Sprint 4; inactiva sin credenciales FCM) ----
   Se deja el esqueleto para no reescribir el SW más adelante. No hace nada hasta
   que exista la integración con Firebase Cloud Messaging. */
self.addEventListener("push", (evento) => {
  if (!evento.data) return;
  let datos = {};
  try { datos = evento.data.json(); } catch (_) { datos = { title: "MobiAire", body: evento.data.text() }; }
  evento.waitUntil(
    self.registration.showNotification(datos.title || "MobiAire Materno", {
      body: datos.body || "",
      icon: "/iconos/icono-192.png",
      badge: "/iconos/icono-192.png",
    })
  );
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  evento.waitUntil(self.clients.openWindow("/"));
});

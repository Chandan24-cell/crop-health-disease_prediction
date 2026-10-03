const CACHE_VERSION = "v3";
const CACHE = `fieldnote-shell-${CACHE_VERSION}`;
const PACK = [
  "/",
  "/index.html",
  "/styleguide.html",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/css/tokens.css",
  "/css/app.css",
  "/css/leaf-explode.css",
  "/js/main.js",
  "/js/router.js",
  "/js/state.js",
  "/js/storage.js",
  "/js/api.js",
  "/js/db.js",
  "/js/i18n.js",
  "/js/quality.js",
  "/js/camera.js",
  "/js/charts.js",
  "/js/disease-data.js",
  "/js/feature-flags.js",
  "/js/batch.js",
  "/js/weather.js",
  "/js/treatment-data.js",
  "/js/notifications.js",
  "/js/report.js",
  "/js/escalation.js",
  "/js/offline-inference.js",
  "/js/components/ui.js",
  "/js/components/leaf-explode.js",
  "/js/pages/home.js",
  "/assets/leaf-sequence/webp/frame-001.webp",
  "/js/pages/scanner.js",
  "/js/pages/analysis.js",
  "/js/pages/results.js",
  "/js/pages/history.js",
  "/js/pages/library.js",
  "/js/pages/limitations.js",
  "/js/pages/settings.js",
  "/js/pages/styleguide.js",
  "/js/pages/outbreak-map.js",
  "/js/pages/treatment.js",
  "/js/pages/admin-feedback.js",
  "/js/pages/admin-analytics.js",
  "/js/styleguide-entry.js",
  "/locales/en.json",
  "/locales/sw.json",
  "/locales/hi.json",
  "/locales/ta.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      await Promise.all(
        PACK.map(async (url) => {
          try {
            const response = await fetch(url, { cache: "reload" });
            if (response.ok) await cache.put(url, response);
          } catch {
            /* Keep install available when optional assets cannot be fetched. */
          }
        }),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((key) => key.startsWith("fieldnote-") && key !== CACHE).map((key) => caches.delete(key)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "CACHE_OFFLINE_PACK") {
    event.waitUntil(
      (async () => {
        const cache = await caches.open(CACHE);
        await Promise.all(
          PACK.map(async (url) => {
            try {
              const response = await fetch(url, { cache: "reload" });
              if (response.ok) await cache.put(url, response);
            } catch {
              /* Offline pack is best effort for items already not cached. */
            }
          }),
        );
        try {
          const response = await fetch("/api/v1/diseases");
          if (response.ok) await cache.put("/api/v1/diseases", response.clone());
        } catch {
          /* Disease guide illustrations and copy are bundled locally. */
        }
        event.source?.postMessage({ type: "OFFLINE_PACK_SAVED" });
      })(),
    );
  }
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(handleRequest(request, url));
});

async function handleRequest(request, url) {
  try {
    const cache = await caches.open(CACHE);
    const networkFirst =
      request.mode === "navigate" ||
      url.pathname.startsWith("/api/v1/diseases") ||
      /\.(js|css|html|json)$/i.test(url.pathname);

    if (networkFirst) {
      try {
              const response = await fetch(request, { cache: "no-store" });
        if (response.ok) await cache.put(request, response.clone()).catch(() => {});
        return response;
      } catch {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === "navigate") {
          const shell = (await cache.match("/index.html")) || (await cache.match("/"));
          if (shell) return shell;
        }
        return unavailableResponse(url.pathname);
      }
    }

    const cached = await caches.match(request);
    if (cached) return cached;
    try {
      return await fetch(request);
    } catch {
      return unavailableResponse(url.pathname);
    }
  } catch {
    return unavailableResponse(url.pathname);
  }
}

function unavailableResponse(pathname) {
  const isApi = pathname.startsWith("/api/");
  return new Response(isApi ? "{}" : "Resource unavailable", {
    status: 503,
    headers: { "Content-Type": isApi ? "application/json" : "text/plain" },
  });
}

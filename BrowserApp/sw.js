/**
 * sw.js — RST Rating service worker
 * Cache-first strategy for static HTML, JS, and CSS assets.
 */

var CACHE_NAME = "rst-rating-v2";

var PRECACHE_URLS = [
  "./lobby.html",
  "./index.html",
  "./leaderboard.html",
  "./notifications.html",
  "./account.html",
  "./league.html",
  "./match.html",
  "./player.html",
  "./admin.html",
  "./league_settings.html",
  "./create_league.html",
  "./create_season.html",
  "./create_match.html",
  "./invite.html",
  "./discover.html",
  "./preview.html",
  "./palette.js",
  "./toast.js",
  "./manifest.json"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(PRECACHE_URLS).catch(function (err) {
        console.warn("[SW] Pre-cache partial failure:", err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; }).map(function (k) {
          return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  // Only handle GET requests to same origin; skip API calls
  var url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.hostname !== self.location.hostname && !url.hostname.includes("localhost")) return;
  // Skip API requests — let them go to network always
  if (url.pathname.startsWith("/api/") || url.port === "8000") return;

  // For page navigations, prefer fresh network response and fall back to cache.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).then(function (response) {
        if (response && response.status === 200 && response.type === "basic") {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      }).catch(function () {
        return caches.match(event.request).then(function (cached) {
          return cached || caches.match("./lobby.html");
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(function (cached) {
      if (cached) return cached;
      return fetch(event.request).then(function (response) {
        if (!response || response.status !== 200 || response.type !== "basic") return response;
        var clone = response.clone();
        caches.open(CACHE_NAME).then(function (cache) {
          cache.put(event.request, clone);
        });
        return response;
      }).catch(function () {
        // Offline fallback: try lobby.html for navigation requests
        if (event.request.mode === "navigate") {
          return caches.match("./lobby.html");
        }
      });
    })
  );
});

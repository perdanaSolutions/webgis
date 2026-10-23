import tailwindcss from "@tailwindcss/vite"
import { MAP_PAGE_CACHE, MAP_PAGE_URL, MAP_TILE_CACHE, MAP_TILE_URL } from "./utils/mapCacheSchema"

export default defineNuxtConfig({
  css: ["~/src/styles/main.scss", "~/assets/css/index.css"],
  app: {
    head: {
      title: "GIS PWA",
      link: [
        { rel: "icon", type: "image/x-icon", href: "/favicon.ico" },
        // Jika menggunakan PNG, gunakan:
        // { rel: 'icon', type: 'image/png', href: '/favicon.png' }
      ],
    },
  },
  runtimeConfig: {
    apiBaseUrlPythonServer:
      process.env.NUXT_API_BASE_URL_PYTHON_SERVER ||
      "http://gis-backend-python:8000/api",
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL,
      apiBaseUrlPython: process.env.NUXT_PUBLIC_API_BASE_URL_PYTHON,
      tokenBaseMap: process.env.TOKEN_BASE_MAP || "",
    },
  },
  // Dev proxy (opsional, via env): set NUXT_DEV_API_PROXY_TARGET=http://144.91.90.112:8083
  // dan NUXT_PUBLIC_API_BASE_URL_PYTHON=/api di .env lokal -> browser memanggil
  // /api di origin yang sama (localhost) sehingga tidak ada CORS sama sekali.
  // Tanpa env ini (produksi) tidak ada rule tambahan.
  routeRules: process.env.NUXT_DEV_API_PROXY_TARGET
    ? {
        "/api/**": {
          proxy: `${process.env.NUXT_DEV_API_PROXY_TARGET.replace(/\/+$/, "")}/api/**`,
        },
      }
    : {},
  // Pastikan Leaflet berjalan di sisi klien saja (Client-side only)
  modules: ["@pinia/nuxt", "@vite-pwa/nuxt"],
  ssr: true,
  devtools: { enabled: false },
  vite: {
    plugins: [tailwindcss()],
    optimizeDeps: {
      include: [
        "@vue/devtools-core",
        "@vue/devtools-kit",
        "vuetify",
        "leaflet",
        "jspdf",
        "html-to-image",
        "xlsx",
        "vuetify/components",
        "vuetify/directives",
        "vuetify/iconsets/mdi",
      ],
    },
    ssr: {
      noExternal: ["vuetify"],
    },
  },
  pwa: {
    registerType: "autoUpdate",
    manifest: {
      name: "GIS Dashboard PWA",
      short_name: "GISDash",
      theme_color: "#638840",
    },
    workbox: {
      globPatterns: ["**/*.{js,css,html,png,svg,ico}"],
      // JSON API peta tidak masuk service worker: isinya tergantung user dan
      // disimpan lewat Cache Storage di utils/mapCacheSchema.ts.
      runtimeCaching: [
        {
          urlPattern: MAP_PAGE_URL,
          handler: "NetworkFirst",
          method: "GET",
          options: {
            cacheName: MAP_PAGE_CACHE,
            networkTimeoutSeconds: 4,
            expiration: {
              maxEntries: 4,
              maxAgeSeconds: 60 * 60 * 24 * 7,
            },
          },
        },
        {
          urlPattern: MAP_TILE_URL,
          handler: "CacheFirst",
          method: "GET",
          options: {
            cacheName: MAP_TILE_CACHE,
            expiration: {
              maxEntries: 800,
              maxAgeSeconds: 60 * 60 * 24 * 30,
            },
            cacheableResponse: {
              statuses: [0, 200],
            },
          },
        },
      ],
    },
  },
});

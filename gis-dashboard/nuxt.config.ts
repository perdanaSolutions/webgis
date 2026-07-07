export default defineNuxtConfig({
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
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL,
      apiBaseUrlPython: process.env.NUXT_PUBLIC_API_BASE_URL_PYTHON,
    },
  },
  routeRules: {},
  // Pastikan Leaflet berjalan di sisi klien saja (Client-side only)
  modules: ["@nuxtjs/tailwindcss", "@pinia/nuxt", "@vite-pwa/nuxt"],
  ssr: true,
  devtools: { enabled: false },
  vite: {
    optimizeDeps: {
      include: [
        "@vue/devtools-core",
        "@vue/devtools-kit",
        "vuetify",
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
      theme_color: "#000000",
    },
    workbox: {
      globPatterns: ["**/*.{js,css,html,png,svg,ico}"],
      runtimeCaching: [
        {
          urlPattern: "/api/filters",
          handler: "StaleWhileRevalidate",
          method: "GET",
          options: {
            cacheName: "api-filters-cache",
            expiration: {
              maxEntries: 20,
              maxAgeSeconds: 60 * 10,
            },
          },
        },
        {
          urlPattern: "/api/summary",
          handler: "StaleWhileRevalidate",
          method: "GET",
          options: {
            cacheName: "api-summary-cache",
            expiration: {
              maxEntries: 50,
              maxAgeSeconds: 60 * 10,
            },
          },
        },
        {
          urlPattern: "/api/features",
          handler: "NetworkFirst",
          method: "GET",
          options: {
            cacheName: "api-features-cache",
            networkTimeoutSeconds: 4,
            expiration: {
              maxEntries: 50,
              maxAgeSeconds: 60 * 5,
            },
          },
        },
      ],
    },
  },
});

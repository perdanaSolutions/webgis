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
    apiBaseUrlPythonServer:
      process.env.NUXT_API_BASE_URL_PYTHON_SERVER ||
      "http://gis-backend-python:8000/api",
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
    css: {
      preprocessorOptions: {
        scss: {
          // Arahkan ke lokasi file SCSS Anda (misal: src/styles/main.scss)
          additionalData: `@import "@/styles/main.scss";`,
        },
      },
    },
  },
  // Tambahkan konfigurasi tailwind di sini
  tailwindcss: {
    config: {
      theme: {
        extend: {},
      },
      safelist: [
        // === BACKGROUND COLORS (-500) ===
        "bg-slate-500",
        "bg-gray-500",
        "bg-zinc-500",
        "bg-neutral-500",
        "bg-stone-500",
        "bg-red-500",
        "bg-orange-500",
        "bg-amber-500",
        "bg-yellow-500",
        "bg-lime-500",
        "bg-green-500",
        "bg-emerald-500",
        "bg-teal-500",
        "bg-cyan-500",
        "bg-sky-500",
        "bg-blue-500",
        "bg-indigo-500",
        "bg-violet-500",
        "bg-purple-500",
        "bg-fuchsia-500",
        "bg-pink-500",
        "bg-rose-500",

        // === TEXT COLORS (-500) ===
        "text-slate-500",
        "text-gray-500",
        "text-zinc-500",
        "text-neutral-500",
        "text-stone-500",
        "text-red-500",
        "text-orange-500",
        "text-amber-500",
        "text-yellow-500",
        "text-lime-500",
        "text-green-500",
        "text-emerald-500",
        "text-teal-500",
        "text-cyan-500",
        "text-sky-500",
        "text-blue-500",
        "text-indigo-500",
        "text-violet-500",
        "text-purple-500",
        "text-fuchsia-500",
        "text-pink-500",
        "text-rose-500",
      ],
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

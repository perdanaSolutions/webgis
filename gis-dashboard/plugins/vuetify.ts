import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";
import { aliases, mdi } from "vuetify/iconsets/mdi";

import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles";

export default defineNuxtPlugin((nuxtApp) => {
  const vuetify = createVuetify({
    components,
    directives,
    icons: {
      defaultSet: "mdi",
      aliases,
      sets: { mdi },
    },
    theme: {
      // App ini tidak punya desain dark mode; tanpa ini Vuetify mengikuti
      // prefers-color-scheme OS dan men-generate utility class (mis. .bg-surface,
      // .bg-page) yang bentrok nama dengan class warna kustom app (assets/css/colors.css),
      // menimpa warna teksnya jadi putih-di-atas-putih saat OS memakai dark mode.
      defaultTheme: "light",
      utilities: false,
    },
    defaults: {
      VAutocomplete: {
        variant: "outlined",
        density: "comfortable",
        hideDetails: true,
        color: "#638840",
      },
    },
  });

  nuxtApp.vueApp.use(vuetify);
});

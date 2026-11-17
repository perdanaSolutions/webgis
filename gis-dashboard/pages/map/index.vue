<script setup lang="ts">
import { defineAsyncComponent, defineComponent, h } from "vue";
import { MAP_UI, mapColorCssVars } from "~/utils/mapColors";

definePageMeta({ ssr: false });

const MapOpening = defineComponent({
  name: "MapOpening",
  setup() {
    return () =>
      h(
        "main",
        {
          class: "flex min-h-screen items-center justify-center text-14",
          style: {
            ...mapColorCssVars(),
            background: MAP_UI.surface.page,
            color: MAP_UI.text.muted,
          },
        },
        "Membuka peta…",
      );
  },
});

const BlokProfileView = defineAsyncComponent({
  loader: () => import("~/components/blok-profile/BlokProfileView.vue"),
  delay: 0,
  loadingComponent: MapOpening,
});
</script>

<template>
  <BlokProfileView />
</template>

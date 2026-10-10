<script setup lang="ts">
import { defineAsyncComponent, defineComponent, h } from "vue";

definePageMeta({ ssr: false });

const MapOpening = defineComponent({
  name: "MapOpening",
  setup() {
    return () => h(
      "main",
      { class: "flex min-h-screen items-center justify-center bg-[#f4f6f1] text-14 text-[#6e7866]" },
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

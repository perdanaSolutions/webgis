<script setup lang="ts">
defineProps<{
  open: boolean;
  title: string;
  body: string;
  pending?: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();
</script>

<template>
  <AppModalTeleport>
  <div v-if="open" class="app-modal-backdrop app-modal-backdrop--top bg-[#1f2a18]/45" role="alertdialog"
    aria-modal="true" aria-labelledby="basemap-access-title" @click.self="pending ? undefined : emit('close')">
    <div class="app-modal-panel app-modal-size-sm w-full rounded-2xl bg-white shadow-2xl">
      <div class="flex items-start gap-3">
        <span v-if="pending"
          class="mt-0.5 h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[#638840] border-t-transparent"
          aria-hidden="true" />
        <div class="min-w-0">
          <h2 id="basemap-access-title" class="text-base font-bold text-[#1f2a18]">{{ title }}</h2>
          <p class="mt-2 text-13 leading-relaxed text-[#3d4a34]">{{ body }}</p>
        </div>
      </div>
      <div v-if="!pending" class="mt-4 flex justify-end">
        <button type="button" class="rounded-xl bg-[#638840] px-4 py-2 text-13 font-semibold text-white"
          @click="emit('close')">
          Mengerti
        </button>
      </div>
    </div>
  </div>
  </AppModalTeleport>
</template>

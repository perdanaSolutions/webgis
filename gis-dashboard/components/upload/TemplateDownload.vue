<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useDocumentUploadStore } from "~/stores/documentUploadStore";

defineOptions({ name: "UploadTemplateDownload" });

/** Tombol "Standar Format GeoJSON": unduh template contoh (.geojson) & petunjuk kolom (.md) per kategori. */
const store = useDocumentUploadStore();
const open = ref(false);
const root = ref<HTMLElement | null>(null);
const kode = ref("");
const downloading = ref<"" | "geojson" | "md">("");
const error = ref("");

const selectedLabel = computed(
  () => store.categories.find((c) => c.value === kode.value)?.label ?? kode.value,
);

watch(
  () => [open.value, store.selectedCategory] as const,
  ([isOpen]) => {
    if (isOpen && (!kode.value || store.selectedCategory)) kode.value = store.selectedCategory || store.categories[0]?.value || "";
  },
);

async function download(format: "geojson" | "md") {
  if (!kode.value) return;
  downloading.value = format;
  error.value = "";
  try {
    await store.downloadTemplate(kode.value, format);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Gagal mengunduh standar format.";
  } finally {
    downloading.value = "";
  }
}

function onClickOutside(event: MouseEvent) {
  if (open.value && root.value && !root.value.contains(event.target as Node)) open.value = false;
}
onMounted(() => document.addEventListener("click", onClickOutside));
onBeforeUnmount(() => document.removeEventListener("click", onClickOutside));
</script>

<template>
  <div ref="root" class="relative">
    <button type="button" aria-haspopup="true" :aria-expanded="open"
      class="flex items-center gap-2 rounded-xl border border-tan bg-cream px-4 py-2 text-size-sm font-semibold text-brand"
      @click="open = !open">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"
        class="h-4 w-4">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
      </svg>
      Standar Format GeoJSON
      <span aria-hidden="true">▾</span>
    </button>

    <div v-if="open"
      class="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-default bg-surface p-4 text-size-sm shadow-lg">
      <label class="mb-1 block font-medium text-label" for="template-kategori">Kategori</label>
      <select id="template-kategori" v-model="kode"
        class="mb-3 w-full rounded-lg border border-default bg-surface px-2 py-1.5">
        <option v-for="c in store.categories" :key="c.value" :value="c.value">{{ c.label }}</option>
      </select>
      <p class="mb-3 text-size-xs text-muted">
        Contoh file {{ selectedLabel }} dengan nama kolom, tipe geometri, dan koordinat (EPSG:4326) yang lolos
        analisa. Petunjuk berisi daftar kolom wajib/opsional beserta aturannya.
      </p>
      <div class="flex flex-col gap-2">
        <button type="button" :disabled="!kode || !!downloading"
          class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
          @click="download('geojson')">
          {{ downloading === "geojson" ? "Mengunduh..." : "Unduh Template (.geojson)" }}
        </button>
        <button type="button" :disabled="!kode || !!downloading"
          class="rounded-xl border border-tan bg-surface px-4 py-2 font-semibold text-brand disabled:opacity-50"
          @click="download('md')">
          {{ downloading === "md" ? "Mengunduh..." : "Unduh Petunjuk Kolom (.md)" }}
        </button>
      </div>
      <p v-if="error" class="mt-2 text-size-xs text-error-dark">{{ error }}</p>
    </div>
  </div>
</template>

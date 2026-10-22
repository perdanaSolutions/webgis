<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

defineOptions({ name: "UploadColumnFilter" });

/**
 * Filter kolom gaya MS Excel: daftar nilai unik (dengan jumlah baris), pencarian, Pilih semua,
 * dan checkbox multi-pilih. `modelValue` = nilai terpilih; null = tidak difilter (semua nilai).
 */
const props = defineProps<{
  label: string;
  modelValue: string[] | null;
  /** Dipanggil saat dropdown dibuka: nilai unik + jumlah baris (sudah memperhitungkan filter kolom lain). */
  loadOptions: () => Array<{ value: string; count: number }>;
  compact?: boolean;
}>();

const emit = defineEmits<{ (e: "update:modelValue", value: string[] | null): void }>();

const open = ref(false);
const search = ref("");
const options = ref<Array<{ value: string; count: number }>>([]);
const draft = ref<Set<string>>(new Set());
const root = ref<HTMLElement | null>(null);

const EMPTY_LABEL = "(Kosong)";
const active = computed(() => props.modelValue !== null);

const visibleOptions = computed(() => {
  const q = search.value.trim().toLowerCase();
  const list = q ? options.value.filter((o) => (o.value || EMPTY_LABEL).toLowerCase().includes(q)) : options.value;
  return list.slice(0, 1000);
});

const allVisibleChecked = computed(
  () => visibleOptions.value.length > 0 && visibleOptions.value.every((o) => draft.value.has(o.value)),
);

function toggleOpen() {
  if (open.value) {
    open.value = false;
    return;
  }
  options.value = props.loadOptions();
  const selected = props.modelValue;
  draft.value = new Set(selected ?? options.value.map((o) => o.value));
  search.value = "";
  open.value = true;
}

function toggle(value: string) {
  const next = new Set(draft.value);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  draft.value = next;
}

function toggleAll() {
  const next = new Set(draft.value);
  const check = !allVisibleChecked.value;
  for (const o of visibleOptions.value) {
    if (check) next.add(o.value);
    else next.delete(o.value);
  }
  draft.value = next;
}

function apply() {
  const all = options.value.every((o) => draft.value.has(o.value));
  emit("update:modelValue", all && !search.value.trim() ? null : [...draft.value]);
  open.value = false;
}

function clear() {
  emit("update:modelValue", null);
  open.value = false;
}

function onDocumentClick(event: MouseEvent) {
  if (open.value && root.value && !root.value.contains(event.target as Node)) open.value = false;
}

watch(
  () => props.modelValue,
  (value) => {
    if (!open.value) draft.value = new Set(value ?? []);
  },
);

onMounted(() => document.addEventListener("mousedown", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("mousedown", onDocumentClick));
</script>

<template>
  <div ref="root" class="relative inline-flex items-center">
    <button
      type="button"
      class="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-size-xs"
      :class="active ? 'border-brand bg-brand text-white' : 'border-default bg-surface text-muted'"
      :title="`Filter ${label}`"
      @click.stop="toggleOpen"
    >
      <span v-if="!compact">{{ label }}</span>
      <span aria-hidden="true">▾</span>
      <span v-if="active">({{ modelValue?.length ?? 0 }})</span>
    </button>
    <div
      v-if="open"
      class="absolute left-0 top-full z-50 mt-1 w-64 rounded-md border border-default bg-surface p-2 text-left font-normal shadow-lg"
      @click.stop
    >
      <div class="mb-1 text-size-xs font-bold text-brand">Filter: {{ label }}</div>
      <input
        v-model="search"
        type="text"
        placeholder="Cari nilai..."
        class="mb-2 w-full rounded border border-default px-2 py-1 text-size-xs"
      />
      <label class="flex items-center gap-2 border-b border-row pb-1 text-size-xs">
        <input type="checkbox" :checked="allVisibleChecked" @change="toggleAll" />
        <span>(Pilih semua)</span>
      </label>
      <div class="max-h-56 overflow-y-auto py-1">
        <label
          v-for="option in visibleOptions"
          :key="option.value"
          class="flex items-center gap-2 py-0.5 text-size-xs"
        >
          <input type="checkbox" :checked="draft.has(option.value)" @change="toggle(option.value)" />
          <span class="flex-1 truncate">{{ option.value || EMPTY_LABEL }}</span>
          <span class="text-muted">{{ option.count.toLocaleString("id-ID") }}</span>
        </label>
        <div v-if="visibleOptions.length === 0" class="py-1 text-size-xs text-muted">Tidak ada nilai.</div>
      </div>
      <div class="mt-2 flex justify-end gap-2">
        <button type="button" class="rounded px-2 py-1 text-size-xs text-muted" @click="clear">Hapus filter</button>
        <button
          type="button"
          class="rounded bg-brand px-2 py-1 text-size-xs text-white disabled:opacity-50"
          :disabled="draft.size === 0"
          @click="apply"
        >
          OK
        </button>
      </div>
    </div>
  </div>
</template>

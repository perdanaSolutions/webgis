<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { PAGE_SIZES, formatCell, humanizeColumn, paginate, toTableRows } from "~/utils/tablePagination";

defineOptions({ name: "UploadPaginatedTable" });

/** Tabel berhalaman (10/25/50/100), lebar tabel discroll horizontal tanpa membungkus teks. */
const props = withDefaults(
  defineProps<{
    rows: unknown[];
    title?: string;
    scalarColumn?: string;
    columnLabels?: Record<string, string>;
  }>(),
  { title: "", scalarColumn: "nilai", columnLabels: () => ({}) },
);

const pageSize = ref<number>(10);
const page = ref(1);

const table = computed(() => toTableRows(props.rows ?? [], props.scalarColumn));
const view = computed(() => paginate(table.value.rows, page.value, pageSize.value));

watch(() => props.rows, () => { page.value = 1; });
watch(pageSize, () => { page.value = 1; });

function label(column: string) {
  return props.columnLabels[column] ?? humanizeColumn(column);
}
</script>

<template>
  <div class="mb-4">
    <div v-if="title" class="mb-1 text-size-sm font-semibold text-brand">
      {{ title }} ({{ view.total.toLocaleString("id-ID") }})
    </div>
    <div class="overflow-x-auto rounded border border-default bg-surface">
      <table class="w-max min-w-full text-size-xs">
        <thead class="bg-surface-warm text-left text-brand">
          <tr>
            <th class="whitespace-nowrap px-2 py-1 font-bold">#</th>
            <th v-for="c in table.columns" :key="c" class="whitespace-nowrap px-2 py-1 font-bold">{{ label(c) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!view.items.length">
            <td :colspan="table.columns.length + 1" class="px-2 py-2 text-muted">Tidak ada data.</td>
          </tr>
          <tr v-for="(row, i) in view.items" :key="i" class="border-t border-row">
            <td class="whitespace-nowrap px-2 py-1 text-muted">{{ view.start + i }}</td>
            <td v-for="c in table.columns" :key="c" class="whitespace-nowrap px-2 py-1">{{ formatCell(row[c]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="mt-1 flex flex-wrap items-center justify-between gap-2 text-size-xs text-muted">
      <span>
        Menampilkan {{ view.start.toLocaleString("id-ID") }}–{{ view.end.toLocaleString("id-ID") }}
        dari {{ view.total.toLocaleString("id-ID") }} baris
      </span>
      <div class="flex items-center gap-2">
        <label class="flex items-center gap-1">
          Per halaman
          <select v-model.number="pageSize" class="rounded border border-default bg-surface px-1 py-0.5">
            <option v-for="s in PAGE_SIZES" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <button type="button" class="rounded border border-default px-2 py-0.5 disabled:opacity-40"
          :disabled="view.page <= 1" @click="page = view.page - 1">‹ Prev</button>
        <span>Halaman {{ view.page }} dari {{ view.totalPages }}</span>
        <button type="button" class="rounded border border-default px-2 py-0.5 disabled:opacity-40"
          :disabled="view.page >= view.totalPages" @click="page = view.page + 1">Next ›</button>
      </div>
    </div>
  </div>
</template>

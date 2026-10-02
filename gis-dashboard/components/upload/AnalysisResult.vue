<script setup lang="ts">
import { computed, reactive } from "vue";

defineOptions({
  name: "UploadAnalysisResult",
});

/**
 * Menampilkan hasil upload-analyze dari semua jenis layer (blok, tph, sawit, layer dinamis, ...).
 * Field yang dibaca: status_analisis, kesimpulan, peringatan[], rincian{}, plus angka ringkas lain.
 */
const props = defineProps<{
  analysis: Record<string, any>;
}>();

const STATUS_STYLE: Record<string, { title: string; box: string; text: string }> = {
  SIAP: { title: "Siap diunggah", box: "bg-success-light border-default", text: "text-success" },
  SIAP_DENGAN_CATATAN: {
    title: "Siap diunggah, dengan catatan",
    box: "bg-warning-light border-default",
    text: "text-warning",
  },
  TIDAK_ADA_DATA_VALID: {
    title: "Tidak ada data yang bisa diunggah",
    box: "bg-error-light border-error",
    text: "text-error-dark",
  },
};

// Field yang sudah ditampilkan di bagian lain, atau tidak relevan sebagai angka ringkas.
const SUMMARY_SKIP = new Set(["status_analisis", "kesimpulan", "peringatan", "rincian", "tipe_upload", "jenis"]);

const SECTION_TITLES: Record<string, string> = {
  per_estate: "Ringkasan per Estate",
  fitur_ditolak: "Data yang Ditolak",
  fitur_tidak_valid: "Data dengan Atribut Tidak Lengkap",
  fitur_geometri_invalid: "Data dengan Geometri Tidak Valid",
  blok_terpecah: "Blok Terpecah (satu blok di beberapa data)",
  blok_akan_ditimpa: "Blok yang Batasnya Akan Ditimpa",
  blok_baru_di_master: "Blok Baru di Master",
  koreksi_label_blok: "Koreksi Label Blok (dicocokkan dari posisi geometri)",
  contoh_blok_tidak_ditemukan: "Contoh Blok Tidak Ditemukan",
  kolom_tersimpan: "Kolom Atribut yang Disimpan",
};

const COLUMN_LABELS: Record<string, string> = {
  fitur_index: "Data #",
  fitur_yang_tersimpan: "Data yang Tersimpan",
  label_file: "Label di File",
  blok_master: "Blok di Master",
};

function asDataWord(text: string): string {
  return String(text ?? "")
    .replace(/\bFeatures\b/g, "Data")
    .replace(/\bFeature\b/g, "Data")
    .replace(/\bFitur\b/g, "Data")
    .replace(/\bfeatures\b/g, "data")
    .replace(/\bfeature\b/g, "data")
    .replace(/\bfitur\b/g, "data");
}

function humanize(key: string): string {
  const label = COLUMN_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return asDataWord(label);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return value.toLocaleString("id-ID");
  if (typeof value === "boolean") return value ? "Ya" : "Tidak";
  if (Array.isArray(value)) return value.map((v) => formatValue(v)).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const status = computed(() => STATUS_STYLE[props.analysis.status_analisis] ?? null);

const warnings = computed<Array<{ kode: string; level?: string; jumlah?: number; pesan: string }>>(() =>
  Array.isArray(props.analysis.peringatan) ? props.analysis.peringatan : [],
);

// Angka ringkas: nilai skalar di level atas + isi objek satu tingkat (mis. ringkasan_struktur_data).
const summaryRows = computed(() => {
  const rows: Array<{ key: string; label: string; value: string }> = [];
  for (const [key, value] of Object.entries(props.analysis)) {
    if (SUMMARY_SKIP.has(key) || value === null || value === undefined || Array.isArray(value)) continue;
    if (isPlainObject(value)) {
      for (const [subKey, subValue] of Object.entries(value)) {
        if (subValue === null || typeof subValue === "object") continue;
        rows.push({ key: `${key}.${subKey}`, label: humanize(subKey), value: formatValue(subValue) });
      }
      continue;
    }
    rows.push({ key, label: humanize(key), value: formatValue(value) });
  }
  return rows;
});

type Section = {
  key: string;
  title: string;
  count: number;
  columns: string[];
  rows: Record<string, unknown>[];
  items: string[];
};

// Daftar rincian: array objek -> tabel, array nilai -> daftar chip.
const sections = computed<Section[]>(() => {
  const sources: Record<string, unknown> = {
    ...(isPlainObject(props.analysis.rincian) ? props.analysis.rincian : {}),
    koreksi_label_blok: props.analysis.koreksi_label_blok,
    contoh_blok_tidak_ditemukan: props.analysis.contoh_blok_tidak_ditemukan,
    kolom_tersimpan: props.analysis.kolom_tersimpan,
  };
  const result: Section[] = [];
  for (const [key, value] of Object.entries(sources)) {
    if (!Array.isArray(value) || value.length === 0) continue;
    const objects = value.filter(isPlainObject);
    const columns = objects.length ? Array.from(new Set(objects.flatMap((row) => Object.keys(row)))) : [];
    result.push({
      key,
      title: SECTION_TITLES[key] ?? humanize(key),
      count: value.length,
      columns,
      rows: objects,
      items: objects.length ? [] : value.map((v) => asDataWord(formatValue(v))),
    });
  }
  return result;
});

const footnote = computed(() =>
  isPlainObject(props.analysis.rincian) && typeof props.analysis.rincian.catatan === "string"
    ? asDataWord(props.analysis.rincian.catatan)
    : "",
);

const sectionQueries = reactive<Record<string, string>>({});

function sectionQuery(key: string) {
  return sectionQueries[key] ?? "";
}

function filteredRows(section: Section) {
  const query = sectionQuery(section.key).trim().toLowerCase();
  if (!query) return section.rows;
  return section.rows.filter((row) => {
    const haystack = section.columns
      .flatMap((column) => [column, humanize(column), formatValue(row[column])])
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function filteredItems(section: Section) {
  const query = sectionQuery(section.key).trim().toLowerCase();
  if (!query) return section.items;
  return section.items.filter((item) => {
    const haystack = `${section.title} ${item}`.toLowerCase();
    return haystack.includes(query);
  });
}
</script>

<template>
  <div class="space-y-4">
    <!-- Status & kesimpulan -->
    <div v-if="status" class="rounded-2xl border p-4" :class="status.box">
      <p class="font-bold" :class="status.text">{{ status.title }}</p>
      <p v-if="analysis.kesimpulan" class="mt-1 text-size-sm text-label">{{ asDataWord(analysis.kesimpulan) }}</p>
    </div>

    <!-- Peringatan -->
    <div v-if="warnings.length" class="space-y-2">
      <p class="px-1 text-size-xs font-bold uppercase tracking-wider text-muted">Peringatan & Informasi</p>
      <div
        v-for="warning in warnings"
        :key="warning.kode"
        class="flex gap-3 rounded-xl border border-default p-3 text-size-sm"
        :class="warning.level === 'INFO' ? 'bg-surface-neutral' : 'bg-warning-light'"
      >
        <span
          class="h-fit shrink-0 rounded-md border border-default bg-surface px-2 py-0.5 text-size-xs font-bold"
          :class="warning.level === 'INFO' ? 'text-label' : 'text-warning'"
        >
          {{ warning.level === "INFO" ? "INFO" : "PERHATIAN" }}
        </span>
        <span class="text-label">{{ asDataWord(warning.pesan) }}</span>
      </div>
    </div>

    <!-- Angka ringkas -->
    <div v-if="summaryRows.length">
      <p class="mb-2 px-1 text-size-xs font-bold uppercase tracking-wider text-muted">Ringkasan Angka</p>
      <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
        <div
          v-for="row in summaryRows"
          :key="row.key"
          class="flex items-center justify-between gap-3 rounded-xl border border-default-60 bg-surface-neutral p-3"
        >
          <span class="text-size-sm font-medium text-label">{{ row.label }}</span>
          <span
            class="shrink-0 rounded-lg border border-default bg-surface px-3 py-1 text-size-sm font-bold text-content-brown"
          >
            {{ row.value }}
          </span>
        </div>
      </div>
    </div>

    <!-- Rincian -->
    <div v-if="sections.length" class="space-y-2">
      <p class="px-1 text-size-xs font-bold uppercase tracking-wider text-muted">Rincian</p>
      <details
        v-for="section in sections"
        :key="section.key"
        class="rounded-xl border border-default bg-surface"
        :open="section.key === 'per_estate'"
      >
        <summary class="cursor-pointer select-none px-4 py-3 text-size-sm font-semibold text-brand">
          {{ section.title }}
          <span class="ml-1 font-normal text-muted">({{ section.count.toLocaleString("id-ID") }})</span>
        </summary>
        <div class="border-t border-default p-3">
          <div class="mb-3">
            <input
              v-model="sectionQueries[section.key]"
              type="text"
              placeholder="Cari di semua kolom..."
              class="w-full rounded-xl border border-tan bg-surface px-3 py-2 text-size-sm text-brand outline-none focus-border-accent-brown md:max-w-[320px]"
            />
            <p v-if="sectionQuery(section.key).trim()" class="mt-1 text-size-xs text-muted">
              Menampilkan
              {{ (section.rows.length ? filteredRows(section).length : filteredItems(section).length).toLocaleString("id-ID") }}
              dari {{ section.count.toLocaleString("id-ID") }} data
            </p>
          </div>
          <div v-if="section.rows.length" class="max-h-80 overflow-auto rounded-lg border border-default">
            <table class="min-w-full text-size-sm">
              <thead class="sticky top-0 bg-surface-warm text-left text-brand">
                <tr>
                  <th v-for="column in section.columns" :key="column" class="whitespace-nowrap px-3 py-2 font-bold">
                    {{ humanize(column) }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="filteredRows(section).length === 0">
                  <td :colspan="section.columns.length" class="px-3 py-3 text-muted">Tidak ada data yang cocok.</td>
                </tr>
                <tr v-for="(row, index) in filteredRows(section)" :key="index" class="border-t border-row">
                  <td v-for="column in section.columns" :key="column" class="px-3 py-2 align-top">
                    {{ formatValue(row[column]) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else>
            <p v-if="filteredItems(section).length === 0" class="text-size-sm text-muted">Tidak ada data yang cocok.</p>
            <div v-else class="flex flex-wrap gap-2">
              <span
                v-for="item in filteredItems(section)"
                :key="item"
                class="rounded-lg border border-default bg-surface-neutral px-2 py-1 text-size-xs text-label"
              >
                {{ item }}
              </span>
            </div>
          </div>
        </div>
      </details>
      <p v-if="footnote" class="px-1 text-size-xs text-muted">{{ footnote }}</p>
    </div>
  </div>
</template>

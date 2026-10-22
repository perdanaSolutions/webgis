<script setup lang="ts">
import { computed, ref } from "vue";
import type { PartAnalyzeSummary } from "~/utils/geojsonFeatureParts";

defineOptions({ name: "UploadAnalysisGroups" });

/**
 * Rincian hasil analisa dikelompokkan: Analisa Aman (akan disimpan) dan Analisa Gagal (kendala data),
 * gabungan semua part atau per part.
 */
const props = defineProps<{
  analysis: Record<string, any>;
  parts: PartAnalyzeSummary[];
}>();

const selectedPart = ref<number | "all">("all");

const view = computed(() => {
  if (selectedPart.value === "all") {
    return { aman: props.analysis.analisa_aman ?? {}, gagal: props.analysis.analisa_gagal ?? {} };
  }
  const part = props.parts.find((p) => p.part === selectedPart.value);
  return { aman: part?.analisa_aman ?? {}, gagal: part?.analisa_gagal ?? {} };
});

const RINCIAN_TITLES: Record<string, string> = {
  per_estate: "Ringkasan per Estate",
  data_ditolak: "Data Ditolak",
  data_tidak_valid: "Atribut Tidak Lengkap",
  data_geometri_invalid: "Geometri Tidak Valid",
  blok_terpecah: "Blok Terpecah (digabung)",
  blok_akan_ditimpa: "Blok yang Batasnya Ditimpa",
  blok_baru_di_master: "Blok Baru di Master",
  blok_pindah_afdeling: "Blok Pindah Afdeling",
  blok_kembar_di_master: "Blok Kembar di Master",
  grup_pt: "Penyesuaian Grup PT",
  area_estate: "Penyesuaian Area Estate",
  nama_pendek_pt: "Penyesuaian Nama Pendek PT",
};

function title(key: string) {
  return RINCIAN_TITLES[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function sections(rincian: Record<string, unknown> | undefined) {
  return Object.entries(rincian ?? {})
    .filter(([, v]) => Array.isArray(v) && v.length > 0)
    .map(([key, value]) => {
      const rows = (value as unknown[]).map((row) =>
        typeof row === "object" && row !== null && !Array.isArray(row) ? (row as Record<string, unknown>) : { nilai: row },
      );
      const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
      return { key, title: title(key), columns, rows };
    });
}

function fmt(value: unknown): string {
  if (value == null || value === "") return "-";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "number") return value.toLocaleString("id-ID");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

const expanded = ref<Record<string, boolean>>({});
const LIMIT = 10;
function rowsOf(id: string, rows: unknown[]) {
  return expanded.value[id] ? rows : rows.slice(0, LIMIT);
}
function toggle(id: string) {
  expanded.value = { ...expanded.value, [id]: !expanded.value[id] };
}
</script>

<template>
  <div class="space-y-4">
    <div v-if="parts.length > 1" class="flex flex-wrap items-center gap-2 text-size-sm">
      <span class="font-semibold text-brand">Tampilkan:</span>
      <button type="button" class="rounded-lg border px-2 py-1"
        :class="selectedPart === 'all' ? 'border-brand font-bold text-brand' : 'border-default text-muted'"
        @click="selectedPart = 'all'">Semua part</button>
      <button v-for="p in parts" :key="p.part" type="button" class="rounded-lg border px-2 py-1"
        :class="selectedPart === p.part ? 'border-brand font-bold text-brand' : 'border-default text-muted'"
        @click="selectedPart = p.part">
        Part {{ p.part }}/{{ p.total_part }}
        <span class="text-success">✓{{ p.jumlah_aman }}</span>
        <span class="text-error-dark">✗{{ p.jumlah_gagal }}</span>
      </button>
    </div>

    <div v-if="parts.length > 1" class="overflow-x-auto rounded-xl border border-default">
      <table class="min-w-full text-size-sm">
        <thead class="bg-surface-warm text-left text-brand">
          <tr>
            <th class="px-3 py-2">Part</th>
            <th class="px-3 py-2">No. Preview</th>
            <th class="px-3 py-2">Aman</th>
            <th class="px-3 py-2">Gagal</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in parts" :key="p.part" class="border-t border-row">
            <td class="px-3 py-1">{{ p.part }}/{{ p.total_part }}</td>
            <td class="px-3 py-1">{{ p.no_preview_awal ?? "-" }} – {{ p.no_preview_akhir ?? "-" }}</td>
            <td class="px-3 py-1 text-success">{{ p.jumlah_aman.toLocaleString("id-ID") }}</td>
            <td class="px-3 py-1 text-error-dark">{{ p.jumlah_gagal.toLocaleString("id-ID") }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="grid gap-4 lg:grid-cols-2">
      <!-- ANALISA AMAN -->
      <div class="rounded-xl border border-default bg-success-light p-4">
        <h4 class="mb-2 font-bold text-success">
          Analisa Aman — {{ fmt(view.aman.jumlah_data ?? 0) }} data
        </h4>
        <ul v-if="view.aman.catatan?.length" class="mb-3 list-disc pl-5 text-size-sm">
          <li v-for="(note, i) in view.aman.catatan" :key="i">{{ note.pesan }}</li>
        </ul>
        <div v-for="sec in sections(view.aman.rincian)" :key="`aman-${sec.key}`" class="mb-3">
          <div class="mb-1 text-size-sm font-semibold text-brand">{{ sec.title }} ({{ sec.rows.length }})</div>
          <div class="overflow-x-auto rounded border border-default bg-surface">
            <table class="min-w-full text-size-xs">
              <thead class="bg-surface-warm text-left"><tr>
                <th v-for="c in sec.columns" :key="c" class="whitespace-nowrap px-2 py-1">{{ c }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="(row, i) in rowsOf(`aman-${sec.key}`, sec.rows)" :key="i" class="border-t border-row">
                  <td v-for="c in sec.columns" :key="c" class="px-2 py-1">{{ fmt((row as any)[c]) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="sec.rows.length > LIMIT" type="button" class="mt-1 text-size-xs text-brand underline"
            @click="toggle(`aman-${sec.key}`)">
            {{ expanded[`aman-${sec.key}`] ? "Ringkas" : `Tampilkan semua (${sec.rows.length})` }}
          </button>
        </div>
        <p v-if="!sections(view.aman.rincian).length && !view.aman.catatan?.length" class="text-size-sm text-muted">
          Tidak ada rincian tambahan.
        </p>
      </div>

      <!-- ANALISA GAGAL -->
      <div class="rounded-xl border border-error bg-error-light p-4">
        <h4 class="mb-2 font-bold text-error-dark">
          Analisa Gagal — {{ fmt(view.gagal.jumlah_data ?? 0) }} data
        </h4>
        <ul v-if="view.gagal.peringatan?.length" class="mb-3 list-disc pl-5 text-size-sm">
          <li v-for="(note, i) in view.gagal.peringatan" :key="i">{{ note.pesan }}</li>
        </ul>
        <div v-for="group in view.gagal.per_kode ?? []" :key="`kode-${group.kode}`" class="mb-3">
          <div class="mb-1 text-size-sm font-semibold text-error-dark">
            {{ group.kode }} — {{ group.keterangan }} ({{ fmt(group.jumlah) }})
          </div>
          <div class="overflow-x-auto rounded border border-default bg-surface">
            <table class="min-w-full text-size-xs">
              <thead class="bg-surface-warm text-left"><tr>
                <th class="px-2 py-1">No. Preview</th><th class="px-2 py-1">Alasan</th>
              </tr></thead>
              <tbody>
                <tr v-for="(row, i) in rowsOf(`kode-${group.kode}`, group.data ?? [])" :key="i" class="border-t border-row">
                  <td class="px-2 py-1">{{ (row as any).no_preview }}</td>
                  <td class="px-2 py-1">{{ (row as any).alasan }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="(group.data ?? []).length > LIMIT" type="button" class="mt-1 text-size-xs text-brand underline"
            @click="toggle(`kode-${group.kode}`)">
            {{ expanded[`kode-${group.kode}`] ? "Ringkas" : `Tampilkan semua (${group.data.length})` }}
          </button>
        </div>
        <p v-if="!(view.gagal.per_kode ?? []).length" class="text-size-sm text-muted">Tidak ada data gagal.</p>
      </div>
    </div>
  </div>
</template>

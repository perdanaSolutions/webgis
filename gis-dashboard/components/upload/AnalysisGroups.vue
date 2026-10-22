<script setup lang="ts">
import { computed, ref } from "vue";
import UploadPaginatedTable from "~/components/upload/PaginatedTable.vue";
import type { PartAnalyzeSummary } from "~/utils/geojsonFeatureParts";
import { humanizeColumn } from "~/utils/tablePagination";

defineOptions({ name: "UploadAnalysisGroups" });

/**
 * Rincian hasil analisa: Analisa Aman (akan disimpan) dan Analisa Gagal (kendala data),
 * gabungan semua part atau per part. Semua array ditampilkan sebagai tabel berhalaman.
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

const TITLES: Record<string, string> = {
  catatan: "Informasi / Catatan",
  peringatan: "Peringatan",
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
// Array string tanpa nama kolom: beri judul kolom yang bermakna.
const SCALAR_COLUMNS: Record<string, string> = {
  blok_akan_ditimpa: "blok",
  blok_baru_di_master: "blok",
};

type Section = { key: string; title: string; rows: unknown[]; scalar: string };

function title(key: string) {
  return TITLES[key] ?? humanizeColumn(key);
}

/** Semua array di objek (termasuk di dalam `rincian`) -> daftar tabel. */
function sections(group: Record<string, any>, skip: string[] = []): Section[] {
  const out: Section[] = [];
  const visit = (obj: Record<string, any>) => {
    for (const [key, value] of Object.entries(obj ?? {})) {
      if (skip.includes(key)) continue;
      if (Array.isArray(value)) {
        if (value.length) out.push({ key, title: title(key), rows: value, scalar: SCALAR_COLUMNS[key] ?? "nilai" });
      } else if (value && typeof value === "object") {
        visit(value);
      }
    }
  };
  visit(group);
  return out;
}

/** per_kode: tabel ringkasan kode (tanpa kolom data) + tabel data tiap kode. */
const perKode = computed(() => (view.value.gagal.per_kode ?? []) as Array<Record<string, any>>);
const perKodeSummary = computed(() =>
  perKode.value.map(({ data: _data, ...rest }) => rest),
);
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

    <UploadPaginatedTable v-if="parts.length > 1" title="Ringkasan per Part"
      :rows="parts.map((p) => ({ part: `${p.part}/${p.total_part}`,
                                 no_preview: `${p.no_preview_awal ?? '-'} – ${p.no_preview_akhir ?? '-'}`,
                                 aman: p.jumlah_aman, gagal: p.jumlah_gagal }))" />

    <!-- ANALISA AMAN -->
    <div class="min-w-0 rounded-xl border border-default bg-success-light p-4">
      <h4 class="mb-3 font-bold text-success">
        Analisa Aman — {{ Number(view.aman.jumlah_data ?? 0).toLocaleString("id-ID") }} data
      </h4>
      <UploadPaginatedTable v-for="sec in sections(view.aman)" :key="`aman-${selectedPart}-${sec.key}`"
        :title="sec.title" :rows="sec.rows" :scalar-column="sec.scalar" />
      <p v-if="!sections(view.aman).length" class="text-size-sm text-muted">Tidak ada rincian tambahan.</p>
    </div>

    <!-- ANALISA GAGAL -->
    <div class="min-w-0 rounded-xl border border-error bg-error-light p-4">
      <h4 class="mb-3 font-bold text-error-dark">
        Analisa Gagal — {{ Number(view.gagal.jumlah_data ?? 0).toLocaleString("id-ID") }} data
      </h4>
      <UploadPaginatedTable v-if="perKode.length" :key="`kode-${selectedPart}`" title="Ringkasan per Kode Gagal"
        :rows="perKodeSummary" />
      <UploadPaginatedTable v-for="group in perKode" :key="`kode-${selectedPart}-${group.kode}`"
        :title="`${group.kode} — ${group.keterangan ?? ''}`" :rows="group.data ?? []" />
      <UploadPaginatedTable v-for="sec in sections(view.gagal, ['per_kode'])" :key="`gagal-${selectedPart}-${sec.key}`"
        :title="sec.title" :rows="sec.rows" :scalar-column="sec.scalar" />
      <p v-if="!perKode.length && !sections(view.gagal, ['per_kode']).length" class="text-size-sm text-muted">
        Tidak ada data gagal.
      </p>
    </div>
  </div>
</template>

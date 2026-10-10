<script setup lang="ts">
import { computed, ref, watch } from "vue";

const PAGE_SIZE = 8;

const SLOPE_GROUPS = [
  { key: "0-3", label: "0 - 3%" },
  { key: "3-8", label: "3 - 8%" },
  { key: "8-15", label: "8 - 15%" },
  { key: "15-25", label: "15 - 25%" },
  { key: ">25", label: ">25%" },
] as const;

type SlopeRow = {
  id: string;
  blok: string;
  afd: string;
  estate: string;
  luas: number;
  classes: Record<string, number>;
};

const props = defineProps<{
  features: GeoJSON.Feature[];
  loading: boolean;
  error: string;
  period: string;
}>();

const page = ref(1);

function text(value: unknown) {
  const raw = String(value ?? "").trim();
  return raw || "—";
}

function numberOf(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function ha(value: number, digits = 2) {
  return `${value.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits })} ha`;
}

function slopeKey(value: string) {
  const raw = value.trim().toLowerCase().replace(/\s+/g, "").replace(/%/g, "").replace(/–/g, "-");
  if (!raw || raw === "—") return "";
  if (raw.startsWith(">") || raw.startsWith(">=") || raw === "25+") return ">25";
  if (raw.startsWith("0-3")) return "0-3";
  if (raw.startsWith("3-8")) return "3-8";
  if (raw.startsWith("8-15")) return "8-15";
  if (raw.startsWith("15-25")) return "15-25";
  const start = Number(raw.split("-")[0]?.replace(",", "."));
  if (!Number.isFinite(start)) return "";
  if (start >= 25) return ">25";
  if (start >= 15) return "15-25";
  if (start >= 8) return "8-15";
  if (start >= 3) return "3-8";
  return "0-3";
}

const rows = computed<SlopeRow[]>(() => {
  const grouped = new Map<string, SlopeRow>();
  for (const feature of props.features) {
    const properties = (feature.properties ?? {}) as Record<string, unknown>;
    const blok = text(properties.kode_blok);
    const afd = text(properties.kode_afd);
    const estate = text(properties.kode_est);
    const id = String(properties.blok_id ?? `${estate}|${afd}|${blok}`);
    let row = grouped.get(id);
    if (!row) {
      row = {
        id,
        blok,
        afd,
        estate,
        luas: 0,
        classes: Object.fromEntries(SLOPE_GROUPS.map((item) => [item.key, 0])),
      };
      grouped.set(id, row);
    }
    const luas = numberOf(properties.luas);
    row.luas += luas;
    const key = slopeKey(text(properties.kelerengan));
    if (key) row.classes[key] = (row.classes[key] ?? 0) + luas;
  }
  return [...grouped.values()].sort((a, b) => a.blok.localeCompare(b.blok, "id"));
});

const groups = computed(() => {
  const sums: Record<string, number> = Object.fromEntries(SLOPE_GROUPS.map((item) => [item.key, 0]));
  for (const row of rows.value) {
    for (const item of SLOPE_GROUPS) sums[item.key] = (sums[item.key] ?? 0) + (row.classes[item.key] ?? 0);
  }
  return SLOPE_GROUPS.map((item) => ({ ...item, luas: sums[item.key] ?? 0 }));
});

const pageCount = computed(() => Math.max(1, Math.ceil(rows.value.length / PAGE_SIZE)));

const pageRows = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE;
  return rows.value.slice(start, start + PAGE_SIZE);
});

const rangeLabel = computed(() => {
  if (!rows.value.length) return "0 data";
  const start = (page.value - 1) * PAGE_SIZE + 1;
  const end = Math.min(page.value * PAGE_SIZE, rows.value.length);
  return `${start.toLocaleString("id-ID")}–${end.toLocaleString("id-ID")} dari ${rows.value.length.toLocaleString("id-ID")} blok`;
});

watch(() => props.features, () => {
  page.value = 1;
});

watch(pageCount, (count) => {
  if (page.value > count) page.value = count;
});

function go(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next));
}
</script>

<template>
  <section class="bp-card flex flex-col gap-4 p-4">
    <div>
      <h2 class="text-16 font-bold text-[#1f2a18]">Slope Kemiringan</h2>
      <p class="mt-0.5 text-12 text-[#6e7866]">
        {{ period ? `Periode ${period}` : "Poligon kemiringan pada scope aktif" }}
      </p>
    </div>

    <p v-if="loading && !rows.length" class="py-8 text-center text-13 text-[#6e7866]">Memuat data slope…</p>
    <p v-else-if="error && !rows.length" class="py-8 text-center text-13 text-[#b42318]">{{ error }}</p>
    <p v-else-if="!rows.length" class="py-8 text-center text-13 text-[#6e7866]">Belum ada data kemiringan untuk scope ini.</p>

    <template v-else>
      <div class="overflow-x-auto rounded-xl border border-[#d5dcc8]">
        <table class="w-full min-w-[640px] border-collapse text-left text-12">
          <thead class="bg-[#e7ecdf] text-[#3d4a34]">
            <tr>
              <th class="px-2.5 py-2 font-semibold">Blok</th>
              <th class="px-2.5 py-2 font-semibold">Afdeling</th>
              <th class="px-2.5 py-2 font-semibold">Estate</th>
              <th class="px-2.5 py-2 text-right font-semibold">Luas (ha)</th>
              <th v-for="group in SLOPE_GROUPS" :key="group.key" class="px-2.5 py-2 text-right font-semibold">{{ group.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in pageRows" :key="row.id" class="border-t border-[#e4eadc] text-[#1f2a18]">
              <td class="px-2.5 py-1.5 font-semibold">{{ row.blok }}</td>
              <td class="px-2.5 py-1.5">{{ row.afd }}</td>
              <td class="px-2.5 py-1.5">{{ row.estate }}</td>
              <td class="px-2.5 py-1.5 text-right tabular-nums">{{ ha(row.luas) }}</td>
              <td v-for="group in SLOPE_GROUPS" :key="group.key" class="px-2.5 py-1.5 text-right tabular-nums">
                {{ row.classes[group.key] ? ha(row.classes[group.key]!) : "—" }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between gap-2 text-12 text-[#55604c]">
        <span>{{ rangeLabel }}</span>
        <div class="flex items-center gap-1">
          <button type="button" class="slope-page" :disabled="page <= 1" aria-label="Halaman sebelumnya" @click="go(page - 1)">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 6-6 6 6 6" /></svg>
          </button>
          <span class="min-w-[4.5rem] text-center font-semibold text-[#1f2a18]">{{ page }} / {{ pageCount }}</span>
          <button type="button" class="slope-page" :disabled="page >= pageCount" aria-label="Halaman berikutnya" @click="go(page + 1)">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6" /></svg>
          </button>
        </div>
      </div>

      <div>
        <p class="mb-2 text-13 font-bold text-[#1f2a18]">Slope (Kemiringan Lereng) :</p>
        <div class="overflow-x-auto rounded-xl border border-[#c5cdd4]">
          <table class="w-full min-w-[460px] border-collapse text-center text-12">
            <thead>
              <tr class="bg-[#d9dee3] text-[#1f2a18]">
                <th v-for="group in groups" :key="group.key" class="border border-[#c5cdd4] px-2 py-2 font-bold">
                  {{ group.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr class="bg-white">
                <td v-for="group in groups" :key="group.key" class="border border-[#c5cdd4] px-2 py-2 tabular-nums text-[#1f2a18]">
                  {{ ha(group.luas) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.slope-page {
  display: inline-flex;
  height: 28px;
  width: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid #d5dcc8;
  background: #fff;
  color: #1f2a18;
}
.slope-page:hover:not(:disabled) {
  background: #eef3e7;
}
.slope-page:disabled {
  opacity: 0.4;
}
</style>

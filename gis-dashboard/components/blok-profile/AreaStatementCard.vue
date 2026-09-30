<script setup lang="ts">
import { computed } from "vue";

import TruncatedText from "~/components/blok-profile/TruncatedText.vue";
import type { AreaStatementGroup, AreaStatementHistory } from "~/stores/blokProfileStore";

const props = defineProps<{ data: AreaStatementHistory | null; loading: boolean }>();

const grand = computed(() => props.data?.grand_total ?? null);
const years = computed(() => (props.data?.data ?? []).filter((year) => (year.groups ?? []).length));
const rangeLabel = computed(() => {
  const raw = props.data?.meta?.filter_applied?.tahun_tanam;
  return raw ? String(raw).replace(" - ", "–") : "";
});

/** Tampilkan angka apa adanya, tanpa pembulatan ke atas. Desimal dipotong maksimal 2 digit. */
function num(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  const sign = n < 0 ? "-" : "";
  const scaled = Math.trunc(Math.abs(n) * 100 + 1e-8);
  const whole = String(Math.trunc(scaled / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const frac = String(scaled % 100).padStart(2, "0").replace(/0+$/, "");
  return sign + (frac ? `${whole},${frac}` : whole);
}

function groupTitle(keys: { status_tanam?: string | null; jenis_bibit?: string | null }) {
  return [keys.status_tanam, keys.jenis_bibit].filter(Boolean).join(" · ") || "Tanpa status";
}

function groupMeta(keys: {
  bulan_tanam?: string | null;
  tahun_tanam?: number | null;
  jenis_topografi?: string | null;
  jenis_tanah?: string | null;
}) {
  const when = [keys.bulan_tanam, keys.tahun_tanam].filter((part) => part !== null && part !== undefined && part !== "").join(" ");
  return [when ? `Tanam ${when}` : "", keys.jenis_topografi, keys.jenis_tanah].filter(Boolean).join(" · ");
}

function metricRows(totals: AreaStatementGroup["totals"] | Record<string, number>) {
  return [
    { label: "Luas Tanam", value: `${num(totals.luas_tanam)} Ha` },
    { label: "Luas Tanah", value: `${num(totals.luas_tanah)} Ha` },
    { label: "Total Pokok", value: num(totals.total_pokok) },
    { label: "SPH", value: num(totals.sph) },
    { label: "Tanah Datar", value: `${num(totals.pct_tanah_datar)}%` },
    { label: "Berbukit", value: `${num(totals.pct_berbukit)}%` },
    { label: "Gelombang", value: `${num(totals.pct_gelombang)}%` },
    { label: "Curam", value: `${num(totals.pct_curam)}%` },
  ];
}

const summaryRows = computed(() => (grand.value ? metricRows(grand.value) : []));
</script>

<template>
  <section class="bp-card p-5">
    <div class="mb-4 flex items-baseline justify-between gap-3">
      <h2 class="text-18 font-bold text-[#2b2118]">Areal Statement</h2>
      <span v-if="rangeLabel" class="shrink-0 text-12 text-[#8a7a68]">{{ rangeLabel }}</span>
    </div>

    <div v-if="loading && !grand" class="flex h-[132px] items-center justify-center text-13 text-[#8a7a68]">Memuat…</div>
    <p v-else-if="!grand" class="py-8 text-center text-13 text-[#8a7a68]">Belum ada data areal statement untuk scope ini.</p>

    <template v-else>
      <dl class="space-y-1.5">
        <div v-for="row in summaryRows" :key="row.label" class="flex items-baseline justify-between gap-3">
          <dt class="text-12 text-[#8a7a68]">{{ row.label }}</dt>
          <dd class="text-14 font-semibold tabular-nums text-[#2b2118]">{{ row.value }}</dd>
        </div>
      </dl>

      <div v-if="years.length" class="mt-4 max-h-[420px] space-y-4 overflow-y-auto pr-1">
        <div v-for="year in years" :key="year.tahun">
          <p class="mb-1 text-13 font-bold text-[#2b2118]">{{ year.tahun }}</p>
          <ul>
            <li v-for="(group, index) in year.groups" :key="`${year.tahun}-${index}`" class="border-t border-[#f3ece1] py-2">
              <TruncatedText tag="p" class="text-14 font-semibold text-[#2b2118]" :text="groupTitle(group.group_keys)" />
              <TruncatedText tag="p" class="text-12 text-[#8a7a68]" :text="groupMeta(group.group_keys)" />
              <dl class="mt-2 space-y-1">
                <div v-for="row in metricRows(group.totals)" :key="row.label" class="flex items-baseline justify-between gap-3">
                  <dt class="text-12 text-[#8a7a68]">{{ row.label }}</dt>
                  <dd class="text-13 font-semibold tabular-nums text-[#2b2118]">{{ row.value }}</dd>
                </div>
              </dl>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </section>
</template>

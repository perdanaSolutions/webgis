<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { LayerArealData, LayerArealLanduseRow, LayerArealTanamRow } from "~/stores/blokProfileStore";

const PAGE_SIZE = 8;
const MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

const props = defineProps<{ data: LayerArealData | null; loading: boolean; expanded?: boolean }>();

const yearPage = ref(1);

const tanam = computed(() => props.data?.areal_tanam ?? null);
const nonTanam = computed(() => props.data?.areal_non_tanam ?? null);
const total = computed(() => props.data?.total ?? null);
const years = computed(() => tanam.value?.per_tahun_tanam ?? []);
const yearPageCount = computed(() => Math.max(1, Math.ceil(years.value.length / PAGE_SIZE)));
const yearRows = computed(() => (
  props.expanded ? years.value : years.value.slice((yearPage.value - 1) * PAGE_SIZE, yearPage.value * PAGE_SIZE)
));
const shownCategories = computed(() => new Set(
  (nonTanam.value?.per_baris ?? []).flatMap((row) => (row.rincian ?? []).map((item) => item.kategori)),
));
const extraCategories = computed(() => (
  (nonTanam.value?.per_kategori ?? []).filter((row) => row.kategori && !shownCategories.value.has(row.kategori))
));

const tanamShare = computed(() => {
  const value = Number(total.value?.persen_tanam);
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
});

function periodText(value: string | null | undefined) {
  const match = /^(\d{1,2})-(\d{4})$/.exec(String(value ?? "").trim());
  if (!match) return value ? String(value) : "—";
  const name = MONTHS[Number(match[1]) - 1];
  return name ? `${name} ${match[2]}` : String(value);
}

function ha(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${n.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ha`;
}

function num(value: unknown, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function pct(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${n.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function yearLabel(row: LayerArealTanamRow) {
  const year = Number(row.tahun_tanam);
  if (year === 0) return "Belum ditanam";
  return Number.isFinite(year) ? String(year) : "—";
}

function rangeLabel(length: number, page: number) {
  if (!length) return "0 tahun";
  const start = (page - 1) * PAGE_SIZE + 1;
  const end = Math.min(page * PAGE_SIZE, length);
  return `${start.toLocaleString("id-ID")}–${end.toLocaleString("id-ID")} dari ${length.toLocaleString("id-ID")} tahun`;
}

function categoryOf(name: string | undefined): LayerArealLanduseRow | undefined {
  if (!name) return undefined;
  return nonTanam.value?.per_kategori.find((row) => row.kategori === name);
}

function goYear(next: number) {
  yearPage.value = Math.min(yearPageCount.value, Math.max(1, next));
}

watch(years, () => {
  yearPage.value = 1;
});
watch(yearPageCount, (count) => {
  if (yearPage.value > count) yearPage.value = count;
});
</script>

<template>
  <section class="bp-card flex flex-col gap-4 p-4">
    <div>
      <h2 class="text-16 font-bold text-[#1f2a18]">Rincian Areal</h2>
      <p v-if="data" class="mt-0.5 text-12 leading-snug text-[#6e7866]">
        Areal statement {{ periodText(data.periode.areal_statement) }}
        · Landuse {{ periodText(data.periode.landuse) }}
      </p>
    </div>

    <div v-if="loading && !data" class="flex h-[132px] items-center justify-center text-13 text-[#6e7866]">
      Memuat…
    </div>
    <p v-else-if="!data" class="py-6 text-center text-13 text-[#6e7866]">
      Belum ada rincian areal untuk scope ini.
    </p>

    <template v-else>
      <div v-if="total" class="rounded-xl bg-[#f6f8f2] px-3 py-2.5">
        <div class="flex items-baseline justify-between gap-3">
          <p class="text-12 text-[#6e7866]">Grand total areal</p>
          <p class="text-15 font-bold tabular-nums text-[#1f2a18]">{{ ha(total.grand_total_areal) }}</p>
        </div>
        <div class="mt-2 flex h-2 overflow-hidden rounded-full bg-[#e4eadc]" aria-hidden="true">
          <span class="h-full bg-[#638840]" :style="{ width: `${tanamShare}%` }" />
          <span class="h-full bg-[#c4a574]" :style="{ width: `${100 - tanamShare}%` }" />
        </div>
        <div class="mt-2 grid grid-cols-2 gap-3 text-12">
          <p>
            <span class="mr-1 inline-block h-2 w-2 rounded-full bg-[#638840]" />
            <span class="text-[#6e7866]">Tanam</span>
            <span class="mt-0.5 block font-semibold tabular-nums text-[#1f2a18]">{{ ha(total.areal_tanam) }}</span>
            <span class="tabular-nums text-[#55604c]">{{ pct(total.persen_tanam) }}</span>
          </p>
          <p>
            <span class="mr-1 inline-block h-2 w-2 rounded-full bg-[#c4a574]" />
            <span class="text-[#6e7866]">Non-tanam</span>
            <span class="mt-0.5 block font-semibold tabular-nums text-[#1f2a18]">{{ ha(total.areal_non_tanam) }}</span>
            <span class="tabular-nums text-[#55604c]">{{ pct(total.persen_non_tanam) }}</span>
          </p>
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <h3 class="text-13 font-bold text-[#1f2a18]">Areal tanam</h3>
        <p v-if="!tanam" class="text-13 text-[#6e7866]">Belum ada data areal tanam pada periode ini.</p>
        <template v-else>
          <dl class="grid grid-cols-2 gap-x-3 gap-y-2">
            <div>
              <dt class="text-12 text-[#6e7866]">Luas tanam</dt>
              <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ ha(tanam.total_luas_tanam) }}</dd>
            </div>
            <div>
              <dt class="text-12 text-[#6e7866]">Luas tanah</dt>
              <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ ha(tanam.total_luas_tanah) }}</dd>
            </div>
            <div>
              <dt class="text-12 text-[#6e7866]">Pokok</dt>
              <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ num(tanam.total_pokok) }}</dd>
            </div>
            <div>
              <dt class="text-12 text-[#6e7866]">SPH rata-rata</dt>
              <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ num(tanam.sph_rata_rata, 2) }}</dd>
            </div>
            <div>
              <dt class="text-12 text-[#6e7866]">Jumlah blok</dt>
              <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ num(tanam.jumlah_blok) }}</dd>
            </div>
          </dl>

          <div v-if="tanam.per_status.length" class="space-y-1.5">
            <article v-for="row in tanam.per_status" :key="row.status || row.label" class="rounded-xl border border-[#e4eadc] px-3 py-2">
              <div class="flex items-baseline justify-between gap-2">
                <p class="min-w-0">
                  <span class="text-13 font-semibold text-[#1f2a18]">{{ row.status || "—" }}</span>
                  <span v-if="row.label" class="mt-0.5 block text-12 text-[#55604c]">{{ row.label }}</span>
                </p>
                <p class="shrink-0 text-12 tabular-nums text-[#55604c]">{{ num(row.jumlah_blok) }} blok</p>
              </div>
              <dl class="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-12">
                <div>
                  <dt class="text-[#6e7866]">Luas tanam</dt>
                  <dd class="font-semibold tabular-nums text-[#1f2a18]">{{ ha(row.luas_tanam) }}</dd>
                </div>
                <div>
                  <dt class="text-[#6e7866]">Luas tanah</dt>
                  <dd class="font-semibold tabular-nums text-[#1f2a18]">{{ ha(row.luas_tanah) }}</dd>
                </div>
                <div>
                  <dt class="text-[#6e7866]">Pokok</dt>
                  <dd class="font-semibold tabular-nums text-[#1f2a18]">{{ num(row.pokok) }}</dd>
                </div>
                <div>
                  <dt class="text-[#6e7866]">Dari tanam / total</dt>
                  <dd class="font-semibold tabular-nums text-[#1f2a18]">{{ pct(row.persen) }} · {{ pct(row.persen_grand_total) }}</dd>
                </div>
              </dl>
            </article>
          </div>

          <div v-if="years.length" class="overflow-x-auto rounded-xl border border-[#d5dcc8]">
            <table class="w-full border-collapse text-left text-12">
              <thead class="bg-[#e7ecdf] text-[#3d4a34]">
                <tr>
                  <th class="px-2.5 py-2 font-semibold">Tahun tanam</th>
                  <th class="px-2.5 py-2 text-right font-semibold">Luas</th>
                  <th class="px-2.5 py-2 text-right font-semibold">% tanam</th>
                  <th class="px-2.5 py-2 text-right font-semibold">% total</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in yearRows" :key="yearLabel(row)" class="border-t border-[#e4eadc] text-[#1f2a18]">
                  <td class="px-2.5 py-1.5 font-semibold tabular-nums">{{ yearLabel(row) }}</td>
                  <td class="px-2.5 py-1.5 text-right tabular-nums">{{ ha(row.luas_tanam) }}</td>
                  <td class="px-2.5 py-1.5 text-right tabular-nums">{{ pct(row.persen) }}</td>
                  <td class="px-2.5 py-1.5 text-right tabular-nums">{{ pct(row.persen_grand_total) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!expanded && years.length > PAGE_SIZE" class="flex items-center justify-between gap-2 text-12 text-[#55604c]">
            <span>{{ rangeLabel(years.length, yearPage) }}</span>
            <div class="flex items-center gap-1">
              <button type="button" class="la-page" :disabled="yearPage <= 1" aria-label="Halaman tahun tanam sebelumnya"
                @click="goYear(yearPage - 1)">
                <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m15 6-6 6 6 6" />
                </svg>
              </button>
              <span class="min-w-[4.5rem] text-center font-semibold text-[#1f2a18]">{{ yearPage }} / {{ yearPageCount }}</span>
              <button type="button" class="la-page" :disabled="yearPage >= yearPageCount"
                aria-label="Halaman tahun tanam berikutnya" @click="goYear(yearPage + 1)">
                <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m9 6 6 6-6 6" />
                </svg>
              </button>
            </div>
          </div>
        </template>
      </div>

      <div class="flex flex-col gap-2">
        <div class="flex items-baseline justify-between gap-3">
          <h3 class="text-13 font-bold text-[#1f2a18]">Areal non-tanam</h3>
          <span v-if="nonTanam" class="text-12 font-semibold tabular-nums text-[#55604c]">{{ ha(nonTanam.total_luas) }}</span>
        </div>
        <p v-if="!nonTanam" class="text-13 text-[#6e7866]">Belum ada data areal non-tanam pada periode ini.</p>
        <template v-else>
          <article v-for="row in nonTanam.per_baris" :key="row.kode || row.label" class="rounded-xl border border-[#e4eadc] px-3 py-2">
            <div class="flex items-baseline justify-between gap-2">
              <p class="text-13 font-semibold text-[#1f2a18]">{{ row.label || row.kode || "—" }}</p>
              <p class="shrink-0 text-12 font-semibold tabular-nums text-[#1f2a18]">{{ ha(row.luas) }}</p>
            </div>
            <p v-if="row.kode" class="text-11 text-[#6e7866]">{{ row.kode }}</p>
            <p class="mt-0.5 text-11 text-[#6e7866]">
              {{ pct(row.persen) }} dari non-tanam · {{ pct(row.persen_grand_total) }} dari total areal
            </p>
            <ul v-if="row.rincian?.length" class="mt-2 space-y-1.5">
              <li v-for="item in row.rincian" :key="item.kategori" class="text-12 text-[#3d4a34]">
                <span class="flex items-baseline justify-between gap-2">
                  <span class="font-semibold">{{ item.kategori }}</span>
                  <span class="shrink-0 tabular-nums text-[#55604c]">{{ ha(item.luas) }}</span>
                </span>
                <span class="mt-0.5 block text-11 text-[#6e7866]">
                  {{ num(item.jumlah_polygon) }} poligon
                  <template v-if="categoryOf(item.kategori)">
                    · {{ pct(categoryOf(item.kategori)?.persen) }} dari non-tanam
                    · {{ pct(categoryOf(item.kategori)?.persen_grand_total) }} dari total
                  </template>
                </span>
              </li>
            </ul>
          </article>

          <article v-for="row in extraCategories" :key="`${row.kode_baris}-${row.kategori}`" class="rounded-xl border border-[#e4eadc] px-3 py-2">
            <div class="flex items-baseline justify-between gap-2">
              <p class="text-13 font-semibold text-[#1f2a18]">{{ row.kategori || "—" }}</p>
              <p class="shrink-0 text-12 font-semibold tabular-nums text-[#1f2a18]">{{ ha(row.luas) }}</p>
            </div>
            <p v-if="row.kode_baris" class="text-11 text-[#6e7866]">{{ row.kode_baris }}</p>
            <p class="mt-0.5 text-11 text-[#6e7866]">
              {{ num(row.jumlah_polygon) }} poligon · {{ pct(row.persen) }} dari non-tanam · {{ pct(row.persen_grand_total) }} dari total
            </p>
          </article>
        </template>
      </div>
    </template>
  </section>
</template>

<style scoped>
.la-page {
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
.la-page:hover:not(:disabled) {
  background: #eef3e7;
}
.la-page:disabled {
  opacity: 0.4;
}
</style>

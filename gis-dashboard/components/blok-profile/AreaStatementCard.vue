<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { AreaStatementHistory } from "~/stores/blokProfileStore";

const PAGE_SIZE = 10;

const props = defineProps<{ data: AreaStatementHistory | null; loading: boolean }>();

const yearPage = ref(1);
const divisionPage = ref(1);

const groups = computed(() => props.data?.data ?? null);
const years = computed(() => groups.value?.group_tahun_tanam?.details ?? []);
const divisions = computed(() => groups.value?.group_divisi?.details ?? []);
const yearTotal = computed(() => Number(groups.value?.group_tahun_tanam?.total_luas_tanam ?? 0));
const divisionTotal = computed(() => Number(groups.value?.group_divisi?.total_luas_tanam ?? 0));
const areaCode = computed(() => {
  const code = groups.value?.group_tahun_tanam?.area_code || groups.value?.group_divisi?.area_code;
  return code ? String(code) : "";
});

const yearPageCount = computed(() => Math.max(1, Math.ceil(years.value.length / PAGE_SIZE)));
const divisionPageCount = computed(() => Math.max(1, Math.ceil(divisions.value.length / PAGE_SIZE)));
const yearRows = computed(() => years.value.slice((yearPage.value - 1) * PAGE_SIZE, yearPage.value * PAGE_SIZE));
const divisionRows = computed(() => divisions.value.slice((divisionPage.value - 1) * PAGE_SIZE, divisionPage.value * PAGE_SIZE));

function ha(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${n.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ha`;
}

function rangeLabel(length: number, page: number, noun: string) {
  if (!length) return `0 ${noun}`;
  const start = (page - 1) * PAGE_SIZE + 1;
  const end = Math.min(page * PAGE_SIZE, length);
  return `${start.toLocaleString("id-ID")}–${end.toLocaleString("id-ID")} dari ${length.toLocaleString("id-ID")} ${noun}`;
}

function goYear(next: number) {
  yearPage.value = Math.min(yearPageCount.value, Math.max(1, next));
}

function goDivision(next: number) {
  divisionPage.value = Math.min(divisionPageCount.value, Math.max(1, next));
}

watch(years, () => {
  yearPage.value = 1;
});
watch(divisions, () => {
  divisionPage.value = 1;
});
watch(yearPageCount, (count) => {
  if (yearPage.value > count) yearPage.value = count;
});
watch(divisionPageCount, (count) => {
  if (divisionPage.value > count) divisionPage.value = count;
});
</script>

<template>
  <section v-if="loading && !groups" class="bp-card p-5">
    <h2 class="text-18 font-bold text-[#1f2a18]">Areal Statement</h2>
    <div class="flex h-[132px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
  </section>

  <section v-else-if="!groups" class="bp-card p-5">
    <h2 class="text-18 font-bold text-[#1f2a18]">Areal Statement</h2>
    <p class="py-8 text-center text-13 text-[#6e7866]">Belum ada data areal statement untuk scope ini.</p>
  </section>

  <template v-else>
    <section class="bp-card flex flex-col gap-3 p-4">
      <div class="flex items-baseline justify-between gap-3">
        <h2 class="text-16 font-bold text-[#1f2a18]">Tahun Tanam</h2>
        <span v-if="areaCode" class="shrink-0 text-12 text-[#6e7866]">{{ areaCode }}</span>
      </div>

      <p v-if="!years.length" class="py-6 text-center text-13 text-[#6e7866]">Belum ada data tahun tanam.</p>
      <template v-else>
        <div class="overflow-x-auto rounded-xl border border-[#d5dcc8]">
          <table class="w-full border-collapse text-left text-12">
            <thead class="bg-[#e7ecdf] text-[#3d4a34]">
              <tr>
                <th class="px-2.5 py-2 font-semibold">Tahun Tanam</th>
                <th class="px-2.5 py-2 text-right font-semibold">Luas Tanam</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in yearRows" :key="row.tahun_tanam" class="border-t border-[#e4eadc] text-[#1f2a18]">
                <td class="px-2.5 py-1.5 font-semibold tabular-nums">{{ row.tahun_tanam }}</td>
                <td class="px-2.5 py-1.5 text-right tabular-nums">{{ ha(row.luas_tanam) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t border-[#d5dcc8] bg-[#f6f8f2] font-semibold text-[#1f2a18]">
                <td class="px-2.5 py-2">Total</td>
                <td class="px-2.5 py-2 text-right tabular-nums">{{ ha(yearTotal) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div class="flex items-center justify-between gap-2 text-12 text-[#55604c]">
          <span>{{ rangeLabel(years.length, yearPage, "tahun") }}</span>
          <div class="flex items-center gap-1">
            <button type="button" class="as-page" :disabled="yearPage <= 1" aria-label="Halaman tahun tanam sebelumnya" @click="goYear(yearPage - 1)">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 6-6 6 6 6" /></svg>
            </button>
            <span class="min-w-[4.5rem] text-center font-semibold text-[#1f2a18]">{{ yearPage }} / {{ yearPageCount }}</span>
            <button type="button" class="as-page" :disabled="yearPage >= yearPageCount" aria-label="Halaman tahun tanam berikutnya" @click="goYear(yearPage + 1)">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6" /></svg>
            </button>
          </div>
        </div>
      </template>
    </section>

    <section class="bp-card flex flex-col gap-3 p-4">
      <div class="flex items-baseline justify-between gap-3">
        <h2 class="text-16 font-bold text-[#1f2a18]">Divisi</h2>
        <span v-if="areaCode" class="shrink-0 text-12 text-[#6e7866]">{{ areaCode }}</span>
      </div>

      <p v-if="!divisions.length" class="py-6 text-center text-13 text-[#6e7866]">Belum ada data divisi.</p>
      <template v-else>
        <div class="overflow-x-auto rounded-xl border border-[#d5dcc8]">
          <table class="w-full border-collapse text-left text-12">
            <thead class="bg-[#e7ecdf] text-[#3d4a34]">
              <tr>
                <th class="px-2.5 py-2 font-semibold">Kode Divisi</th>
                <th class="px-2.5 py-2 text-right font-semibold">Luas Tanam</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in divisionRows" :key="row.division_code" class="border-t border-[#e4eadc] text-[#1f2a18]">
                <td class="px-2.5 py-1.5 font-semibold">{{ row.division_code }}</td>
                <td class="px-2.5 py-1.5 text-right tabular-nums">{{ ha(row.luas_tanam) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t border-[#d5dcc8] bg-[#f6f8f2] font-semibold text-[#1f2a18]">
                <td class="px-2.5 py-2">Total</td>
                <td class="px-2.5 py-2 text-right tabular-nums">{{ ha(divisionTotal) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div class="flex items-center justify-between gap-2 text-12 text-[#55604c]">
          <span>{{ rangeLabel(divisions.length, divisionPage, "divisi") }}</span>
          <div class="flex items-center gap-1">
            <button type="button" class="as-page" :disabled="divisionPage <= 1" aria-label="Halaman divisi sebelumnya" @click="goDivision(divisionPage - 1)">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 6-6 6 6 6" /></svg>
            </button>
            <span class="min-w-[4.5rem] text-center font-semibold text-[#1f2a18]">{{ divisionPage }} / {{ divisionPageCount }}</span>
            <button type="button" class="as-page" :disabled="divisionPage >= divisionPageCount" aria-label="Halaman divisi berikutnya" @click="goDivision(divisionPage + 1)">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6" /></svg>
            </button>
          </div>
        </div>
      </template>
    </section>
  </template>
</template>

<style scoped>
.as-page {
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
.as-page:hover:not(:disabled) {
  background: #eef3e7;
}
.as-page:disabled {
  opacity: 0.4;
}
</style>

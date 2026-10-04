<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";

const props = defineProps<{ open: boolean; detail: Record<string, any> | null }>();
const emit = defineEmits<{ (e: "close"): void }>();

function num(value: unknown, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("id-ID", { maximumFractionDigits: digits }) : "-";
}

const info = computed(() => props.detail?.informasi_blok ?? {});
const prod = computed(() => props.detail?.produksi_tbs ?? {});
const areal = computed(() => props.detail?.areal_statement?.grand_total ?? {});
const rotasi = computed(() => (props.detail?.rotasi_pusingan?.daftar_rotasi ?? []) as Array<Record<string, any>>);

const sections = computed(() => [
  {
    title: "Areal Statement",
    note: props.detail?.areal_statement?.periode ? `periode ${props.detail.areal_statement.periode}` : "",
    rows: [
      ["Luas Tanam", `${num(areal.value.luas_tanam)} Ha`], ["Luas Tanah", `${num(areal.value.luas_tanah)} Ha`],
      ["Total Pokok", num(areal.value.total_pokok, 0)], ["SPH", num(areal.value.sph, 1)],
      ["Topografi", info.value.jenis_topografi ?? "-"], ["Jenis Tanah", info.value.jenis_tanah ?? "-"],
    ],
  },
  {
    title: "Produksi TBS",
    note: props.detail?.periode?.label_periode ?? "",
    rows: [
      ["TBS Aktual", `${num((prod.value.tbs?.aktual ?? 0) / 1000)} ton`], ["TBS Budget", `${num((prod.value.tbs?.budget ?? 0) / 1000)} ton`],
      ["Pencapaian", `${num(prod.value.tbs?.pct_achievement, 1)}%`], ["Kategori", prod.value.kategori_budget ?? "-"],
      ["Janjang Aktual", num(prod.value.janjang?.aktual, 0)], ["BJR Aktual", `${num(prod.value.bjr?.aktual)} kg`],
      ["Kg / Pokok", num(prod.value.kpi_per_pokok?.kg_pkk)], ["Janjang / Pokok", num(prod.value.kpi_per_pokok?.jjg_pkk)],
    ],
  },
]);

function onKey(event: KeyboardEvent) {
  if (event.key === "Escape" && props.open) emit("close");
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <Transition name="bp-drawer">
    <div v-if="open" class="fixed inset-0 z-[3000] flex justify-end bg-black/30" @click.self="emit('close')">
      <aside class="flex h-full w-full max-w-[460px] flex-col bg-[#fbfcf9] shadow-2xl" role="dialog" aria-modal="true"
        :aria-label="`Detail blok ${info.kode_blok ?? ''}`">
        <header class="flex items-start justify-between gap-3 border-b border-[#d5dcc8] px-6 py-5">
          <div>
            <p class="text-12 font-semibold uppercase tracking-wider text-[#6e7866]">Detail Blok</p>
            <h2 class="text-[22px] font-bold text-[#1f2a18]">{{ info.kode_blok ?? "-" }}</h2>
            <p class="text-13 text-[#6e7866]">
              {{ [info.hierarki?.nama_pt, info.hierarki?.nama_estate, info.hierarki?.kode_afd].filter(Boolean).join(" · ") }}
            </p>
          </div>
          <button type="button" class="rounded-lg p-2 text-[#55604c] hover:bg-[#eef3e7]" aria-label="Tutup" @click="emit('close')">
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        </header>

        <div class="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <section v-for="section in sections" :key="section.title">
            <div class="mb-2 flex items-baseline justify-between">
              <h3 class="text-15 font-bold text-[#1f2a18]">{{ section.title }}</h3>
              <span class="text-12 text-[#6e7866]">{{ section.note }}</span>
            </div>
            <dl class="grid grid-cols-2 gap-x-6 gap-y-2.5 rounded-xl border border-[#d5dcc8] p-4">
              <div v-for="[label, value] in section.rows" :key="label">
                <dt class="text-12 text-[#6e7866]">{{ label }}</dt>
                <dd class="text-14 font-semibold text-[#1f2a18]">{{ value }}</dd>
              </div>
            </dl>
          </section>

          <section>
            <div class="mb-2 flex items-baseline justify-between">
              <h3 class="text-15 font-bold text-[#1f2a18]">Rotasi Panen</h3>
              <span class="text-12 text-[#6e7866]">{{ rotasi.length }} kegiatan</span>
            </div>
            <p v-if="!rotasi.length" class="rounded-xl border border-[#d5dcc8] p-4 text-13 text-[#6e7866]">Belum ada data rotasi.</p>
            <table v-else class="w-full overflow-hidden rounded-xl border border-[#d5dcc8] text-13">
              <thead class="bg-[#eef3e7] text-left text-12 text-[#55604c]">
                <tr><th class="px-3 py-2">Periode</th><th class="px-3 py-2 text-right">Rotasi</th><th class="px-3 py-2 text-right">Pusingan</th><th class="px-3 py-2">Status</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in rotasi" :key="row.id_rotasi_pusingan" class="border-t border-[#d5dcc8]">
                  <td class="px-3 py-1.5">{{ String(row.tanggal ?? '').slice(0, 7) }}</td>
                  <td class="px-3 py-1.5 text-right tabular-nums">{{ num(row.rotasi_ke, 1) }}</td>
                  <td class="px-3 py-1.5 text-right tabular-nums">{{ row.pusingan_hari ?? '-' }} hr</td>
                  <td class="px-3 py-1.5">{{ row.status_pusingan ?? '-' }}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.bp-drawer-enter-active,
.bp-drawer-leave-active { transition: opacity 0.2s ease; }
.bp-drawer-enter-active aside,
.bp-drawer-leave-active aside { transition: transform 0.2s ease; }
.bp-drawer-enter-from,
.bp-drawer-leave-to { opacity: 0; }
.bp-drawer-enter-from aside,
.bp-drawer-leave-to aside { transform: translateX(24px); }
</style>

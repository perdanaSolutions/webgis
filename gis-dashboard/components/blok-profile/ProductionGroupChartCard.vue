<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import {
  compactTon,
  pctOf,
  periodTitle,
  scaleMax,
  tooltipRows,
  type ProductionGroupChart,
  type ProductionGroupItem,
} from "~/utils/productionGroups";

const props = defineProps<{
  data: ProductionGroupChart | null;
  loading: boolean;
}>();

type Section = { key: string; title: string; items: ProductionGroupItem[]; scroll?: boolean };

const sections = computed<Section[]>(() => {
  const groups = props.data?.group_produksi_ton;
  if (!groups) return [];
  const total = groups.total;
  // Bar gabungan (mis. "TPA + SGA") hanya berarti bila ada lebih dari satu grup.
  const groupItems = total && groups.by_group.length > 1 ? [...groups.by_group, total] : groups.by_group;
  return [
    { key: "grup", title: "Grup", items: groupItems },
    { key: "area", title: "Area", items: groups.by_area },
    { key: "estate", title: "Estate", items: groups.by_estate, scroll: true },
  ].filter((s) => s.items.length);
});

const title = computed(() => periodTitle(props.data?.periode));

type Tip = { id: string; item: ProductionGroupItem; row: DOMRect; card: DOMRect };

const active = ref<Tip | null>(null);
const pinned = ref<string | null>(null);
const cardEl = ref<HTMLElement | null>(null);
const tipEl = ref<HTMLElement | null>(null);
const tipPos = ref({ left: 0, top: 0, width: 280 });

function rowId(section: Section, item: ProductionGroupItem) {
  return `${section.key}:${item.kode ?? item.nama}`;
}

/**
 * Tooltip dirender di <body> dengan posisi fixed: kartu-kartu panel punya stacking context dan panelnya
 * ber-scroll, jadi tooltip di dalam kartu tertutup kartu berikutnya / terpotong. Di bawah baris bila muat,
 * selain itu di atas baris; selalu dijaga di dalam layar.
 */
async function place() {
  const tip = active.value;
  if (!tip) return;
  const width = Math.min(300, Math.max(220, tip.card.width - 16));
  const left = Math.max(8, Math.min(window.innerWidth - width - 8, tip.card.left + (tip.card.width - width) / 2));
  tipPos.value = { left, top: tip.row.bottom + 4, width };
  await nextTick();
  const height = tipEl.value?.offsetHeight ?? 0;
  const below = tip.row.bottom + 4;
  const above = tip.row.top - height - 4;
  const top = below + height <= window.innerHeight - 8 ? below : above >= 8 ? above : Math.max(8, window.innerHeight - height - 8);
  tipPos.value = { left, top, width };
}

function show(section: Section, item: ProductionGroupItem, event: Event) {
  const row = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const card = cardEl.value?.getBoundingClientRect() ?? row;
  active.value = { id: rowId(section, item), item, row, card };
  void place();
}

function hide(section: Section, item: ProductionGroupItem) {
  const id = rowId(section, item);
  if (active.value?.id === id && pinned.value !== id) active.value = null;
}

function toggle(section: Section, item: ProductionGroupItem, event: Event) {
  const id = rowId(section, item);
  if (pinned.value === id) {
    pinned.value = null;
    active.value = null;
    return;
  }
  pinned.value = id;
  show(section, item, event);
}

/** Posisi fixed tidak ikut bergeser saat panel/daftar di-scroll, jadi tooltip ditutup. */
function dismiss() {
  pinned.value = null;
  active.value = null;
}

onMounted(() => {
  window.addEventListener("scroll", dismiss, true);
  window.addEventListener("resize", dismiss);
});
onBeforeUnmount(() => {
  window.removeEventListener("scroll", dismiss, true);
  window.removeEventListener("resize", dismiss);
});
</script>

<template>
  <section ref="cardEl" class="bp-card flex flex-col gap-3 p-4">
    <div class="flex flex-col gap-1">
      <h2 class="text-18 font-bold text-[#1f2a18]">Produksi TBS (Ton)</h2>
      <p v-if="title" class="text-12 text-[#55604c]">{{ title }}</p>
      <ul class="pg-legend" aria-label="Keterangan grafik">
        <li><span class="pg-key pg-key--bar" aria-hidden="true" />Aktual</li>
        <li><span class="pg-key pg-key--budget" aria-hidden="true" />Budget</li>
        <li><span class="pg-key pg-key--lalu" aria-hidden="true" />Aktual tahun lalu</li>
      </ul>
    </div>

    <div v-if="loading && !sections.length" class="flex h-[132px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
    <p v-else-if="!sections.length" class="py-8 text-center text-13 text-[#6e7866]">Belum ada data produksi untuk scope ini.</p>

    <template v-else>
    <div v-for="section in sections" :key="section.key" class="pg-section">
      <h3 class="mb-1.5 text-13 font-bold text-[#1f2a18]">{{ section.title }}</h3>
      <div :class="section.scroll && 'pg-scroll'">
        <button v-for="item in section.items" :key="rowId(section, item)" type="button" class="pg-row"
          :class="active?.id === rowId(section, item) && 'is-active'"
          :aria-label="`${item.nama}: aktual ${compactTon(item.aktual_ton)} ton, budget ${compactTon(item.budget_ton)} ton`"
          :aria-expanded="active?.id === rowId(section, item)"
          @mouseenter="show(section, item, $event)" @mouseleave="hide(section, item)"
          @focus="show(section, item, $event)" @blur="hide(section, item)"
          @click="toggle(section, item, $event)">
          <span class="pg-label" :title="item.nama_lengkap || item.nama">{{ item.nama }}</span>
          <span class="pg-track">
            <span class="pg-bar" :style="{ width: `${pctOf(item.aktual_ton, scaleMax(section.items))}%` }" />
            <span v-if="item.aktual_tahun_lalu_ton > 0" class="pg-tick pg-tick--lalu"
              :style="{ left: `${pctOf(item.aktual_tahun_lalu_ton, scaleMax(section.items))}%` }" />
            <span v-if="item.budget_ton > 0" class="pg-tick pg-tick--budget"
              :style="{ left: `${pctOf(item.budget_ton, scaleMax(section.items))}%` }" />
          </span>
          <span class="pg-value">{{ compactTon(item.aktual_ton) }}</span>
        </button>
      </div>

    </div>
    </template>

    <Teleport to="body">
      <div v-if="active" ref="tipEl" class="pg-tip" role="tooltip"
        :style="{ left: `${tipPos.left}px`, top: `${tipPos.top}px`, width: `${tipPos.width}px` }">
        <p class="mb-1 font-bold">{{ active.item.nama_lengkap || active.item.nama }}</p>
        <p v-if="title" class="mb-1.5 text-[#55604c]">{{ title }}</p>
        <dl>
          <template v-for="row in tooltipRows(active.item)" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd :class="row.tone && `is-${row.tone}`">{{ row.value }}</dd>
          </template>
        </dl>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.pg-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  font-size: 11px;
  color: #55604c;
}
.pg-legend li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pg-key {
  display: inline-block;
}
.pg-key--bar {
  width: 12px;
  height: 10px;
  border-radius: 2px;
  background: #3a9a45;
}
.pg-key--budget,
.pg-key--lalu {
  width: 3px;
  height: 12px;
  border-radius: 1px;
}
.pg-key--budget {
  background: #c62828;
}
.pg-key--lalu {
  background: #e3b505;
}
.pg-scroll {
  max-height: 340px;
  overflow-y: auto;
  padding-right: 2px;
}
.pg-row {
  display: grid;
  grid-template-columns: 74px 1fr 76px;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 3px 4px;
  border-radius: 6px;
  text-align: left;
  font-size: 12px;
  color: #1f2a18;
}
.pg-row:hover,
.pg-row.is-active,
.pg-row:focus-visible {
  background: #eef3e7;
  outline: none;
}
.pg-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.pg-track {
  position: relative;
  height: 14px;
}
.pg-bar {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 0 4px 4px 0;
  background: #3a9a45;
}
.pg-tick {
  position: absolute;
  top: -3px;
  bottom: -3px;
  width: 3px;
  margin-left: -1.5px;
  border-radius: 1px;
  box-shadow: 0 0 0 1px #fff;
}
.pg-tick--budget {
  background: #c62828;
}
.pg-tick--lalu {
  background: #e3b505;
}
.pg-value {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #3b4534;
}
.pg-tip {
  position: fixed;
  z-index: 3000;
  padding: 10px 12px;
  border: 1px solid #d5dcc8;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgb(31 42 24 / 0.16);
  font-size: 12px;
  color: #1f2a18;
  pointer-events: none;
}
.pg-tip dl {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px 12px;
}
.pg-tip dt {
  color: #55604c;
}
.pg-tip dd {
  text-align: right;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.pg-tip dd.is-good {
  color: #2e7d32;
}
.pg-tip dd.is-bad {
  color: #c62828;
}
</style>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type ProductionRow = {
  tahun: number
  ton: number
  ton_ha: number
  ton_ha_budget: number | null
}

type RotationRow = {
  tahun: number
  hari: number
}

type SlopeSlice = {
  key: string
  label: string
  color: string
  ha: number
  pct: number
}

const SLOPE = [
  { key: '0-3%', label: 'Datar', color: '#d7e4c8' },
  { key: '3-8%', label: 'Gelombang', color: '#a3c07e' },
  { key: '8-15%', label: 'Berbukit', color: '#638840' },
  { key: '15-25%', label: 'Curam', color: '#3d5528' },
  { key: '>25%', label: 'Sangat', color: '#243618' },
]

const loading = ref(true)
const production = ref<ProductionRow[]>([])
const rotation = ref<RotationRow[]>([])
const slope = ref<SlopeSlice[]>([])

const hasBudget = computed(() => production.value.some((row) => row.ton_ha_budget != null))

function num(value: number, digits = 1) {
  return value.toLocaleString('id-ID', { maximumFractionDigits: value >= 100 ? 0 : digits })
}

function yearOf(value: unknown) {
  const year = Number(value)
  return Number.isFinite(year) ? year : null
}

function takeRecent<T extends { tahun: number }>(rows: T[]) {
  return [...rows].sort((a, b) => a.tahun - b.tahun).slice(-6)
}

function barHeight(value: number, max: number) {
  if (max <= 0 || value <= 0) return 0
  return Math.max((value / max) * 100, 8)
}

function lineX(index: number) {
  const count = production.value.length
  if (count <= 1) return 50
  return 4 + (index / (count - 1)) * 92
}

function pointY(value: number) {
  const values = production.value.flatMap((row) => [
    row.ton_ha,
    ...(row.ton_ha_budget == null ? [] : [row.ton_ha_budget]),
  ])
  const max = Math.max(...values, 0)
  const min = Math.min(...values, max)
  const pad = Math.max((max - min) * 0.35, 0.15)
  const low = Math.max(min - pad, 0)
  const high = max + pad
  return 34 - ((value - low) / Math.max(high - low, 0.1)) * 30
}

function linePoints(pick: (row: ProductionRow) => number | null) {
  const rows = production.value
    .map((row, index) => ({ index, value: pick(row) }))
    .filter((row): row is { index: number; value: number } => row.value != null)
  if (!rows.length) return ''
  return rows.map((row) => `${lineX(row.index)},${pointY(row.value)}`).join(' ')
}

async function loadTable(table: string) {
  const { $api } = useNuxtApp()
  const base = useRuntimeConfig().public.apiBaseUrlPython as string
  return $api<Record<string, any>>(`${base}/v1/spatial/history?table=${table}`)
}

onMounted(async () => {
  const [produksiResult, rotasiResult] = await Promise.allSettled([
    loadTable('trx_produksi_tbs'),
    loadTable('trx_rotasi_pusingan'),
  ])

  if (produksiResult.status === 'fulfilled') {
    const payload = produksiResult.value
    production.value = takeRecent(
      ((payload.data_histori ?? []) as Array<Record<string, any>>)
        .map((row) => {
          const tahun = yearOf(row.tahun)
          if (tahun == null) return null
          const budget = row.ton_ha_budget == null ? null : Number(row.ton_ha_budget)
          return {
            tahun,
            ton: Number(row.ton ?? 0),
            ton_ha: Number(row.ton_ha ?? 0),
            ton_ha_budget: budget != null && Number.isFinite(budget) ? budget : null,
          }
        })
        .filter((row): row is ProductionRow => row != null),
    )

    const hectares = (payload.slope_kemiringan_lereng_ha ?? {}) as Record<string, number>
    const slices = SLOPE.map((item) => ({
      ...item,
      ha: Number(hectares[item.key] ?? 0),
    })).filter((item) => item.ha > 0)
    const total = slices.reduce((sum, item) => sum + item.ha, 0)
    slope.value = total
      ? slices.map((item) => ({ ...item, pct: (item.ha / total) * 100 }))
      : []
  }

  if (rotasiResult.status === 'fulfilled') {
    rotation.value = takeRecent(
      ((rotasiResult.value.data ?? []) as Array<Record<string, any>>)
        .map((row) => {
          const tahun = yearOf(row.tahun)
          if (tahun == null) return null
          return { tahun, hari: Number(row.avg_pusingan_hari ?? 0) }
        })
        .filter((row): row is RotationRow => row != null),
    )
  }

  loading.value = false
})

const productionMax = computed(() => Math.max(...production.value.map((row) => row.ton), 1))
const rotationMax = computed(() => Math.max(...rotation.value.map((row) => row.hari), 1))
const latestProduction = computed(() => production.value.at(-1) ?? null)
const latestRotation = computed(() => rotation.value.at(-1) ?? null)
const leadSlope = computed(() =>
  [...slope.value].sort((a, b) => b.pct - a.pct)[0] ?? null,
)
</script>

<template>
  <div class="container">
    <div class="banner-charts">
      <article class="banner-charts__card">
        <header class="banner-charts__head">
          <h1>Produksi TBS</h1>
          <span>{{ latestProduction ? `${num(latestProduction.ton)} t` : 'ton' }}</span>
        </header>
        <p v-if="loading" class="banner-charts__empty">Memuat…</p>
        <p v-else-if="!production.length" class="banner-charts__empty">Belum ada data</p>
        <div v-else class="banner-charts__plot" role="img"
          :aria-label="`Produksi TBS: ${production.map((row) => `${row.tahun} ${num(row.ton)} ton`).join(', ')}`">
          <div class="banner-charts__bars">
            <div v-for="row in production" :key="row.tahun" class="banner-charts__bar">
              <i :class="row.tahun === latestProduction?.tahun && 'is-latest'"
                :style="{ height: `${barHeight(row.ton, productionMax)}%` }"
                :title="`${row.tahun}: ${num(row.ton)} ton`" />
            </div>
          </div>
          <div class="banner-charts__years is-columns">
            <small v-for="row in production" :key="row.tahun">{{ row.tahun }}</small>
          </div>
        </div>
      </article>

      <article class="banner-charts__card">
        <header class="banner-charts__head">
          <h1>Yield</h1>
          <span>{{ latestProduction ? `${num(latestProduction.ton_ha, 2)} t/ha` : 'ton/ha' }}</span>
        </header>
        <p v-if="loading" class="banner-charts__empty">Memuat…</p>
        <p v-else-if="!production.length" class="banner-charts__empty">Belum ada data</p>
        <div v-else class="banner-charts__plot" role="img"
          :aria-label="`Yield: ${production.map((row) => `${row.tahun} ${num(row.ton_ha, 2)} ton per hektare`).join(', ')}`">
          <div class="banner-charts__line-wrap">
            <svg viewBox="0 0 100 40" class="banner-charts__line" preserveAspectRatio="none">
              <polyline v-if="hasBudget" :points="linePoints((row) => row.ton_ha_budget)" class="is-budget" />
              <polyline :points="linePoints((row) => row.ton_ha)" class="is-actual" />
            </svg>
            <span v-for="(row, index) in production" :key="row.tahun" class="banner-charts__dot" :style="{
              left: `${lineX(index)}%`,
              top: `${(pointY(row.ton_ha) / 40) * 100}%`,
            }" :title="`${row.tahun}: ${num(row.ton_ha, 2)} t/ha`" />
          </div>
          <div class="banner-charts__years">
            <small v-for="row in production" :key="row.tahun">{{ row.tahun }}</small>
          </div>
          <p v-if="hasBudget" class="banner-charts__legend">
            <span><i class="is-actual" /> Aktual</span>
            <span><i class="is-budget" /> Budget</span>
          </p>
        </div>
      </article>

      <article class="banner-charts__card">
        <header class="banner-charts__head">
          <h1>Kemiringan</h1>
          <span>{{ leadSlope ? `${Math.round(leadSlope.pct)}% ${leadSlope.label}` : 'ha' }}</span>
        </header>
        <p v-if="loading" class="banner-charts__empty">Memuat…</p>
        <p v-else-if="!slope.length" class="banner-charts__empty">Belum ada data</p>
        <div v-else class="banner-charts__plot" role="img"
          :aria-label="`Kemiringan: ${slope.map((item) => `${item.label} ${Math.round(item.pct)} persen`).join(', ')}`">
          <div class="banner-charts__stack">
            <span v-for="item in slope" :key="item.key" :style="{ width: `${item.pct}%`, background: item.color }"
              :title="`${item.label}: ${num(item.ha, 1)} ha`" />
          </div>
          <ul class="banner-charts__slope">
            <li v-for="item in slope" :key="item.key">
              <i :style="{ background: item.color }" />
              <span>{{ item.label }}</span>
              <strong>{{ Math.round(item.pct) }}%</strong>
            </li>
          </ul>
        </div>
      </article>

      <article class="banner-charts__card">
        <header class="banner-charts__head">
          <h1>Rotasi</h1>
          <span>{{ latestRotation ? `${num(latestRotation.hari, 1)} hari` : 'hari' }}</span>
        </header>
        <p v-if="loading" class="banner-charts__empty">Memuat…</p>
        <p v-else-if="!rotation.length" class="banner-charts__empty">Belum ada data</p>
        <div v-else class="banner-charts__plot" role="img"
          :aria-label="`Rata-rata pusingan: ${rotation.map((row) => `${row.tahun} ${num(row.hari, 1)} hari`).join(', ')}`">
          <div class="banner-charts__bars">
            <div v-for="row in rotation" :key="row.tahun" class="banner-charts__bar">
              <i class="is-warm" :class="row.tahun === latestRotation?.tahun && 'is-latest'"
                :style="{ height: `${barHeight(row.hari, rotationMax)}%` }"
                :title="`${row.tahun}: ${num(row.hari, 1)} hari`" />
            </div>
          </div>
          <div class="banner-charts__years is-columns">
            <small v-for="row in rotation" :key="row.tahun">{{ row.tahun }}</small>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.banner-charts {
  display: grid;
  width: 100%;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.7rem;
}

@media (min-width: 1200px) {
  .banner-charts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.banner-charts__card {
  min-width: 0;
  border-radius: 14px;
  background: rgb(255 255 255 / 94%);
  padding: 2rem;
  margin: 2rem;
  box-shadow:
    0 14px 32px rgb(16 32 8 / 18%),
    0 0 0 1px rgb(255 255 255 / 70%);
  backdrop-filter: blur(10px);
}

.banner-charts__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.banner-charts__head h3 {
  margin: 0;
  color: #1f2a18;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.01em;
}

.banner-charts__head span {
  color: #638840;
  font-size: 0.68rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.banner-charts__empty {
  display: flex;
  height: 4.6rem;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: #6e7866;
  font-size: 0.68rem;
}

.banner-charts__plot {
  min-height: 4.6rem;
}

.banner-charts__bars {
  display: flex;
  height: 3.15rem;
  align-items: flex-end;
  gap: 0.28rem;
}

.banner-charts__bar {
  display: flex;
  height: 100%;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
}

.banner-charts__bar i {
  display: block;
  width: 100%;
  max-width: 1.35rem;
  border-radius: 3px 3px 0 0;
  background: #c5d4b4;
}

.banner-charts__bar i.is-latest {
  background: #638840;
}

.banner-charts__bar i.is-warm {
  background: #ead3bf;
}

.banner-charts__bar i.is-warm.is-latest {
  background: #d87633;
}

.banner-charts__years small {
  margin-top: 0.18rem;
  color: #6e7866;
  font-size: 0.58rem;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.banner-charts__line-wrap {
  position: relative;
  height: 2.7rem;
}

.banner-charts__line {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.banner-charts__dot {
  position: absolute;
  width: 6px;
  height: 6px;
  border: 1px solid #fff;
  border-radius: 999px;
  background: #638840;
  transform: translate(-50%, -50%);
}

.banner-charts__line polyline {
  fill: none;
  stroke-width: 1.6;
  vector-effect: non-scaling-stroke;
}

.banner-charts__line .is-actual {
  stroke: #638840;
}

.banner-charts__line .is-budget {
  stroke: #d87633;
  stroke-dasharray: 3 2;
}

.banner-charts__years {
  display: flex;
  justify-content: space-between;
}

.banner-charts__years.is-columns {
  justify-content: flex-start;
  gap: 0.28rem;
}

.banner-charts__years.is-columns small {
  flex: 1;
  text-align: center;
}

.banner-charts__legend {
  display: flex;
  gap: 0.65rem;
  margin: 0.28rem 0 0;
  color: #6e7866;
  font-size: 0.58rem;
}

.banner-charts__legend span {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.banner-charts__legend i {
  width: 0.7rem;
  height: 2px;
  background: #638840;
}

.banner-charts__legend i.is-budget {
  background: repeating-linear-gradient(90deg, #d87633 0 3px, transparent 3px 5px);
}

.banner-charts__stack {
  display: flex;
  height: 0.55rem;
  overflow: hidden;
  border-radius: 999px;
  background: #e4e8de;
}

.banner-charts__slope {
  display: flex;
  flex-wrap: wrap;
  gap: 0.22rem 0.55rem;
  margin: 0.45rem 0 0;
  padding: 0;
  list-style: none;
}

.banner-charts__slope li {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 0.22rem;
  color: #55604c;
  font-size: 0.58rem;
}

.banner-charts__slope i {
  width: 0.42rem;
  height: 0.42rem;
  flex: none;
  border-radius: 2px;
}

.banner-charts__slope strong {
  color: #1f2a18;
  font-variant-numeric: tabular-nums;
}

</style>

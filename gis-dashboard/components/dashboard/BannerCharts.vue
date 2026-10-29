<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  statusTanamSummary,
  type StatusTanamSummary,
} from "~/utils/statusTanam";

type ProductionRow = {
  tahun: number;
  bulan: number | null;
  ton: number;
};

type YieldRow = {
  tahun: number;
  bulan: number | null;
  ton_ha: number;
};

type RotationRow = {
  tahun: number;
  bulan: number | null;
  hari: number;
};

type StatusSlice = {
  key: string;
  label: string;
  ha: number;
  pct: number;
};

type Point = { x: number; y: number };

type ChartTip = {
  chart: string;
  id: string;
  title: string;
  value: string;
  x: number;
  y: number;
};

const MONTHS = [
  "JAN",
  "FEB",
  "MAR",
  "APR",
  "MEI",
  "JUN",
  "JUL",
  "AGU",
  "SEP",
  "OKT",
  "NOV",
  "DES",
];

const GREEN_BAR = { front: "#3cba4c", side: "#2b9338", top: "#8ee08a" };
const BAR_COLORS = [
  { front: "#f0a31c", side: "#c98412", top: "#ffd06a" },
  { front: "#f6c516", side: "#d4a40c", top: "#ffe38a" },
  GREEN_BAR,
];

const loading = ref(true);
const production = ref<ProductionRow[]>([]);
const yieldSeries = ref<YieldRow[]>([]);
const rotation = ref<RotationRow[]>([]);
const statusSlices = ref<StatusSlice[]>([]);
const statusSummary = ref<StatusTanamSummary | null>(null);
const statusPeriod = ref<{ tahun: number | null; bulan: number | null }>({
  tahun: null,
  bulan: null,
});
const productionAccess = ref(true);
const yieldAccess = ref(true);
const statusAccess = ref(true);
const rotationAccess = ref(true);
const hoverTip = ref<ChartTip | null>(null);
const pinnedTip = ref<ChartTip | null>(null);

function num(value: number, digits = 1) {
  return value.toLocaleString("id-ID", {
    minimumFractionDigits: value >= 100 ? 0 : digits,
    maximumFractionDigits: value >= 100 ? 0 : digits,
  });
}

function yearOf(value: unknown) {
  const year = Number(value);
  return Number.isFinite(year) ? year : null;
}

function monthOf(value: unknown) {
  const month = Number(value);
  return Number.isInteger(month) && month >= 1 && month <= 12 ? month : null;
}

function periodLabel(row: { tahun: number; bulan: number | null }) {
  if (row.bulan) return MONTHS[row.bulan - 1] ?? String(row.bulan);
  return String(row.tahun);
}

function periodTitle(row: { tahun: number; bulan: number | null }) {
  if (row.bulan) return `${periodLabel(row)} ${row.tahun}`;
  return String(row.tahun);
}

function enterTip(tip: ChartTip) {
  hoverTip.value = tip;
}

function leaveChart(chart: string) {
  if (hoverTip.value?.chart === chart) hoverTip.value = null;
}

function toggleTip(tip: ChartTip) {
  pinnedTip.value = pinnedTip.value?.id === tip.id ? null : tip;
}

function clearPin(chart: string, event?: MouseEvent) {
  const target = event?.target;
  if (target instanceof Element && target.closest(".kpi__hit")) return;
  if (pinnedTip.value?.chart === chart) pinnedTip.value = null;
}

function chartTip(chart: string) {
  if (hoverTip.value?.chart === chart) return hoverTip.value;
  if (pinnedTip.value?.chart === chart) return pinnedTip.value;
  return null;
}

function tipOn(id: string) {
  return hoverTip.value?.id === id || pinnedTip.value?.id === id;
}

function tipFrame(tip: ChartTip | null, viewWidth: number, viewHeight: number) {
  if (!tip) return null;
  const width = Math.min(
    viewWidth - 8,
    Math.max(88, Math.max(tip.title.length, tip.value.length) * 6.5 + 18),
  );
  const height = 36;
  const x = Math.max(4, Math.min(viewWidth - width - 4, tip.x - width / 2));
  const above = tip.y - height - 10;
  const y = above >= 2 ? above : Math.min(viewHeight - height - 2, tip.y + 12);
  return { x, y, width, height, title: tip.title, value: tip.value };
}

function periodKey(row: { tahun: number; bulan: number | null }) {
  return `${row.tahun}-${row.bulan ?? 0}`;
}

function summary(values: number[], subject: string) {
  const latest = values.at(-1);
  const previous = values.at(-2);
  if (latest == null || previous == null) {
    return "Ringkasan periode ini disusun dari data transaksi perkebunan yang sudah tercatat.";
  }
  const rising = latest >= previous;
  return rising
    ? `TPA & SGA mengalami kenaikan ${subject} pada periode terakhir, dan tren beberapa bulan ke depan menunjukkan peningkatan.`
    : `TPA & SGA mencatat penurunan ${subject} pada periode terakhir. Tren beberapa bulan ke depan perlu dipantau agar produksi TBS tetap terjaga.`;
}

function plotPoints(
  values: number[],
  width: number,
  height: number,
  padX: number,
  padY: number,
): Point[] {
  if (!values.length) return [];
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = Math.max(max - min, Math.abs(max) * 0.35, 0.01);
  const low = min - span * 0.2;
  const high = max + span * 0.35;
  return values.map((value, index) => ({
    x:
      values.length === 1
        ? width / 2
        : padX + (index / (values.length - 1)) * (width - padX * 2),
    y: padY + (1 - (value - low) / (high - low)) * (height - padY * 2),
  }));
}

function smoothPath(points: Point[]) {
  const start = points[0];
  if (!start) return "";
  if (points.length === 1)
    return `M ${start.x.toFixed(1)} ${start.y.toFixed(1)}`;
  let path = `M ${start.x.toFixed(1)} ${start.y.toFixed(1)}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    if (!current || !next) continue;
    const prev = points[index - 1] ?? current;
    const after = points[index + 2] ?? next;
    const c1x = current.x + (next.x - prev.x) / 6;
    const c1y = current.y + (next.y - prev.y) / 6;
    const c2x = next.x - (after.x - current.x) / 6;
    const c2y = next.y - (after.y - current.y) / 6;
    path += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${next.x.toFixed(1)} ${next.y.toFixed(1)}`;
  }
  return path;
}

function areaPath(points: Point[], baseline: number) {
  const line = smoothPath(points);
  const first = points[0];
  const last = points[points.length - 1];
  if (!line || !first || !last || points.length < 2) return "";
  return `${line} L ${last.x.toFixed(1)} ${baseline} L ${first.x.toFixed(1)} ${baseline} Z`;
}

onMounted(async () => {
  try {
    const { $api } = useNuxtApp();
    const base = useRuntimeConfig().public.apiBaseUrlPython as string;
    const payload = await $api<Record<string, any>>(
      `${base}/v1/dashboard/laporan`,
    );
    const produksi = payload.produksi_tbs ?? {};
    const yieldReport = payload.yield ?? {};
    const statusReport = payload.status_tanam ?? {};
    const rotasi = payload.rotasi ?? {};

    productionAccess.value = produksi.akses !== false;
    yieldAccess.value = yieldReport.akses !== false;
    statusAccess.value = statusReport.akses !== false;
    rotationAccess.value = rotasi.akses !== false;

    production.value = ((produksi.periode ?? []) as Array<Record<string, any>>)
      .map((row) => {
        const tahun = yearOf(row.tahun);
        if (tahun == null) return null;
        return { tahun, bulan: monthOf(row.bulan), ton: Number(row.ton ?? 0) };
      })
      .filter((row): row is ProductionRow => row != null);

    yieldSeries.value = (
      (yieldReport.periode ?? []) as Array<Record<string, any>>
    )
      .map((row) => {
        const tahun = yearOf(row.tahun);
        const tonHa = Number(row.ton_ha);
        if (tahun == null || !Number.isFinite(tonHa)) return null;
        return { tahun, bulan: monthOf(row.bulan), ton_ha: tonHa };
      })
      .filter((row): row is YieldRow => row != null);

    statusSummary.value = statusTanamSummary(statusReport.per_status);
    statusSlices.value = statusSummary.value?.slices ?? [];
    statusPeriod.value = {
      tahun: yearOf(statusReport.tahun),
      bulan: monthOf(statusReport.bulan),
    };

    rotation.value = ((rotasi.periode ?? []) as Array<Record<string, any>>)
      .map((row) => {
        const tahun = yearOf(row.tahun);
        if (tahun == null) return null;
        return {
          tahun,
          bulan: monthOf(row.bulan),
          hari: Number(row.avg_pusingan_hari ?? 0),
        };
      })
      .filter((row): row is RotationRow => row != null);
  } finally {
    loading.value = false;
  }
});

const latestProduction = computed(() => production.value.at(-1) ?? null);
const latestYield = computed(() => yieldSeries.value.at(-1) ?? null);
const latestRotation = computed(() => rotation.value.at(-1) ?? null);
const reportYear = computed(
  () =>
    latestProduction.value?.tahun ??
    latestYield.value?.tahun ??
    latestRotation.value?.tahun ??
    new Date().getFullYear(),
);

const productionBars = computed(() => {
  const rows = production.value.slice(-3);
  if (!rows.length) return [];
  const max = Math.max(...rows.map((row) => row.ton), 1);
  const colors = BAR_COLORS.slice(-rows.length);
  const barWidth = 50;
  const gap = rows.length === 1 ? 0 : 34;
  const depthX = 16;
  const depthY = 11;
  const base = 126;
  const maxHeight = 86;
  const total = rows.length * barWidth + (rows.length - 1) * gap;
  const origin = (320 - total - depthX) / 2;

  return rows.map((row, index) => {
    const height = Math.max((row.ton / max) * maxHeight, row.ton > 0 ? 20 : 8);
    const x = origin + index * (barWidth + gap);
    const y = base - height;
    return {
      row,
      color: colors[index] ?? GREEN_BAR,
      x,
      y,
      base,
      barWidth,
      front: `${x},${y} ${x + barWidth},${y} ${x + barWidth},${base} ${x},${base}`,
      top: `${x},${y} ${x + depthX},${y - depthY} ${x + barWidth + depthX},${y - depthY} ${x + barWidth},${y}`,
      side: `${x + barWidth},${y} ${x + barWidth + depthX},${y - depthY} ${x + barWidth + depthX},${base - depthY} ${x + barWidth},${base}`,
      labelX: x + barWidth / 2 + depthX * 0.25,
      tip: {
        chart: "produksi",
        id: `produksi-${periodKey(row)}`,
        title: periodTitle(row),
        value: `${num(row.ton)} TON`,
        x: x + barWidth / 2 + depthX * 0.35,
        y: y - depthY,
      } satisfies ChartTip,
    };
  });
});

const productionArrow = computed(() => {
  const bars = productionBars.value;
  const first = bars[0];
  const last = bars[bars.length - 1];
  if (!first || !last || bars.length < 2) return "";
  if (last.row.ton < first.row.ton) return "";
  const x1 = first.x + 6;
  const y1 = first.base - 18;
  const x2 = last.x + last.barWidth + 22;
  const y2 = last.y - 24;
  return `M ${x1} ${y1} C ${x1 + 54} ${y1 - 6}, ${x2 - 40} ${y2 + 16}, ${x2} ${y2}`;
});

const yieldPoints = computed(() =>
  plotPoints(
    yieldSeries.value.map((row) => row.ton_ha),
    300,
    132,
    18,
    16,
  ),
);
const yieldLine = computed(() => smoothPath(yieldPoints.value));
const yieldArea = computed(() => areaPath(yieldPoints.value, 126));
const yieldMarkers = computed(() =>
  yieldSeries.value.flatMap((row, index) => {
    const point = yieldPoints.value[index];
    if (!point) return [];
    return [
      {
        ...point,
        tip: {
          chart: "yield",
          id: `yield-${periodKey(row)}`,
          title: periodTitle(row),
          value: `${num(row.ton_ha, 2)} TON/HA`,
          x: point.x,
          y: point.y,
        } satisfies ChartTip,
      },
    ];
  }),
);

const rotationPoints = computed(() =>
  plotPoints(
    rotation.value.map((row) => row.hari),
    300,
    132,
    18,
    18,
  ),
);
const rotationLine = computed(() => smoothPath(rotationPoints.value));
const rotationMarkers = computed(() =>
  rotation.value.flatMap((row, index) => {
    const point = rotationPoints.value[index];
    if (!point) return [];
    return [
      {
        ...point,
        tip: {
          chart: "rotasi",
          id: `rotasi-${periodKey(row)}`,
          title: periodTitle(row),
          value: `${num(row.hari, 1)} HARI`,
          x: point.x,
          y: point.y,
        } satisfies ChartTip,
      },
    ];
  }),
);

/** Batang 3D (gaya kartu Produksi TBS) untuk LC, TBM, TM: tinggi ~ luas tanam, label ha & % di atas batang. */
const STATUS_COLORS: Record<
  string,
  { front: string; side: string; top: string }
> = {
  LC: BAR_COLORS[0]!,
  TBM: BAR_COLORS[1]!,
  TM: GREEN_BAR,
};
const statusBars = computed(() => {
  const rows = statusSlices.value;
  if (!rows.length) return [];
  const max = Math.max(...rows.map((row) => row.ha), 1);
  const barWidth = 46;
  const gap = 38;
  const depthX = 14;
  const depthY = 10;
  const base = 124;
  const maxHeight = 64;
  const total = rows.length * barWidth + (rows.length - 1) * gap;
  const origin = (300 - total - depthX) / 2;
  return rows.map((row, index) => {
    const height = row.ha > 0 ? Math.max((row.ha / max) * maxHeight, 4) : 1.5;
    const x = origin + index * (barWidth + gap);
    const y = base - height;
    const cx = x + barWidth / 2 + depthX * 0.25;
    return {
      row,
      color: STATUS_COLORS[row.key] ?? GREEN_BAR,
      x,
      y,
      base,
      barWidth,
      cx,
      front: `${x},${y} ${x + barWidth},${y} ${x + barWidth},${base} ${x},${base}`,
      top: `${x},${y} ${x + depthX},${y - depthY} ${x + barWidth + depthX},${y - depthY} ${x + barWidth},${y}`,
      side: `${x + barWidth},${y} ${x + barWidth + depthX},${y - depthY} ${x + barWidth + depthX},${base - depthY} ${x + barWidth},${base}`,
      pctText: `${num(row.pct, 1)}%`,
      haText: `${num(row.ha, 0)} ha`,
      tip: {
        chart: "status",
        id: `status-${row.key}`,
        title: `${row.key} · ${row.label}`,
        value: `${num(row.pct, 2)}% · ${num(row.ha, 2)} HA`,
        x: cx,
        y: y - depthY,
      } satisfies ChartTip,
    };
  });
});

const productionNote = computed(() =>
  summary(
    production.value.map((row) => row.ton),
    "produksi",
  ),
);
const yieldNote = computed(() =>
  summary(
    yieldSeries.value.map((row) => row.ton_ha),
    "yield",
  ),
);
const statusYear = computed(() => statusPeriod.value.tahun ?? reportYear.value);
const statusNote = computed(() => {
  const s = statusSummary.value;
  if (!s) return "Belum ada sebaran status tanam pada periode ini.";
  const part = (key: string) => {
    const item = s.slices.find((x) => x.key === key);
    return `${key} ${num(item?.pct ?? 0, 1)}% (${num(item?.ha ?? 0, 0)} ha)`;
  };
  const bulan = statusPeriod.value.bulan
    ? `${MONTHS[statusPeriod.value.bulan - 1]} `
    : "";
  const lain =
    s.lainnya.blok > 0
      ? ` ${num(s.lainnya.blok, 0)} blok tanpa status tidak dihitung.`
      : "";
  return `Area TM mencakup ${num(s.tmPct, 1)}% dari ${num(s.total, 0)} ha luas tanam (LC + TBM + TM) periode ${bulan}${statusYear.value}: ${part("LC")}, ${part("TBM")}, ${part("TM")}.${lain}`;
});
const rotationNote = computed(() =>
  summary(
    rotation.value.map((row) => row.hari),
    "rotasi panen",
  ),
);
</script>

<template>
  <div class="kpi-grid">
    <article class="kpi">
      <h2>Produksi TBS</h2>
      <div class="kpi__chart" @mouseleave="leaveChart('produksi')" @click="clearPin('produksi', $event)">
        <p v-if="latestProduction" class="kpi__metric is-left is-green">
          {{ num(latestProduction.ton) }} TON
        </p>
        <p v-if="loading" class="kpi__empty">Memuat…</p>
        <p v-else-if="!production.length" class="kpi__empty">
          {{ productionAccess ? "Belum ada data" : "Tidak ada akses" }}
        </p>
        <svg v-else viewBox="0 0 320 168" class="kpi__svg" role="img"
          :aria-label="`Produksi TBS: ${productionBars.map((bar) => `${periodLabel(bar.row)} ${num(bar.row.ton)} ton`).join(', ')}`">
          <defs>
            <marker id="kpi-prod-arrow" markerWidth="7" markerHeight="7" refX="5.5" refY="3.5" orient="auto">
              <path d="M0 0 L7 3.5 L0 7 Z" fill="#1c9a38" />
            </marker>
          </defs>
          <path v-if="productionArrow" :d="productionArrow" class="kpi__arrow" marker-end="url(#kpi-prod-arrow)" />
          <g v-for="bar in productionBars" :key="periodKey(bar.row)" class="kpi__series"
            :class="{ 'is-hot': tipOn(bar.tip.id) }">
            <polygon :points="bar.side" :fill="bar.color.side" />
            <polygon :points="bar.front" :fill="bar.color.front" />
            <polygon :points="bar.top" :fill="bar.color.top" />
            <text :x="bar.labelX" y="156" text-anchor="middle" class="kpi__axis">
              {{ periodLabel(bar.row) }}
            </text>
            <rect class="kpi__hit" :x="bar.x - 2" :y="bar.y - 18" :width="bar.barWidth + 20"
              :height="bar.base - bar.y + 48" @pointerenter="enterTip(bar.tip)" @click.stop="toggleTip(bar.tip)" />
          </g>
          <template v-for="frame in [tipFrame(chartTip('produksi'), 320, 168)]" :key="frame?.title ?? 'produksi'">
            <g v-if="frame" class="kpi__tip">
              <rect :x="frame.x" :y="frame.y" :width="frame.width" :height="frame.height" rx="7" />
              <text :x="frame.x + frame.width / 2" :y="frame.y + 14" text-anchor="middle" class="kpi__tip-label">
                {{ frame.title }}
              </text>
              <text :x="frame.x + frame.width / 2" :y="frame.y + 28" text-anchor="middle" class="kpi__tip-value">
                {{ frame.value }}
              </text>
            </g>
          </template>
        </svg>
      </div>
      <div class="kpi__foot">
        <h3>Ringkasan Produksi {{ reportYear }}</h3>
        <p>
          {{
            productionAccess
              ? (production.length ? productionNote : "Data produksi TBS belum tersedia.")
              : "Tidak ada akses untuk data produksi TBS."
          }}
        </p>
      </div>
    </article>

    <article class="kpi">
      <h2>Yield</h2>
      <div class="kpi__chart" @mouseleave="leaveChart('yield')" @click="clearPin('yield', $event)">
        <p v-if="latestYield" class="kpi__metric is-right is-red">
          {{ num(latestYield.ton_ha, 2) }} TON/HA
        </p>
        <p v-if="loading" class="kpi__empty">Memuat…</p>
        <p v-else-if="!yieldSeries.length" class="kpi__empty">
          {{ yieldAccess ? "Belum ada data" : "Tidak ada akses" }}
        </p>
        <svg v-else viewBox="0 0 300 140" class="kpi__svg" role="img"
          :aria-label="`Yield: ${yieldSeries.map((row) => `${periodLabel(row)} ${num(row.ton_ha, 2)} ton per hektare`).join(', ')}`">
          <g class="kpi__grid">
            <line v-for="index in 7" :key="index" :x1="12 + (index - 1) * 44" y1="8" :x2="12 + (index - 1) * 44"
              y2="126" />
          </g>
          <path :d="yieldArea" class="kpi__area" />
          <path :d="yieldLine" class="kpi__line" />
          <g v-for="marker in yieldMarkers" :key="marker.tip.id">
            <circle class="kpi__node" :cx="marker.x" :cy="marker.y" :r="tipOn(marker.tip.id) ? 5.2 : 3.4" />
            <circle class="kpi__hit" :cx="marker.x" :cy="marker.y" r="14" @pointerenter="enterTip(marker.tip)"
              @click.stop="toggleTip(marker.tip)" />
          </g>
          <template v-for="frame in [tipFrame(chartTip('yield'), 300, 140)]" :key="frame?.title ?? 'yield'">
            <g v-if="frame" class="kpi__tip">
              <rect :x="frame.x" :y="frame.y" :width="frame.width" :height="frame.height" rx="7" />
              <text :x="frame.x + frame.width / 2" :y="frame.y + 14" text-anchor="middle" class="kpi__tip-label">
                {{ frame.title }}
              </text>
              <text :x="frame.x + frame.width / 2" :y="frame.y + 28" text-anchor="middle" class="kpi__tip-value">
                {{ frame.value }}
              </text>
            </g>
          </template>
        </svg>
      </div>
      <div class="kpi__foot">
        <h3>Ringkasan Produksi {{ reportYear }}</h3>
        <p>
          {{
            yieldAccess
              ? (yieldSeries.length ? yieldNote : "Data yield belum tersedia.")
              : "Tidak ada akses untuk data yield."
          }}
        </p>
      </div>
    </article>

    <article class="kpi">
      <h2>Status Tanam</h2>
      <div class="kpi__chart" @mouseleave="leaveChart('status')" @click="clearPin('status', $event)">
        <p v-if="statusSummary" class="kpi__metric is-right is-ink">
          {{ Math.round(statusSummary.tmPct) }} % AREA TM
        </p>
        <p v-if="loading" class="kpi__empty">Memuat…</p>
        <p v-else-if="!statusSlices.length" class="kpi__empty">
          {{ statusAccess ? "Belum ada data" : "Tidak ada akses" }}
        </p>
        <svg v-else viewBox="0 0 300 148" class="kpi__svg" role="img"
          :aria-label="`Status tanam: ${statusSlices.map((item) => `${item.key} ${Math.round(item.pct)} persen`).join(', ')}`">
          <g v-for="bar in statusBars" :key="bar.row.key" class="kpi__series" :class="{ 'is-hot': tipOn(bar.tip.id) }">
            <polygon :points="bar.side" :fill="bar.color.side" />
            <polygon :points="bar.front" :fill="bar.color.front" />
            <polygon :points="bar.top" :fill="bar.color.top" />
            <text :x="bar.cx" :y="bar.y - 24" text-anchor="middle" class="kpi__bar-pct">
              {{ bar.pctText }}
            </text>
            <text :x="bar.cx" :y="bar.y - 13" text-anchor="middle" class="kpi__axis">
              {{ bar.haText }}
            </text>
            <text :x="bar.cx" y="140" text-anchor="middle" class="kpi__axis kpi__bar-key">
              {{ bar.row.key }}
            </text>
            <rect class="kpi__hit" :x="bar.x - 4" :y="bar.y - 34" :width="bar.barWidth + 22"
              :height="bar.base - bar.y + 52" @pointerenter="enterTip(bar.tip)" @click.stop="toggleTip(bar.tip)" />
          </g>
          <template v-for="frame in [tipFrame(chartTip('status'), 300, 148)]" :key="frame?.title ?? 'status'">
            <g v-if="frame" class="kpi__tip">
              <rect :x="frame.x" :y="frame.y" :width="frame.width" :height="frame.height" rx="7" />
              <text :x="frame.x + frame.width / 2" :y="frame.y + 14" text-anchor="middle" class="kpi__tip-label">
                {{ frame.title }}
              </text>
              <text :x="frame.x + frame.width / 2" :y="frame.y + 28" text-anchor="middle" class="kpi__tip-value">
                {{ frame.value }}
              </text>
            </g>
          </template>
        </svg>
      </div>
      <div class="kpi__foot">
        <h3>Ringkasan LC, TBM &amp; TM {{ statusYear }}</h3>
        <p>
          {{
            statusAccess
              ? statusNote
              : "Tidak ada akses untuk data status tanam."
          }}
        </p>
      </div>
    </article>

    <article class="kpi">
      <h2>Rotasi</h2>
      <div class="kpi__chart" @mouseleave="leaveChart('rotasi')" @click="clearPin('rotasi', $event)">
        <p v-if="latestRotation" class="kpi__metric is-right is-red">
          SD BULAN INI
        </p>
        <p v-if="loading" class="kpi__empty">Memuat…</p>
        <p v-else-if="!rotation.length" class="kpi__empty">
          {{ rotationAccess ? "Belum ada data" : "Tidak ada akses" }}
        </p>
        <svg v-else viewBox="0 0 300 140" class="kpi__svg" role="img"
          :aria-label="`Rotasi: ${rotation.map((row) => `${periodLabel(row)} ${num(row.hari, 1)} hari`).join(', ')}`">
          <g class="kpi__grid">
            <line v-for="index in 4" :key="`h-${index}`" x1="12" :y1="14 + (index - 1) * 32" x2="288"
              :y2="14 + (index - 1) * 32" />
            <line v-for="index in 7" :key="`v-${index}`" :x1="12 + (index - 1) * 46" y1="14" :x2="12 + (index - 1) * 46"
              y2="126" />
          </g>
          <path :d="rotationLine" class="kpi__line" />
          <g v-for="marker in rotationMarkers" :key="marker.tip.id">
            <circle class="kpi__node" :cx="marker.x" :cy="marker.y" :r="tipOn(marker.tip.id) ? 5.2 : 3.4" />
            <circle class="kpi__hit" :cx="marker.x" :cy="marker.y" r="14" @pointerenter="enterTip(marker.tip)"
              @click.stop="toggleTip(marker.tip)" />
          </g>
          <template v-for="frame in [tipFrame(chartTip('rotasi'), 300, 140)]" :key="frame?.title ?? 'rotasi'">
            <g v-if="frame" class="kpi__tip">
              <rect :x="frame.x" :y="frame.y" :width="frame.width" :height="frame.height" rx="7" />
              <text :x="frame.x + frame.width / 2" :y="frame.y + 14" text-anchor="middle" class="kpi__tip-label">
                {{ frame.title }}
              </text>
              <text :x="frame.x + frame.width / 2" :y="frame.y + 28" text-anchor="middle" class="kpi__tip-value">
                {{ frame.value }}
              </text>
            </g>
          </template>
        </svg>
      </div>
      <div class="kpi__foot">
        <h3>Trend Rotasi SD.BI {{ reportYear }}</h3>
        <p>
          {{
            rotationAccess
              ? (rotation.length ? rotationNote : "Data rotasi belum tersedia.")
              : "Tidak ada akses untuk data rotasi."
          }}
        </p>
      </div>
    </article>
  </div>
</template>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.9rem;
}

@media (min-width: 760px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .kpi-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.6rem;
  }

  .kpi {
    border-radius: 16px;
    padding: 0.42rem 0.55rem 0.38rem;
  }

  .kpi h2 {
    font-size: 0.9rem;
  }

  .kpi__chart {
    min-height: 5.7rem;
    margin-top: 0.1rem;
  }

  .kpi__svg {
    height: 5.7rem;
  }

  .kpi__empty {
    height: 5.2rem;
  }

  .kpi__foot {
    padding-top: 0.15rem;
  }

  .kpi__foot p {
    margin-top: 0.12rem;
  }
}

.kpi {
  display: flex;
  min-width: 0;
  min-height: 100%;
  flex-direction: column;
  border: 1px solid rgb(255 255 255 / 55%);
  border-radius: 22px;
  background: rgba(205, 204, 204, 0.313);
  padding: 0.85rem 0.95rem 0.8rem;
  box-shadow: 0 10px 30px rgb(31 42 24 / 12%);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  color: #1f2a18;
}

.kpi h2 {
  margin: 0;
  color: #111;
  font-size: clamp(1rem, 1.25vw, 1.22rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
  text-align: center;
  text-transform: uppercase;
}

.kpi__chart {
  position: relative;
  display: flex;
  min-height: 9.4rem;
  flex: 1;
  align-items: center;
  margin-top: 0.35rem;
}

.kpi__metric {
  position: absolute;
  z-index: 1;
  top: 0;
  margin: 0;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  line-height: 1.2;
}

.kpi__metric.is-left {
  left: 0.1rem;
}

.kpi__metric.is-right {
  right: 0.1rem;
  max-width: 58%;
  text-align: right;
}

.kpi__metric.is-green {
  color: #1c9a38;
}

.kpi__metric.is-red {
  color: #e23b3b;
}

.kpi__metric.is-ink {
  color: #243024;
}

.kpi__empty {
  display: flex;
  width: 100%;
  height: 8.2rem;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: #8b9086;
  font-size: 0.78rem;
}

.kpi__svg {
  display: block;
  width: 100%;
  height: 9.2rem;
  overflow: visible;
}

.kpi__hit {
  fill: transparent;
  cursor: pointer;
  pointer-events: all;
}

.kpi__series.is-hot polygon {
  stroke: #102416;
  stroke-width: 0.8;
}

.kpi__tip {
  pointer-events: none;
}

.kpi__tip rect {
  fill: #172117;
  stroke: rgb(255 255 255 / 72%);
  stroke-width: 1;
  filter: drop-shadow(0 2px 3px rgb(0 0 0 / 28%));
}

.kpi__tip-label {
  fill: #d7e4d4;
  font-size: 9px;
  font-weight: 700;
}

.kpi__tip-value {
  fill: #fff;
  font-size: 11px;
  font-weight: 800;
}

.kpi__arrow {
  fill: none;
  stroke: #1c9a38;
  stroke-width: 7;
  stroke-linecap: round;
  pointer-events: none;
}

.kpi__axis {
  fill: #6d6d6d;
  font-size: 11px;
  font-weight: 700;
}

.kpi__grid line {
  stroke: #ececec;
  stroke-width: 1;
  pointer-events: none;
}

.kpi__area {
  fill: rgb(226 59 59 / 16%);
  pointer-events: none;
}

.kpi__line {
  fill: none;
  stroke: #e23b3b;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
  pointer-events: none;
}

.kpi__axis-line {
  stroke: #1a1a1a;
  stroke-width: 1.7;
  stroke-linecap: round;
}

.kpi__bar-pct {
  font-size: 11px;
  font-weight: 800;
  fill: #1a1a1a;
}

.kpi__bar-key {
  font-weight: 800;
}

.kpi__dot {
  fill: #161616;
  pointer-events: none;
}

.kpi__dot.is-hot {
  fill: #1c9a38;
}

.kpi__node {
  fill: #e23b3b;
  stroke: #fff;
  stroke-width: 1;
  pointer-events: none;
}

.kpi__foot {
  margin-top: auto;
  padding-top: 0.35rem;
  text-align: center;
}

.kpi__foot h3 {
  margin: 0;
  color: #161616;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  line-height: 1.25;
  text-transform: uppercase;
}

.kpi__foot p {
  margin: 0.28rem 0 0;
  color: #3f3f3f;
  font-size: 0.64rem;
  font-weight: 500;
  line-height: 1.35;
}
</style>

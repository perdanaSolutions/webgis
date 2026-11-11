<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import Header from "~/components/Header.vue";
import {
  useMonitoringUserStore,
  type MonitoringStatus,
  type MonitoringUserItem,
} from "~/stores/monitoringUserStore";

defineOptions({
  name: "MonitoringUserPage",
});

const REFRESH_MS = 30_000;

const STATUS_OPTIONS: { value: MonitoringStatus | ""; label: string }[] = [
  { value: "", label: "Semua status" },
  { value: "online", label: "Online" },
  { value: "offline", label: "Offline" },
];

const store = useMonitoringUserStore();

const search = ref("");
const statusFilter = ref<MonitoringStatus | "">("");
const autoRefresh = ref(true);
let timer: ReturnType<typeof setInterval> | null = null;

const canGoPrev = computed(() => store.page > 1);
const canGoNext = computed(() => store.page < store.totalPage);

const sumberLabel = computed(() =>
  store.sumber === "redis"
    ? "Sumber: sesi login (Redis)"
    : store.sumber === "log_aktivitas"
      ? "Sumber: perkiraan dari log login/logout (Redis auth nonaktif)"
      : "",
);

const lastFetchedLabel = computed(() =>
  store.lastFetchedAt
    ? store.lastFetchedAt.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "-",
);

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

/** "5 menit lalu" supaya admin langsung melihat seberapa baru aktivitas terakhir. */
function formatRelative(value?: string | null) {
  if (!value) return "";
  const diff = Date.now() - new Date(value).getTime();
  if (Number.isNaN(diff) || diff < 0) return "";
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "baru saja";
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  return `${Math.floor(hours / 24)} hari lalu`;
}

function statusClass(item: MonitoringUserItem) {
  return item.status === "online"
    ? "bg-success-lighter text-success"
    : "bg-slate-muted text-slate-muted";
}

function accountNote(item: MonitoringUserItem) {
  if (item.terkunci) return "Akun terkunci";
  if (!item.akun_aktif) return "Akun nonaktif";
  return "";
}

async function load(nextPage?: number, silent = false) {
  try {
    await store.fetchUsers(
      {
        search: search.value.trim(),
        status: statusFilter.value,
        page: nextPage ?? store.page,
        limit: store.limit,
      },
      { silent },
    );
  } catch {
    // pesan error sudah ada di store.errorMessage
  }
}

function startTimer() {
  stopTimer();
  if (!autoRefresh.value) return;
  timer = setInterval(() => {
    if (document.visibilityState === "visible") void load(undefined, true);
  }, REFRESH_MS);
}

function stopTimer() {
  if (timer) clearInterval(timer);
  timer = null;
}

watch(autoRefresh, startTimer);

async function onSearch() {
  await load(1);
}

async function onReset() {
  search.value = "";
  statusFilter.value = "";
  await load(1);
}

async function goPrev() {
  if (canGoPrev.value) await load(store.page - 1);
}

async function goNext() {
  if (canGoNext.value) await load(store.page + 1);
}

async function onLimitChange(event: Event) {
  store.limit = Number((event.target as HTMLSelectElement).value) || 10;
  await load(1);
}

onMounted(async () => {
  await load(1);
  startTimer();
});

onBeforeUnmount(stopTimer);

async function gotoDashboard() {
  await navigateTo("/dashboard");
}
</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Monitoring User"
      brand-subtitle="Pantau user yang sedang login (online) dan yang tidak (offline)" />
    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <button type="button" aria-label="Back" @click="gotoDashboard"
            class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-light bg-surface text-icon shadow-sm transition-all duration-200 hover-border-navy hover-text-navy hover-bg-slate-light hover:scale-105 active:scale-95">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
              stroke="currentColor" class="h-4 w-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>

          <p class="font-semibold tracking-wide text-subtitle">Dashboard</p>
        </div>
      </div>

      <section class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3" aria-label="Ringkasan status user">
        <div class="rounded-2xl border border-default bg-surface p-5">
          <p class="text-label">Total User</p>
          <p class="text-20 font-bold" data-testid="sum-total">{{ store.summary.total_user.toLocaleString("id-ID") }}</p>
        </div>
        <div class="rounded-2xl border border-default bg-surface p-5">
          <p class="text-label">Online</p>
          <p class="text-20 font-bold text-success" data-testid="sum-online">
            {{ store.summary.online.toLocaleString("id-ID") }}
          </p>
        </div>
        <div class="rounded-2xl border border-default bg-surface p-5">
          <p class="text-label">Offline</p>
          <p class="text-20 font-bold" data-testid="sum-offline">{{ store.summary.offline.toLocaleString("id-ID") }}</p>
        </div>
      </section>

      <section class="rounded-2xl border border-default bg-surface p-5">
        <div class="mb-4 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 class="text-20 font-bold">Daftar User</h2>
            <p class="text-muted">
              Online = punya sesi login yang masih berlaku. Tiap akun non-Admin hanya punya satu sesi.
            </p>
            <p v-if="sumberLabel" class="text-12 text-muted">{{ sumberLabel }}</p>
          </div>
          <div class="flex items-center gap-3 text-12 text-muted">
            <label class="flex items-center gap-2">
              <input v-model="autoRefresh" type="checkbox" />
              Perbarui otomatis (30 dtk)
            </label>
            <span>Diperbarui: {{ lastFetchedLabel }}</span>
            <button class="rounded-lg border border-tan bg-cream px-3 py-1.5 font-semibold text-brand"
              :disabled="store.loading" @click="load(undefined)">
              Muat ulang
            </button>
          </div>
        </div>

        <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-6">
          <input v-model="search" type="text" placeholder="Cari username, nama, atau email..."
            class="h-11 rounded-xl border border-default px-4 outline-none placeholder-text-placeholder md:col-span-3"
            @keyup.enter="onSearch" />
          <select v-model="statusFilter"
            class="h-11 rounded-xl border border-default bg-surface px-3 outline-none md:col-span-1" @change="onSearch">
            <option v-for="option in STATUS_OPTIONS" :key="option.label" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <div class="flex items-center gap-2 md:col-span-2 md:justify-end">
            <button class="h-11 rounded-xl bg-brand px-6 font-semibold text-on-brand" @click="onSearch">Cari</button>
            <button class="h-11 rounded-xl border border-tan bg-cream px-6 font-semibold text-brand" @click="onReset">
              Reset
            </button>
          </div>
        </div>

        <p v-if="store.errorMessage" class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ store.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-4 py-3 font-bold">Status</th>
                <th class="px-4 py-3 font-bold">User</th>
                <th class="px-4 py-3 font-bold">Role</th>
                <th class="px-4 py-3 font-bold">Login Terakhir</th>
                <th class="px-4 py-3 font-bold">Logout Terakhir</th>
                <th class="px-4 py-3 font-bold">Aktivitas Terakhir</th>
                <th class="px-4 py-3 font-bold">IP</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="store.loading" class="border-t border-row">
                <td colspan="7" class="px-4 py-8 text-center text-muted">Memuat data user...</td>
              </tr>

              <tr v-for="item in store.items" :key="item.id" class="border-t border-row align-top">
                <td class="px-4 py-3">
                  <span class="inline-flex items-center gap-2 whitespace-nowrap rounded-full px-3 py-1 text-size-xs font-semibold"
                    :class="statusClass(item)">
                    <span class="h-2 w-2 rounded-full" :class="item.status === 'online' ? 'bg-success' : 'bg-slate-muted'"
                      aria-hidden="true"></span>
                    {{ item.status === "online" ? "Online" : "Offline" }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <p class="font-semibold">{{ item.nama_lengkap || "-" }}</p>
                  <p class="text-12 text-muted">@{{ item.username }} · {{ item.email }}</p>
                  <p v-if="accountNote(item)" class="text-12 text-error">{{ accountNote(item) }}</p>
                </td>
                <td class="px-4 py-3">{{ item.role.length ? item.role.join(", ") : "-" }}</td>
                <td class="px-4 py-3 whitespace-nowrap">{{ formatDateTime(item.login_terakhir) }}</td>
                <td class="px-4 py-3 whitespace-nowrap">{{ formatDateTime(item.logout_terakhir) }}</td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <p>{{ formatDateTime(item.aktivitas_terakhir) }}</p>
                  <p class="text-12 text-muted">{{ formatRelative(item.aktivitas_terakhir) }}</p>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">{{ item.ip_terakhir || "-" }}</td>
              </tr>

              <tr v-if="!store.loading && !store.hasItems" class="border-t border-row">
                <td colspan="7" class="px-4 py-8 text-center text-muted">Tidak ada user yang cocok.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-muted">
            Total: <span class="font-bold text-content">{{ store.totalData }}</span>
            user • Halaman
            <span class="font-bold text-content">{{ store.page }}</span>
            dari
            <span class="font-bold text-content">{{ store.totalPage }}</span>
          </p>

          <div class="flex items-center gap-2">
            <label class="text-muted">Limit</label>
            <select :value="store.limit" class="h-10 rounded-lg border border-tan bg-surface px-2"
              @change="onLimitChange">
              <option :value="5">5</option>
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>

            <button
              class="rounded-lg border border-tan bg-surface px-3 py-2 font-semibold text-brand disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canGoPrev" @click="goPrev">
              Prev
            </button>
            <button
              class="rounded-lg border border-tan bg-surface px-3 py-2 font-semibold text-brand disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canGoNext" @click="goNext">
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

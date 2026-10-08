<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import {
  useManagePengumumanStore,
  type PengumumanItem,
  type PengumumanPayload,
  type PengumumanStatus,
} from "~/stores/managePengumumanStore";

defineOptions({
  name: "PengumumanManagementPage",
});

const STATUS_OPTIONS: { value: PengumumanStatus | ""; label: string }[] = [
  { value: "", label: "Semua status" },
  { value: "aktif", label: "Aktif" },
  { value: "terjadwal", label: "Terjadwal" },
  { value: "kedaluwarsa", label: "Kedaluwarsa" },
  { value: "nonaktif", label: "Nonaktif" },
];

const managePengumumanStore = useManagePengumumanStore();

const search = ref("");
const statusFilter = ref<PengumumanStatus | "">("");
const showFormModal = ref(false);
const formError = ref("");
const showDeleteModal = ref(false);
const deleteError = ref("");
const formMode = ref<"create" | "edit">("create");
const selectedId = ref("");
const selectedJudul = ref("");

const form = reactive({
  judul: "",
  isi: "",
  is_active: true,
  tanggal_mulai: "",
  tanggal_berakhir: "",
});

const submitLoading = computed(
  () =>
    managePengumumanStore.loadingCreate || managePengumumanStore.loadingUpdate,
);

const pageTitle = computed(() =>
  formMode.value === "create" ? "Tambah Pengumuman" : "Edit Pengumuman",
);

const canGoPrev = computed(() => managePengumumanStore.page > 1);
const canGoNext = computed(
  () => managePengumumanStore.page < managePengumumanStore.totalPage,
);

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function toDatetimeLocal(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toIsoOrNull(value: string) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function formatDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatPeriod(item: PengumumanItem) {
  const mulai = formatDateTime(item.tanggal_mulai);
  const berakhir = formatDateTime(item.tanggal_berakhir);
  if (mulai && berakhir) return `${mulai} – ${berakhir}`;
  if (mulai) return `Mulai ${mulai}`;
  if (berakhir) return `Sampai ${berakhir}`;
  return "Tanpa batas waktu";
}

function statusLabel(status: string) {
  return (
    STATUS_OPTIONS.find((option) => option.value === status)?.label || status
  );
}

function statusClass(status: string) {
  if (status === "aktif") return "bg-success-lighter text-success";
  if (status === "terjadwal") return "bg-warning-light text-warning";
  if (status === "kedaluwarsa") return "bg-error-light text-error";
  return "bg-slate-muted text-slate-muted";
}

function resetForm() {
  form.judul = "";
  form.isi = "";
  form.is_active = true;
  form.tanggal_mulai = "";
  form.tanggal_berakhir = "";
  formError.value = "";
}

function fillForm(item: PengumumanItem) {
  form.judul = item.judul ?? "";
  form.isi = item.isi ?? "";
  form.is_active = Boolean(item.is_active);
  form.tanggal_mulai = toDatetimeLocal(item.tanggal_mulai);
  form.tanggal_berakhir = toDatetimeLocal(item.tanggal_berakhir);
  formError.value = "";
}

function buildPayload(): PengumumanPayload | null {
  const tanggalMulai = toIsoOrNull(form.tanggal_mulai);
  const tanggalBerakhir = toIsoOrNull(form.tanggal_berakhir);

  if (form.tanggal_mulai && !tanggalMulai) {
    formError.value = "Tanggal mulai tidak valid.";
    return null;
  }
  if (form.tanggal_berakhir && !tanggalBerakhir) {
    formError.value = "Tanggal berakhir tidak valid.";
    return null;
  }
  if (
    tanggalMulai &&
    tanggalBerakhir &&
    new Date(tanggalBerakhir) < new Date(tanggalMulai)
  ) {
    formError.value = "Tanggal berakhir tidak boleh lebih awal dari tanggal mulai.";
    return null;
  }

  return {
    judul: form.judul.trim(),
    isi: form.isi.trim(),
    is_active: form.is_active,
    tanggal_mulai: tanggalMulai,
    tanggal_berakhir: tanggalBerakhir,
  };
}

async function loadPengumuman(nextPage?: number) {
  await managePengumumanStore.fetchPengumuman({
    search: search.value.trim(),
    status: statusFilter.value,
    page: nextPage ?? managePengumumanStore.page,
    limit: managePengumumanStore.limit,
  });
}

async function onSearch() {
  await loadPengumuman(1);
}

async function onResetSearch() {
  search.value = "";
  statusFilter.value = "";
  await loadPengumuman(1);
}

function openCreateModal() {
  formMode.value = "create";
  selectedId.value = "";
  selectedJudul.value = "";
  resetForm();
  showFormModal.value = true;
}

async function openEditModal(item: PengumumanItem) {
  formMode.value = "edit";
  selectedId.value = item.id;
  selectedJudul.value = item.judul;
  fillForm(item);
  showFormModal.value = true;

  try {
    const detail = await managePengumumanStore.fetchPengumumanById(item.id);
    if (selectedId.value === item.id) fillForm(detail);
  } catch {
    managePengumumanStore.clearError();
  }
}

function closeFormModal() {
  showFormModal.value = false;
}

function openDeleteModal(item: PengumumanItem) {
  selectedId.value = item.id;
  selectedJudul.value = item.judul;
  deleteError.value = "";
  showDeleteModal.value = true;
}

function closeDeleteModal() {
  showDeleteModal.value = false;
}

async function submitForm() {
  const payload = buildPayload();
  if (!payload) return;
  formError.value = "";

  try {
    if (formMode.value === "create") {
      await managePengumumanStore.createPengumuman(payload);
    } else {
      await managePengumumanStore.updatePengumuman(selectedId.value, payload);
    }
  } catch {
    formError.value =
      managePengumumanStore.errorMessage || "Gagal menyimpan pengumuman.";
    return;
  }

  showFormModal.value = false;
  await Promise.all([
    loadPengumuman(formMode.value === "create" ? 1 : undefined),
    managePengumumanStore.fetchActivePengumuman(),
  ]);
}

async function confirmDelete() {
  deleteError.value = "";
  try {
    await managePengumumanStore.deletePengumuman(selectedId.value);
  } catch {
    deleteError.value =
      managePengumumanStore.errorMessage || "Gagal menghapus pengumuman.";
    return;
  }
  showDeleteModal.value = false;

  const refreshActive = managePengumumanStore.fetchActivePengumuman();
  if (
    managePengumumanStore.items.length === 1 &&
    managePengumumanStore.page > 1 &&
    managePengumumanStore.totalData > 1
  ) {
    await Promise.all([
      loadPengumuman(managePengumumanStore.page - 1),
      refreshActive,
    ]);
    return;
  }

  await Promise.all([loadPengumuman(), refreshActive]);
}

async function goPrev() {
  if (!canGoPrev.value) return;
  await loadPengumuman(managePengumumanStore.page - 1);
}

async function goNext() {
  if (!canGoNext.value) return;
  await loadPengumuman(managePengumumanStore.page + 1);
}

async function onLimitChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const nextLimit = Number(target.value) || 10;
  managePengumumanStore.limit = nextLimit;
  await loadPengumuman(1);
}

onMounted(async () => {
  await loadPengumuman(1);
});

async function gotoDashboard() {
  await navigateTo("/dashboard");
}
</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Management Pengumuman" brand-subtitle="Kelola judul, isi, dan masa tayang pengumuman" />
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

      <section class="rounded-2xl border border-default bg-surface p-5">
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-20 font-bold">Daftar Pengumuman</h2>
            <p class="text-muted">
              Kelola pengumuman, status tayang, dan periode berlaku.
            </p>
          </div>

          <button class="rounded-full bg-brand px-5 py-2.5 font-semibold text-on-brand" @click="openCreateModal">
            + Tambah Pengumuman
          </button>
        </div>

        <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-6">
          <input v-model="search" type="text" placeholder="Cari judul atau isi pengumuman..."
            class="h-11 rounded-xl border border-default px-4 outline-none placeholder-text-placeholder md:col-span-3"
            @keyup.enter="onSearch" />
          <select v-model="statusFilter"
            class="h-11 rounded-xl border border-default bg-surface px-3 outline-none md:col-span-1"
            @change="onSearch">
            <option v-for="option in STATUS_OPTIONS" :key="option.label" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <div class="flex items-center gap-2 md:col-span-2">
            <button class="h-11 flex-1 rounded-xl bg-brand px-5 font-semibold text-on-brand" @click="onSearch">
              Cari
            </button>
            <button class="h-11 flex-1 rounded-xl border border-tan bg-cream px-5 font-semibold text-brand"
              @click="onResetSearch">
              Reset
            </button>
          </div>
        </div>

        <p v-if="managePengumumanStore.errorMessage && !showFormModal && !showDeleteModal"
          class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ managePengumumanStore.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-4 py-3 font-bold">Judul</th>
                <th class="px-4 py-3 font-bold">Isi</th>
                <th class="px-4 py-3 font-bold">Periode</th>
                <th class="px-4 py-3 font-bold">Status</th>
                <th class="px-4 py-3 font-bold">Dibuat Oleh</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="managePengumumanStore.loadingList" class="border-t border-row">
                <td colspan="6" class="px-4 py-8 text-center text-muted">
                  Memuat data pengumuman...
                </td>
              </tr>

              <tr v-for="item in managePengumumanStore.items" :key="item.id" class="border-t border-row align-top">
                <td class="px-4 py-3 font-semibold">{{ item.judul }}</td>
                <td class="max-w-xs px-4 py-3">
                  <p class="line-clamp-2 text-muted">{{ item.isi }}</p>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">{{ formatPeriod(item) }}</td>
                <td class="px-4 py-3">
                  <span class="rounded-full px-3 py-1 text-size-xs font-semibold" :class="statusClass(item.status)">
                    {{ statusLabel(item.status) }}
                  </span>
                </td>
                <td class="px-4 py-3">{{ item.dibuat_oleh || "-" }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <button class="rounded-lg border border-tan bg-cream px-3 py-1.5 font-semibold text-brand"
                      @click="openEditModal(item)">
                      Edit
                    </button>
                    <button class="rounded-lg border border-error bg-error-light px-3 py-1.5 font-semibold text-error"
                      @click="openDeleteModal(item)">
                      Hapus
                    </button>
                  </div>
                </td>
              </tr>

              <tr v-if="!managePengumumanStore.loadingList && !managePengumumanStore.hasItems"
                class="border-t border-row">
                <td colspan="6" class="px-4 py-8 text-center text-muted">
                  Belum ada data pengumuman.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-muted">
            Total: <span class="font-bold text-content">{{ managePengumumanStore.totalData }}</span>
            data • Halaman
            <span class="font-bold text-content">{{ managePengumumanStore.page }}</span>
            dari
            <span class="font-bold text-content">{{ managePengumumanStore.totalPage }}</span>
          </p>

          <div class="flex items-center gap-2">
            <label class="text-muted">Limit</label>
            <select :value="managePengumumanStore.limit" class="h-10 rounded-lg border border-tan bg-surface px-2"
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

    <div v-if="showFormModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
      <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-surface p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-18 font-bold">{{ pageTitle }}</h3>
          <button class="text-muted" @click="closeFormModal">✕</button>
        </div>

        <p v-if="formMode === 'edit' && managePengumumanStore.loadingDetail" class="mb-3 text-muted">
          Memuat detail pengumuman...
        </p>

        <form class="grid grid-cols-1 gap-3 md:grid-cols-2" @submit.prevent="submitForm">
          <div class="md:col-span-2">
            <label class="mb-1 block text-label">Judul</label>
            <input v-model="form.judul" required maxlength="200" type="text"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div class="md:col-span-2">
            <label class="mb-1 block text-label">Isi</label>
            <textarea v-model="form.isi" required rows="5"
              class="w-full rounded-xl border border-default px-3 py-2 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-label">Status</label>
            <v-select :model-value="form.is_active" :items="[
              { label: 'Aktif', value: true },
              { label: 'Nonaktif', value: false },
            ]" item-title="label" item-value="value" variant="outlined" density="comfortable"
              class="w-full custom-underlined-input" @update:model-value="form.is_active = $event" />
          </div>

          <div class="hidden md:block" />

          <div>
            <label class="mb-1 block text-label">Tanggal Mulai</label>
            <input v-model="form.tanggal_mulai" type="datetime-local"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-label">Tanggal Berakhir</label>
            <input v-model="form.tanggal_berakhir" type="datetime-local"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <p class="md:col-span-2 text-12 text-muted">
            Kosongkan tanggal jika pengumuman tidak dibatasi waktu. Status tayang dihitung dari status aktif dan periode
            ini.
          </p>

          <p v-if="formError" class="md:col-span-2 rounded-xl bg-error-light px-4 py-3 text-error">
            {{ formError }}
          </p>

          <div class="md:col-span-2 mt-2 flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              @click="closeFormModal">
              Batal
            </button>
            <button type="submit" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="submitLoading || managePengumumanStore.loadingDetail">
              {{ submitLoading ? "Menyimpan..." : "Simpan" }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showDeleteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
      <div class="w-full max-w-md rounded-2xl bg-surface p-5">
        <h3 class="text-18 font-bold">Konfirmasi Hapus</h3>
        <p class="mt-2 text-muted">
          Apakah Anda yakin ingin menghapus pengumuman
          <span class="font-semibold text-content">{{ selectedJudul }}</span>?
        </p>
        <p v-if="deleteError" class="mt-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ deleteError }}
        </p>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
            @click="closeDeleteModal">
            Batal
          </button>
          <button
            class="rounded-xl border border-error bg-error-light px-4 py-2 font-semibold text-error disabled:opacity-50"
            :disabled="managePengumumanStore.loadingDelete" @click="confirmDelete">
            {{ managePengumumanStore.loadingDelete ? "Menghapus..." : "Hapus" }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.custom-underlined-input :deep(.v-field__outline) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.267) !important;
  opacity: 1 !important;
}
</style>

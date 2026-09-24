<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import {
  useManagePermissionStore,
  type PermissionItem,
} from "~/stores/managePermissionStore";
import { parsePermissionMeta } from "~/composables/usePermissionScope";

defineOptions({
  name: "PermissionsManagementPage",
});

const managePermissionStore = useManagePermissionStore();

const search = ref("");
const showFormModal = ref(false);
const showDeleteModal = ref(false);
const formMode = ref<"create" | "edit">("create");
const selectedPermissionId = ref("");

const form = reactive({
  kode: "",
  resource: "",
  aksi: "",
  deskripsi: "",
});

const filteredPermissions = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  if (!keyword) return managePermissionStore.permissions;

  return managePermissionStore.permissions.filter((item) => {
    return (
      item.kode?.toLowerCase().includes(keyword) ||
      item.resource?.toLowerCase().includes(keyword) ||
      item.aksi?.toLowerCase().includes(keyword) ||
      item.deskripsi?.toLowerCase().includes(keyword)
    );
  });
});

const submitLoading = computed(
  () => managePermissionStore.loadingCreate || managePermissionStore.loadingUpdate,
);

const permissionScopeGroups = computed(() =>
  managePermissionStore.scopeGroups.filter((group) => group.items.length > 0),
);

const selectedScopePreview = computed(() => {
  if (!form.kode && !form.resource && !form.aksi && !form.deskripsi) {
    return {
      categoryLabel: "Belum terdeteksi",
      ptCode: "-",
      estateCode: "-",
      transactionCode: "-",
    };
  }

  const meta = parsePermissionMeta({
    id: selectedPermissionId.value || "draft",
    kode: form.kode,
    resource: form.resource,
    aksi: form.aksi,
    deskripsi: form.deskripsi,
  });

  const categoryMap: Record<string, string> = {
    menu: "Level 1 - Menu / Modul Dashboard",
    pt: "Level 2 - Akses PT",
    estate: "Level 3 - Akses Estate",
    transaction: "Level 4 - Akses Transaksi",
    general: "Permission Umum / Lainnya",
  };

  return {
    categoryLabel: categoryMap[meta.category] ?? "Permission Umum / Lainnya",
    ptCode: meta.ptCode ?? "-",
    estateCode: meta.estateCode ?? "-",
    transactionCode: meta.transactionCode ?? "-",
  };
});

const pageTitle = computed(() =>
  formMode.value === "create" ? "Tambah Permission" : "Edit Permission",
);

function resetForm() {
  form.kode = "";
  form.resource = "";
  form.aksi = "";
  form.deskripsi = "";
}

function fillForm(permission: PermissionItem) {
  form.kode = permission.kode ?? "";
  form.resource = permission.resource ?? "";
  form.aksi = permission.aksi ?? "";
  form.deskripsi = permission.deskripsi ?? "";
}

function openCreateModal() {
  formMode.value = "create";
  selectedPermissionId.value = "";
  resetForm();
  showFormModal.value = true;
}

function openEditModal(permission: PermissionItem) {
  formMode.value = "edit";
  selectedPermissionId.value = permission.id;
  fillForm(permission);
  showFormModal.value = true;
}

function closeFormModal() {
  showFormModal.value = false;
}

function openDeleteModal(permission: PermissionItem) {
  selectedPermissionId.value = permission.id;
  showDeleteModal.value = true;
}

function closeDeleteModal() {
  showDeleteModal.value = false;
}

async function submitForm() {
  if (formMode.value === "create") {
    await managePermissionStore.createPermission({
      kode: form.kode,
      resource: form.resource,
      aksi: form.aksi,
      deskripsi: form.deskripsi,
    });
  } else {
    await managePermissionStore.updatePermission(selectedPermissionId.value, {
      kode: form.kode,
      resource: form.resource,
      aksi: form.aksi,
      deskripsi: form.deskripsi,
    });
  }

  showFormModal.value = false;
  await managePermissionStore.fetchPermissions();
}

async function confirmDelete() {
  await managePermissionStore.deletePermission(selectedPermissionId.value);
  showDeleteModal.value = false;
  await managePermissionStore.fetchPermissions();
}

async function gotoUsers() {
  await navigateTo("/users");
}

onMounted(async () => {
  await managePermissionStore.fetchPermissions();
});
</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Management Permission" brand-subtitle="Kelola permission sistem" />

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center gap-3">
        <button type="button" aria-label="Back" @click="gotoUsers"
          class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-light bg-surface text-icon shadow-sm transition-all duration-200 hover-border-navy hover-bg-slate-light hover-text-navy">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
            stroke="currentColor" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>

        <p class="text-size-sm font-semibold tracking-wide text-subtitle">Management User</p>
      </div>

      <section class="rounded-2xl border border-default bg-surface p-5">
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-20 font-bold">Daftar Permission</h2>
            <p class="text-muted">
              Kelola permission bertingkat: menu, PT, estate, dan transaksi.
            </p>
          </div>

          <button class="rounded-full bg-brand px-5 py-2.5 font-semibold text-on-brand" @click="openCreateModal">
            + Tambah Permission
          </button>
        </div>

        <div class="mb-4">
          <input v-model="search" type="text" placeholder="Cari permission..."
            class="h-11 w-full rounded-xl border border-default px-4 outline-none placeholder-text-placeholder" />
        </div>

        <p v-if="managePermissionStore.errorMessage" class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ managePermissionStore.errorMessage }}
        </p>

        <!-- <div class="mb-4 rounded-xl border border-default bg-cream-light p-4">
          <h3 class="text-16 font-bold text-brand">Struktur Permission Bertingkat</h3>
          <p class="mt-1 text-muted">
            Preview kategori permission berdasarkan data saat ini. Ini membantu memastikan flow level akses konsisten.
          </p>

          <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div v-for="group in permissionScopeGroups" :key="group.category"
              class="rounded-lg border border-dashed-tan bg-surface p-3">
              <p class="text-size-sm font-semibold text-brand">{{ group.label }}</p>
              <p class="mt-1 text-size-xs text-muted">{{ group.items.length }} permission</p>
            </div>

            <div v-if="permissionScopeGroups.length === 0"
              class="rounded-lg border border-dashed border-dashed-tan bg-surface p-3 text-muted">
              Belum ada data permission yang bisa dikategorikan.
            </div>
          </div>
        </div> -->

        <div class="overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-4 py-3 font-bold">Kode</th>
                <th class="px-4 py-3 font-bold">Resource</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
                <th class="px-4 py-3 font-bold">Deskripsi</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="managePermissionStore.loadingList" class="border-t border-row">
                <td colspan="5" class="px-4 py-8 text-center text-muted">
                  Memuat data permission...
                </td>
              </tr>

              <tr v-for="item in filteredPermissions" :key="item.id" class="border-t border-row">
                <td class="px-4 py-3">{{ item.kode }}</td>
                <td class="px-4 py-3">{{ item.resource }}</td>
                <td class="px-4 py-3">{{ item.aksi }}</td>
                <td class="px-4 py-3">{{ item.deskripsi }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <button
                      class="rounded-lg border border-tan bg-cream px-3 py-1.5 font-semibold text-brand"
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

              <tr v-if="
                !managePermissionStore.loadingList &&
                filteredPermissions.length === 0
              " class="border-t border-row">
                <td colspan="5" class="px-4 py-8 text-center text-muted">
                  Belum ada data permission.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="showFormModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
      <div class="w-full max-w-3xl rounded-2xl bg-surface p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-18 font-bold">{{ pageTitle }}</h3>
          <button class="text-muted" @click="closeFormModal">✕</button>
        </div>

        <form @submit.prevent="submitForm">

          <div class="mx-4 p-4">
            <div class="grid grid-cols-1 gap-4 md:grid-cols-3">

              <button
                class="w-full rounded-lg bg-blue-dark px-5 py-3 font-semibold text-on-brand shadow-md hover-bg-blue-darker transition duration-200 ease-in-out focus:outline-none focus:ring-2 focus-ring-blue focus:ring-opacity-75">
                Menu
              </button>

              <button
                class="w-full rounded-lg bg-blue-dark px-5 py-3 font-semibold text-on-brand shadow-md hover-bg-blue-darker transition duration-200 ease-in-out focus:outline-none focus:ring-2 focus-ring-blue focus:ring-opacity-75">
                Perusahaan & Estate
              </button>

              <button
                class="w-full rounded-lg bg-blue-dark px-5 py-3 font-semibold text-on-brand shadow-md hover-bg-blue-darker transition duration-200 ease-in-out focus:outline-none focus:ring-2 focus-ring-blue focus:ring-opacity-75">
                Transaksi
              </button>

            </div>
          </div>

          <div class="grid grid-cols-1 gap-3 md:grid-cols-2">

            <div>
              <label class="mb-1 block text-label">Kode</label>
              <input v-model="form.kode" required type="text"
                class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
            </div>

            <div>
              <label class="mb-1 block text-label">Resource</label>
              <input v-model="form.resource" required type="text"
                class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
            </div>

            <div>
              <label class="mb-1 block text-label">Aksi</label>
              <input v-model="form.aksi" required type="text"
                class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
            </div>

            <div class="md:col-span-2">
              <label class="mb-1 block text-label">Deskripsi</label>
              <textarea v-model="form.deskripsi" rows="3"
                class="w-full rounded-xl border border-default px-3 py-2 outline-none" />
            </div>

            <!-- <div class="md:col-span-2 rounded-xl border border-default bg-cream-light p-4">
              <h4 class="text-15 font-bold text-brand">Preview Scope Permission</h4>
              <p class="mt-1 text-13 text-muted">
                Kategori akan terdeteksi otomatis dari kombinasi kode/resource/deskripsi.
              </p>

              <div class="mt-3 grid grid-cols-1 gap-2 text-13 md:grid-cols-2">
                <div class="rounded-lg border border-default bg-surface px-3 py-2">
                  <p class="text-muted">Kategori</p>
                  <p class="font-semibold text-brand">{{ selectedScopePreview.categoryLabel }}</p>
                </div>
                <div class="rounded-lg border border-default bg-surface px-3 py-2">
                  <p class="text-muted">PT Scope</p>
                  <p class="font-semibold text-brand">{{ selectedScopePreview.ptCode }}</p>
                </div>
                <div class="rounded-lg border border-default bg-surface px-3 py-2">
                  <p class="text-muted">Estate Scope</p>
                  <p class="font-semibold text-brand">{{ selectedScopePreview.estateCode }}</p>
                </div>
                <div class="rounded-lg border border-default bg-surface px-3 py-2">
                  <p class="text-muted">Transaction Scope</p>
                  <p class="font-semibold text-brand">{{ selectedScopePreview.transactionCode }}</p>
                </div>
              </div>
            </div> -->


            <div class="md:col-span-2 mt-2 flex justify-end gap-2">
              <button type="button"
                class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
                @click="closeFormModal">
                Batal
              </button>
              <button type="submit"
                class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
                :disabled="submitLoading">
                {{ submitLoading ? "Menyimpan..." : "Simpan" }}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showDeleteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
      <div class="w-full max-w-md rounded-2xl bg-surface p-5">
        <h3 class="text-18 font-bold">Konfirmasi Hapus</h3>
        <p class="mt-2 text-muted">
          Apakah Anda yakin ingin menghapus permission ini?
        </p>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
            @click="closeDeleteModal">
            Batal
          </button>
          <button
            class="rounded-xl border border-error bg-error-light px-4 py-2 font-semibold text-error disabled:opacity-50"
            :disabled="managePermissionStore.loadingDelete" @click="confirmDelete">
            {{ managePermissionStore.loadingDelete ? "Menghapus..." : "Hapus" }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

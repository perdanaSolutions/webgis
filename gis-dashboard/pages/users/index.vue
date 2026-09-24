<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import {
  useManageUserStore,
  type CreateUserPayload,
  type UpdateUserPayload,
  type UserItem,
} from "~/stores/manageUserStore";
import type { RoleItem } from "~/stores/manageRoleStore";

defineOptions({
  name: "UsersManagementPage",
});

const manageUserStore = useManageUserStore();

const search = ref("");
const showFormModal = ref(false);
const showDeleteModal = ref(false);
const formMode = ref<"create" | "edit">("create");
const selectedUserId = ref<string>("");

const form = reactive<CreateUserPayload>({
  username: "",
  email: "",
  nama_lengkap: "",
  role_id: "",
  is_active: true,
  password: "",
});

const submitLoading = computed(
  () => manageUserStore.loadingCreate || manageUserStore.loadingUpdate,
);

const pageTitle = computed(() =>
  formMode.value === "create" ? "Tambah User" : "Edit User",
);

const canGoPrev = computed(() => manageUserStore.page > 1);
const canGoNext = computed(
  () => manageUserStore.page < manageUserStore.totalPage,
);

function resetForm() {
  form.username = "";
  form.email = "";
  form.nama_lengkap = "";
  form.role_id = "";
  form.is_active = true;
  form.password = "";
}

function fillFormFromUser(user: UserItem) {
  form.username = user.username ?? "";
  form.email = user.email ?? "";
  form.nama_lengkap = user.nama_lengkap ?? "";
  form.role_id = user.role?.id ?? "";
  form.is_active = Boolean(user.is_active);
  form.password = "";
}

async function loadUsers(nextPage?: number) {
  await manageUserStore.fetchUsers({
    search: search.value,
    page: nextPage ?? manageUserStore.page,
    limit: manageUserStore.limit,
  });
}

async function onSearch() {
  await loadUsers(1);
}

async function onResetSearch() {
  search.value = "";
  await loadUsers(1);
}

function openCreateModal() {
  formMode.value = "create";
  selectedUserId.value = "";
  resetForm();
  showFormModal.value = true;
}

async function openEditModal(user: UserItem) {
  formMode.value = "edit";
  selectedUserId.value = user.id;
  fillFormFromUser(user);
  // belum ada end point get detail
  // try {
  //   const detail = await manageUserStore.fetchUserById(user.id);
  //   fillFormFromUser(detail);
  // } catch {
  //   // fallback menggunakan data row table jika endpoint detail gagal
  // }
  showFormModal.value = true;
}

function closeFormModal() {
  showFormModal.value = false;
}

function openDeleteModal(user: UserItem) {
  selectedUserId.value = user.id;
  showDeleteModal.value = true;
}

function closeDeleteModal() {
  showDeleteModal.value = false;
}

async function submitForm() {
  if (formMode.value === "create") {
    await manageUserStore.createUser({
      username: form.username,
      email: form.email,
      nama_lengkap: form.nama_lengkap,
      role_id: form.role_id,
      is_active: form.is_active,
      password: form.password,
    });
  } else {
    const payload: UpdateUserPayload = {
      username: form.username,
      email: form.email,
      nama_lengkap: form.nama_lengkap,
      role_id: form.role_id,
      is_active: form.is_active,
      password: form.password,
    };

    await manageUserStore.updateUser(selectedUserId.value, payload);
  }

  showFormModal.value = false;
  await loadUsers();
}

async function confirmDelete() {
  await manageUserStore.deleteUser(selectedUserId.value);
  showDeleteModal.value = false;

  if (
    manageUserStore.users.length === 1 &&
    manageUserStore.page > 1 &&
    manageUserStore.totalData > 1
  ) {
    await loadUsers(manageUserStore.page - 1);
    return;
  }

  await loadUsers();
}

async function goPrev() {
  if (!canGoPrev.value) return;
  await loadUsers(manageUserStore.page - 1);
}

async function goNext() {
  if (!canGoNext.value) return;
  await loadUsers(manageUserStore.page + 1);
}

async function onLimitChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const nextLimit = Number(target.value) || 10;
  manageUserStore.limit = nextLimit;
  await loadUsers(1);
}

onMounted(async () => {
  await Promise.all([
    manageUserStore.fetchRoles(),
    loadUsers(1),
  ]);
});


async function gotoDashboard() {
  await navigateTo('/dashboard')
}

function filterRoleOption(
  _value: string,
  query: string,
  item?: { raw: RoleItem },
) {
  const keyword = query.trim().toLowerCase();
  if (!keyword) return true;

  const role = item?.raw;
  if (!role) return true;

  return (
    role.nama.toLowerCase().includes(keyword) ||
    role.deskripsi.toLowerCase().includes(keyword)
  );
}

</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Management User" brand-subtitle="Kelola data pengguna dan role" />
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

        <div class="flex flex-1 items-center justify-end gap-2">
          <NuxtLink to="/roles"
            class="rounded-md border border-tan bg-cream px-4 py-1.5 text-size-sm font-semibold text-brand transition hover-bg-cream-active">
            Management Role
          </NuxtLink>
        </div>
      </div>

      <section class="rounded-2xl border border-default bg-surface p-5">
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-20 font-bold">Daftar User</h2>
            <p class="text-muted">
              Kelola pengguna, role, dan status aktif user.
            </p>
          </div>

          <button class="rounded-full bg-brand px-5 py-2.5 font-semibold text-on-brand" @click="openCreateModal">
            + Tambah User
          </button>
        </div>

        <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_auto]">
          <input v-model="search" type="text" placeholder="Cari username / email / nama lengkap..."
            class="h-11 rounded-xl border border-default px-4 outline-none placeholder-text-placeholder"
            @keyup.enter="onSearch" />
          <button class="h-11 rounded-xl bg-brand px-5 font-semibold text-on-brand" @click="onSearch">
            Cari
          </button>
          <button class="h-11 rounded-xl border border-tan bg-cream px-5 font-semibold text-brand"
            @click="onResetSearch">
            Reset
          </button>
        </div>

        <p v-if="manageUserStore.errorMessage" class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ manageUserStore.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-4 py-3 font-bold">Username</th>
                <th class="px-4 py-3 font-bold">Email</th>
                <th class="px-4 py-3 font-bold">Nama Lengkap</th>
                <th class="px-4 py-3 font-bold">Role</th>
                <th class="px-4 py-3 font-bold">Status</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="manageUserStore.loadingList" class="border-t border-row">
                <td colspan="6" class="px-4 py-8 text-center text-muted">
                  Memuat data user...
                </td>
              </tr>

              <tr v-for="item in manageUserStore.users" :key="item.id" class="border-t border-row">
                <td class="px-4 py-3">{{ item.username }}</td>
                <td class="px-4 py-3">{{ item.email }}</td>
                <td class="px-4 py-3">{{ item.nama_lengkap }}</td>
                <td class="px-4 py-3">{{ item.role?.nama ?? '' }}</td>
                <td class="px-4 py-3">
                  <span class="rounded-full px-3 py-1 text-size-xs font-semibold" :class="item.is_active
                    ? 'bg-success-lighter text-success'
                    : 'bg-slate-muted text-slate-muted'
                    ">
                    {{ item.is_active ? "Aktif" : "Nonaktif" }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <div v-if="item.role?.nama !== 'superadmin'" class="flex items-center gap-2">
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

              <tr v-if="!manageUserStore.loadingList && !manageUserStore.hasUsers" class="border-t border-row">
                <td colspan="6" class="px-4 py-8 text-center text-muted">
                  Belum ada data user.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-muted">
            Total: <span class="font-bold text-content">{{ manageUserStore.totalData }}</span>
            data • Halaman
            <span class="font-bold text-content">{{ manageUserStore.page }}</span>
            dari
            <span class="font-bold text-content">{{ manageUserStore.totalPage }}</span>
          </p>

          <div class="flex items-center gap-2">
            <label class="text-muted">Limit</label>
            <select :value="manageUserStore.limit" class="h-10 rounded-lg border border-tan bg-surface px-2"
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
      <div class="w-full max-w-2xl rounded-2xl bg-surface p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-18 font-bold">{{ pageTitle }}</h3>
          <button class="text-muted" @click="closeFormModal">✕</button>
        </div>

        <form class="grid grid-cols-1 gap-3 md:grid-cols-2" @submit.prevent="submitForm">
          <div>
            <label class="mb-1 block text-label">Username</label>
            <input v-model="form.username" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-label">Email</label>
            <input v-model="form.email" required type="email"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div class="md:col-span-2">
            <label class="mb-1 block text-label">Nama Lengkap</label>
            <input v-model="form.nama_lengkap" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-label">Role</label>
            <v-autocomplete v-model="form.role_id" :items="manageUserStore.roles" item-title="nama" item-value="id"
              placeholder="Cari atau pilih role" variant="outlined" density="comfortable" color="#2B7FFF"
              class="w-full custom-underlined-input" hide-details clearable :loading="manageUserStore.loadingRoles"
              :custom-filter="filterRoleOption" />
          </div>

          <div>
            <label class="mb-1 block text-label">Status</label>
            <v-select :model-value="form.is_active" :items="[
              { label: 'Aktif', value: true },
              { label: 'Nonaktif', value: false }
            ]" item-title="label" item-value="value" variant="outlined" density="comfortable"
              class="w-full custom-underlined-input" @update:model-value="form.is_active = $event"></v-select>
          </div>

          <div class="md:col-span-2">
            <label class="mb-1 block text-label">
              Password
            </label>
            <input v-model="form.password" :required="formMode === 'create'" type="password"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div class="md:col-span-2 mt-2 flex justify-end gap-2">
            <button type="button"
              class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              @click="closeFormModal">
              Batal
            </button>
            <button type="submit" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="submitLoading">
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
          Apakah Anda yakin ingin menghapus user ini?
        </p>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
            @click="closeDeleteModal">
            Batal
          </button>
          <button
            class="rounded-xl border border-error bg-error-light px-4 py-2 font-semibold text-error disabled:opacity-50"
            :disabled="manageUserStore.loadingDelete" @click="confirmDelete">
            {{ manageUserStore.loadingDelete ? "Menghapus..." : "Hapus" }}
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

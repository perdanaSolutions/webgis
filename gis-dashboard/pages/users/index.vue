<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import {
  useManageUserStore,
  type CreateUserPayload,
  type UpdateUserPayload,
  type UserItem,
} from "~/stores/manageUserStore";
import { dashboardStore } from "~/stores/dashboardStore";

defineOptions({
  name: "UsersManagementPage",
});

const manageUserStore = useManageUserStore();
const dashboardStoreInstance = dashboardStore();

const search = ref("");
const showFormModal = ref(false);
const showDeleteModal = ref(false);
const showPermissionModal = ref(false);
const formMode = ref<"create" | "edit">("create");
const selectedUserId = ref<string>("");
const selectedPermissionUser = ref<UserItem | null>(null);
const activePermissionTab = ref<"menu" | "masterData" | "transaksi">("menu");
const selectedMenuKeys = ref<string[]>([]);
const selectedPtValues = ref<string[]>([]);
const selectedEstateValues = ref<string[]>([]);
const selectedTransaksiValues = ref<string[]>([]);

const ptOptions = [
  { value: "pt-a", label: "PT Perkebunan A" },
  { value: "pt-b", label: "PT Perkebunan B" },
];

const estateOptions = [
  { value: "estate-utara", label: "Estate Utara" },
  { value: "estate-selatan", label: "Estate Selatan" },
];

const transaksiOptions = [
  { value: "input-transaksi", label: "Input Transaksi" },
  { value: "approval-transaksi", label: "Approval Transaksi" },
  { value: "riwayat-transaksi", label: "Riwayat Transaksi" },
];

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

function openPermissionModal(user: UserItem) {
  selectedPermissionUser.value = user;
  activePermissionTab.value = "menu";
  selectedMenuKeys.value = [];
  selectedPtValues.value = [];
  selectedEstateValues.value = [];
  selectedTransaksiValues.value = [];
  showPermissionModal.value = true;
}

function closePermissionModal() {
  showPermissionModal.value = false;
  selectedPermissionUser.value = null;
}

function toggleAllMenu() {
  const allMenuKeys = dashboardStoreInstance.moduleItems.map((menu, index) => `${menu.to}-${index}`);
  selectedMenuKeys.value =
    selectedMenuKeys.value.length === allMenuKeys.length ? [] : allMenuKeys;
}

function toggleAllMasterData() {
  const allPt = ptOptions.map((item) => item.value);
  const allEstate = estateOptions.map((item) => item.value);
  const isAllSelected =
    selectedPtValues.value.length === allPt.length &&
    selectedEstateValues.value.length === allEstate.length;

  if (isAllSelected) {
    selectedPtValues.value = [];
    selectedEstateValues.value = [];
    return;
  }

  selectedPtValues.value = allPt;
  selectedEstateValues.value = allEstate;
}

function toggleAllTransaksi() {
  const allTransaksi = transaksiOptions.map((item) => item.value);
  selectedTransaksiValues.value =
    selectedTransaksiValues.value.length === allTransaksi.length ? [] : allTransaksi;
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

</script>

<template>
  <main class="min-h-screen bg-[#FBFAF8] text-[14px] text-[#2E1F18]">
    <Header brand-title="Management User" brand-subtitle="Kelola data pengguna dan hak akses" />
    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <button type="button" aria-label="Back" @click="gotoDashboard"
            class="flex h-8 w-8 items-center justify-center rounded-full border border-[#D8DEE8] bg-white text-[#566074] shadow-sm transition-all duration-200 hover:border-[#1A315B] hover:text-[#1A315B] hover:bg-slate-50 hover:scale-105 active:scale-95">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
              stroke="currentColor" class="h-4 w-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>

          <p class="font-semibold tracking-wide text-[#333d4e]">Dashboard</p>
        </div>

        <!-- <div class="flex flex-1 items-center justify-end gap-2">
          <NuxtLink to="/roles"
            class="rounded-md border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-1.5 text-sm font-semibold text-[#4D392A] transition hover:bg-[#F4E9DD]">
            Management Role
          </NuxtLink>

          <NuxtLink to="/permissions"
            class="rounded-md border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-1.5 text-sm font-semibold text-[#4D392A] transition hover:bg-[#F4E9DD]">
            Management Permission
          </NuxtLink>
        </div> -->
      </div>

      <section class="rounded-2xl border border-[#EEE6DE] bg-white p-5">
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-[20px] font-bold">Daftar User</h2>
            <p class="text-[#8A817A]">
              Kelola pengguna, role, dan status aktif user.
            </p>
          </div>

          <button class="rounded-full bg-[#4D392A] px-5 py-2.5 font-semibold text-white" @click="openCreateModal">
            + Tambah User
          </button>
        </div>

        <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_auto]">
          <input v-model="search" type="text" placeholder="Cari username / email / nama lengkap..."
            class="h-11 rounded-xl border border-[#EEE6DE] px-4 outline-none placeholder:text-[#A6A29D]"
            @keyup.enter="onSearch" />
          <button class="h-11 rounded-xl bg-[#4D392A] px-5 font-semibold text-white" @click="onSearch">
            Cari
          </button>
          <button class="h-11 rounded-xl border border-[#DDD1C7] bg-[#FFF8F2] px-5 font-semibold text-[#4D392A]"
            @click="onResetSearch">
            Reset
          </button>
        </div>

        <p v-if="manageUserStore.errorMessage" class="mb-3 rounded-xl bg-red-50 px-4 py-3 text-red-600">
          {{ manageUserStore.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-[#EEE6DE]">
          <table class="min-w-full bg-white">
            <thead class="bg-[#F8F3EE] text-left text-[#4D392A]">
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
              <tr v-if="manageUserStore.loadingList" class="border-t border-[#F0E8E0]">
                <td colspan="6" class="px-4 py-8 text-center text-[#8A817A]">
                  Memuat data user...
                </td>
              </tr>

              <tr v-for="item in manageUserStore.users" :key="item.id" class="border-t border-[#F0E8E0]">
                <td class="px-4 py-3">{{ item.username }}</td>
                <td class="px-4 py-3">{{ item.email }}</td>
                <td class="px-4 py-3">{{ item.nama_lengkap }}</td>
                <td class="px-4 py-3">{{ item.role?.nama ?? '' }}</td>
                <td class="px-4 py-3">
                  <span class="rounded-full px-3 py-1 text-xs font-semibold" :class="item.is_active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-slate-200 text-slate-600'
                    ">
                    {{ item.is_active ? "Aktif" : "Nonaktif" }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <div v-if="item.role?.nama !== 'superadmin'" class="flex items-center gap-2">
                    <button
                      class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 font-semibold text-[#4D392A]"
                      @click="openEditModal(item)">
                      Edit
                    </button>
                    <button class="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 font-semibold text-red-600"
                      @click="openDeleteModal(item)">
                      Hapus
                    </button>
                    <button
                      class="rounded-lg border border-red-200 bg-orange-50 px-3 py-1.5 font-semibold text-orange-600"
                      @click="openPermissionModal(item)">
                      Hak Akses
                    </button>
                  </div>
                </td>
              </tr>

              <tr v-if="!manageUserStore.loadingList && !manageUserStore.hasUsers" class="border-t border-[#F0E8E0]">
                <td colspan="6" class="px-4 py-8 text-center text-[#8A817A]">
                  Belum ada data user.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-[#8A817A]">
            Total: <span class="font-bold text-[#2E1F18]">{{ manageUserStore.totalData }}</span>
            data • Halaman
            <span class="font-bold text-[#2E1F18]">{{ manageUserStore.page }}</span>
            dari
            <span class="font-bold text-[#2E1F18]">{{ manageUserStore.totalPage }}</span>
          </p>

          <div class="flex items-center gap-2">
            <label class="text-[#8A817A]">Limit</label>
            <select :value="manageUserStore.limit" class="h-10 rounded-lg border border-[#DDD1C7] bg-white px-2"
              @change="onLimitChange">
              <option :value="5">5</option>
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>

            <button
              class="rounded-lg border border-[#DDD1C7] bg-white px-3 py-2 font-semibold text-[#4D392A] disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canGoPrev" @click="goPrev">
              Prev
            </button>
            <button
              class="rounded-lg border border-[#DDD1C7] bg-white px-3 py-2 font-semibold text-[#4D392A] disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canGoNext" @click="goNext">
              Next
            </button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="showFormModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-2xl rounded-2xl bg-white p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-[18px] font-bold">{{ pageTitle }}</h3>
          <button class="text-[#8A817A]" @click="closeFormModal">✕</button>
        </div>

        <form class="grid grid-cols-1 gap-3 md:grid-cols-2" @submit.prevent="submitForm">
          <div>
            <label class="mb-1 block text-[#6F645B]">Username</label>
            <input v-model="form.username" required type="text"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">Email</label>
            <input v-model="form.email" required type="email"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div class="md:col-span-2">
            <label class="mb-1 block text-[#6F645B]">Nama Lengkap</label>
            <input v-model="form.nama_lengkap" required type="text"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">Role</label>
            <select v-model="form.role_id" required
              class="h-11 w-full rounded-xl border border-[#EEE6DE] bg-white px-3 outline-none">
              <option value="" disabled>Pilih role</option>
              <option v-for="role in manageUserStore.roles" :key="role.id" :value="role.id">
                {{ role.nama }}
              </option>
            </select>
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">Status</label>
            <select v-model="form.is_active"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] bg-white px-3 outline-none">
              <option :value="true">Aktif</option>
              <option :value="false">Nonaktif</option>
            </select>
          </div>

          <div class="md:col-span-2">
            <label class="mb-1 block text-[#6F645B]">
              Password
            </label>
            <input v-model="form.password" :required="formMode === 'create'" type="password"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div class="md:col-span-2 mt-2 flex justify-end gap-2">
            <button type="button"
              class="rounded-xl border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-2 font-semibold text-[#4D392A]"
              @click="closeFormModal">
              Batal
            </button>
            <button type="submit" class="rounded-xl bg-[#4D392A] px-4 py-2 font-semibold text-white disabled:opacity-50"
              :disabled="submitLoading">
              {{ submitLoading ? "Menyimpan..." : "Simpan" }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showPermissionModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-4xl rounded-2xl bg-white p-5">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <h3 class="text-[18px] font-bold">Hak Akses User</h3>
            <p class="text-sm text-[#8A817A]">
              Atur hak akses untuk
              <span class="font-semibold text-[#2E1F18]">{{ selectedPermissionUser?.username }}</span>
            </p>
          </div>
          <button class="text-[#8A817A]" @click="closePermissionModal">✕</button>
        </div>

        <div class="mb-4 flex flex-wrap gap-2 border-b border-[#EEE6DE] pb-3">
          <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'menu'
            ? 'bg-[#4D392A] text-white'
            : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="activePermissionTab = 'menu'">
            Akses Menu
          </button>
          <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'masterData'
            ? 'bg-[#4D392A] text-white'
            : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="activePermissionTab = 'masterData'">
            Akses Perusahaan dan Akses estate
          </button>
          <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'transaksi'
            ? 'bg-[#4D392A] text-white'
            : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="activePermissionTab = 'transaksi'">
            Akses transaksi
          </button>
        </div>

        <div v-if="activePermissionTab === 'menu'" class="rounded-xl border border-[#EEE6DE] p-4">
          <div class="mb-3 flex items-center justify-between gap-2">
            <p class="font-semibold text-[#4D392A]">List Menu</p>
            <button type="button"
              class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm font-semibold text-[#4D392A]"
              @click="toggleAllMenu">
              Ceklis Semua
            </button>
          </div>

          <div v-if="dashboardStoreInstance.loading" class="text-[#8A817A]">
            Memuat data menu...
          </div>

          <div v-else-if="!dashboardStoreInstance.moduleItems?.length" class="text-[#8A817A]">
            Belum ada data menu.
          </div>

          <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
            <label v-for="(menu, index) in dashboardStoreInstance.moduleItems" :key="`${menu.to}-${index}`"
              class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
              <input v-model="selectedMenuKeys" type="checkbox" class="h-4 w-4" :value="`${menu.to}-${index}`" />
              <span>{{ menu.title ?? 'Menu' }}</span>
            </label>
          </div>
        </div>

        <div v-else-if="activePermissionTab === 'masterData'" class="rounded-xl border border-[#EEE6DE] p-4">
          <div class="mb-3 flex items-center justify-between gap-2">
            <p class="font-semibold text-[#4D392A]">List data pt dan list data estate</p>
            <button type="button"
              class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm font-semibold text-[#4D392A]"
              @click="toggleAllMasterData">
              Ceklis Semua
            </button>
          </div>

          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p class="mb-2 text-sm font-semibold text-[#6F645B]">Data PT</p>
              <div class="space-y-2">
                <label v-for="pt in ptOptions" :key="pt.value"
                  class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                  <input v-model="selectedPtValues" type="checkbox" class="h-4 w-4" :value="pt.value" />
                  <span>{{ pt.label }}</span>
                </label>
              </div>
            </div>

            <div>
              <p class="mb-2 text-sm font-semibold text-[#6F645B]">Data Estate</p>
              <div class="space-y-2">
                <label v-for="estate in estateOptions" :key="estate.value"
                  class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                  <input v-model="selectedEstateValues" type="checkbox" class="h-4 w-4" :value="estate.value" />
                  <span>{{ estate.label }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="rounded-xl border border-[#EEE6DE] p-4">
          <div class="mb-3 flex items-center justify-between gap-2">
            <p class="font-semibold text-[#4D392A]">List data transaksi</p>
            <button type="button"
              class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm font-semibold text-[#4D392A]"
              @click="toggleAllTransaksi">
              Ceklis Semua
            </button>
          </div>

          <div class="space-y-2">
            <label v-for="trx in transaksiOptions" :key="trx.value"
              class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
              <input v-model="selectedTransaksiValues" type="checkbox" class="h-4 w-4" :value="trx.value" />
              <span>{{ trx.label }}</span>
            </label>
          </div>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-2 font-semibold text-[#4D392A]"
            @click="closePermissionModal">
            Tutup
          </button>
          <button class="rounded-xl bg-[#4D392A] px-4 py-2 font-semibold text-white">
            Simpan Hak Akses
          </button>
        </div>
      </div>
    </div>

    <div v-if="showDeleteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-md rounded-2xl bg-white p-5">
        <h3 class="text-[18px] font-bold">Konfirmasi Hapus</h3>
        <p class="mt-2 text-[#8A817A]">
          Apakah Anda yakin ingin menghapus user ini?
        </p>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-2 font-semibold text-[#4D392A]"
            @click="closeDeleteModal">
            Batal
          </button>
          <button
            class="rounded-xl border border-red-200 bg-red-50 px-4 py-2 font-semibold text-red-600 disabled:opacity-50"
            :disabled="manageUserStore.loadingDelete" @click="confirmDelete">
            {{ manageUserStore.loadingDelete ? "Menghapus..." : "Hapus" }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

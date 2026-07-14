<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import { useManageRoleStore, type RoleItem } from "~/stores/manageRoleStore";
import { usePermissionScope } from "~/composables/usePermissionScope";

defineOptions({
  name: "RolesManagementPage",
});

const manageRoleStore = useManageRoleStore();

const search = ref("");
const showFormModal = ref(false);
const formMode = ref<"create" | "edit">("create");
const selectedRoleId = ref("");

const form = reactive({
  nama: "",
  deskripsi: "",
  permission_ids: [] as string[],
});

const filteredRoles = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  if (!keyword) return manageRoleStore.roles;

  return manageRoleStore.roles.filter((item) => {
    return (
      item.nama?.toLowerCase().includes(keyword) ||
      item.deskripsi?.toLowerCase().includes(keyword)
    );
  });
});

const submitLoading = computed(
  () => manageRoleStore.loadingCreate || manageRoleStore.loadingUpdate,
);

const { grouped: groupedPermissions } = usePermissionScope(
  () => manageRoleStore.permissions,
);

const groupedPermissionSections = computed(() => [
  {
    key: "menu",
    label: "Level 1 - Akses Menu / Modul Dashboard",
    items: groupedPermissions.value.menu,
  },
  {
    key: "pt",
    label: "Level 2 - Akses Data Map per PT",
    items: groupedPermissions.value.pt,
  },
  {
    key: "estate",
    label: "Level 3 - Akses Data Map per Estate",
    items: groupedPermissions.value.estate,
  },
  {
    key: "transaction",
    label: "Level 4 - Akses Data Transaksi",
    items: groupedPermissions.value.transaction,
  },
  {
    key: "general",
    label: "Permission Umum / Lainnya",
    items: groupedPermissions.value.general,
  },
].filter((section) => section.items.length > 0));

const pageTitle = computed(() =>
  formMode.value === "create" ? "Tambah Role" : "Edit Role",
);

function resetForm() {
  form.nama = "";
  form.deskripsi = "";
  form.permission_ids = [];
}

function fillForm(role: RoleItem) {
  form.nama = role.nama ?? "";
  form.deskripsi = role.deskripsi ?? "";
  form.permission_ids = (role.permissions ?? []).map((item) => item.id);
}

function openCreateModal() {
  formMode.value = "create";
  selectedRoleId.value = "";
  resetForm();
  showFormModal.value = true;
}

function openEditModal(role: RoleItem) {
  formMode.value = "edit";
  selectedRoleId.value = role.id;
  fillForm(role);
  showFormModal.value = true;
}

function closeFormModal() {
  showFormModal.value = false;
}

function togglePermission(permissionId: string) {
  const exists = form.permission_ids.includes(permissionId);

  if (exists) {
    form.permission_ids = form.permission_ids.filter((id) => id !== permissionId);
    return;
  }

  form.permission_ids = [...form.permission_ids, permissionId];
}

async function submitForm() {
  if (formMode.value === "create") {
    await manageRoleStore.createRole({
      nama: form.nama,
      deskripsi: form.deskripsi,
      permission_ids: form.permission_ids,
    });
  } else {
    await manageRoleStore.updateRole(selectedRoleId.value, {
      nama: form.nama,
      deskripsi: form.deskripsi,
      permission_ids: form.permission_ids,
    });
  }

  showFormModal.value = false;
  await manageRoleStore.fetchRoles();
}

async function gotoUsers() {
  await navigateTo("/users");
}

onMounted(async () => {
  await Promise.all([
    manageRoleStore.fetchRoles(),
    manageRoleStore.fetchPermissions(),
  ]);
});
</script>

<template>
  <main class="min-h-screen bg-[#FBFAF8] text-[14px] text-[#2E1F18]">
    <Header brand-title="Management Role" brand-subtitle="Kelola role dan mapping permission" />

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center gap-3">
        <button type="button" aria-label="Back" @click="gotoUsers"
          class="flex h-8 w-8 items-center justify-center rounded-full border border-[#D8DEE8] bg-white text-[#566074] shadow-sm transition-all duration-200 hover:border-[#1A315B] hover:bg-slate-50 hover:text-[#1A315B]">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
            stroke="currentColor" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>

        <p class="text-sm font-semibold tracking-wide text-[#333d4e]">Management User</p>
      </div>

      <section class="rounded-2xl border border-[#EEE6DE] bg-white p-5">
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-[20px] font-bold">Daftar Role</h2>
            <p class="text-[#8A817A]">Kelola role dan permission bertingkat berdasarkan scope akses.</p>
          </div>

          <button class="rounded-full bg-[#4D392A] px-5 py-2.5 font-semibold text-white" @click="openCreateModal">
            + Tambah Role
          </button>
        </div>

        <div class="mb-4">
          <input v-model="search" type="text" placeholder="Cari role..."
            class="h-11 w-full rounded-xl border border-[#EEE6DE] px-4 outline-none placeholder:text-[#A6A29D]" />
        </div>

        <p v-if="manageRoleStore.errorMessage" class="mb-3 rounded-xl bg-red-50 px-4 py-3 text-red-600">
          {{ manageRoleStore.errorMessage }}
        </p>

        <div class="mb-4 rounded-xl border border-[#EEE6DE] bg-[#FFFCF8] p-4">
          <h3 class="text-[16px] font-bold text-[#4D392A]">Group Permission Bertingkat</h3>
          <p class="mt-1 text-[#8A817A]">
            Permission dikelompokkan ke 4 level utama agar assignment role lebih terstruktur.
          </p>

          <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div v-for="section in groupedPermissionSections" :key="section.key"
              class="rounded-lg border border-[#E7DDD3] bg-white p-3">
              <p class="text-sm font-semibold text-[#4D392A]">{{ section.label }}</p>
              <p class="mt-1 text-xs text-[#8A817A]">{{ section.items.length }} permission</p>
            </div>
            <div v-if="groupedPermissionSections.length === 0"
              class="rounded-lg border border-dashed border-[#E7DDD3] bg-white p-3 text-[#8A817A]">
              Belum ada data permission untuk dikelompokkan.
            </div>
          </div>
        </div>

        <div class="overflow-x-auto rounded-xl border border-[#EEE6DE]">
          <table class="min-w-full bg-white">
            <thead class="bg-[#F8F3EE] text-left text-[#4D392A]">
              <tr>
                <th class="px-4 py-3 font-bold">Nama</th>
                <th class="px-4 py-3 font-bold">Deskripsi</th>
                <th class="px-4 py-3 font-bold">Jumlah Permission</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="manageRoleStore.loadingList" class="border-t border-[#F0E8E0]">
                <td colspan="4" class="px-4 py-8 text-center text-[#8A817A]">
                  Memuat data role...
                </td>
              </tr>

              <tr v-for="item in filteredRoles" :key="item.id" class="border-t border-[#F0E8E0]">
                <td class="px-4 py-3">{{ item.nama }}</td>
                <td class="px-4 py-3">{{ item.deskripsi }}</td>
                <td class="px-4 py-3">{{ item.permissions?.length ?? 0 }}</td>
                <td class="px-4 py-3">
                  <button
                    class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 font-semibold text-[#4D392A]"
                    @click="openEditModal(item)">
                    Edit
                  </button>
                </td>
              </tr>

              <tr v-if="!manageRoleStore.loadingList && filteredRoles.length === 0" class="border-t border-[#F0E8E0]">
                <td colspan="4" class="px-4 py-8 text-center text-[#8A817A]">
                  Belum ada data role.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="showFormModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-4xl rounded-2xl bg-white p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-[18px] font-bold">{{ pageTitle }}</h3>
          <button class="text-[#8A817A]" @click="closeFormModal">✕</button>
        </div>

        <form class="grid grid-cols-1 gap-3 md:grid-cols-2" @submit.prevent="submitForm">
          <div>
            <label class="mb-1 block text-[#6F645B]">Nama Role</label>
            <input v-model="form.nama" required type="text"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">Deskripsi</label>
            <input v-model="form.deskripsi" required type="text"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div class="md:col-span-2">
            <label class="mb-2 block text-[#6F645B]">Permission Scope</label>
            <div class="max-h-80 overflow-y-auto rounded-xl border border-[#EEE6DE] p-3">
              <div v-if="manageRoleStore.loadingPermissions" class="text-[#8A817A]">
                Memuat data permission...
              </div>

              <div v-else-if="groupedPermissionSections.length === 0" class="text-[#8A817A]">
                Tidak ada data permission.
              </div>

              <div v-for="section in groupedPermissionSections" :key="`section-${section.key}`"
                class="mb-3 rounded-xl border border-[#EFE6DE] bg-[#FFFCF9] p-3">
                <p class="mb-2 text-sm font-bold text-[#4D392A]">{{ section.label }}</p>
                <div class="space-y-1.5">
                  <label v-for="permission in section.items" :key="permission.id"
                    class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 hover:bg-[#F8F3EE]">
                    <input type="checkbox" :checked="form.permission_ids.includes(permission.id)"
                      @change="togglePermission(permission.id)" />
                    <span class="font-semibold">{{ permission.kode }}</span>
                    <span class="text-[#8A817A]">
                      ({{ permission.resource }} - {{ permission.aksi }})
                    </span>
                  </label>
                </div>
              </div>
            </div>
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
  </main>
</template>

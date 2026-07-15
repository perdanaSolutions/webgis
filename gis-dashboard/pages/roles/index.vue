<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import { useManageRoleStore } from "~/stores/manageRoleStore";
import { dashboardStore } from '~/stores/dashboardStore'


defineOptions({
  name: "RolesManagementPage",
});

const manageRoleStore = useManageRoleStore();
const dashboardService = dashboardStore()


const search = ref("");
const showFormModal = ref(false);
const formMode = ref("create");
const selectedRoleId = ref("");
const searchQueryPerusahaan = ref("");

const activePermissionTab = ref("menu");

const form = reactive({
  nama: "",
  deskripsi: "",
  menu_ids: [],
  perusahaan_ids: [],
  estate_ids: [],
  transaksi_ids: [],
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

const allDataPerusahaan = computed(
  () => {
    if (!searchQueryPerusahaan.value) {
      return manageRoleStore.allDataPerusahaan ?? [];
    }
    return manageRoleStore.allDataPerusahaan.filter(perusahaan =>
      perusahaan.nama_pt.toLowerCase().includes(searchQueryPerusahaan.value.toLowerCase())
    )
  }


);
const allDataEstate = computed(
  () => manageRoleStore.allDataEstate ?? [],
);
const allDataTransaksi = computed(
  () => manageRoleStore.allDataTransaksi ?? [],
);

const pageTitle = computed(() =>
  formMode.value === "create" ? "Tambah Role" : "Edit Role",
);

function resetForm() {
  form.nama = "";
  form.deskripsi = "";
  form.menu_ids = [];
  activePermissionTab.value = "menu";
}

function fillForm(role) {
  form.nama = role.nama ?? "";
  form.deskripsi = role.deskripsi ?? "";
  // form.menu_ids = (role.permissions ?? []).map((item) => item.id);
  activePermissionTab.value = "menu";
}

function openCreateModal() {
  formMode.value = "create";
  selectedRoleId.value = "";
  resetForm();
  showFormModal.value = true;
}

function openEditModal(role) {
  formMode.value = "edit";
  selectedRoleId.value = role.id;
  fillForm(role);
  showFormModal.value = true;
}

function closeFormModal() {
  showFormModal.value = false;
}


async function submitForm() {
  if (formMode.value === "create") {
    // await manageRoleStore.createRole({
    //   nama: form.nama,
    //   deskripsi: form.deskripsi,
    //   permission_ids: form.permission_ids,
    // });
  } else {
    // await manageRoleStore.updateRole(selectedRoleId.value, {
    //   nama: form.nama,
    //   deskripsi: form.deskripsi,
    //   permission_ids: form.permission_ids,
    // });
  }

  showFormModal.value = false;
  await manageRoleStore.fetchRoles();
}

async function gotoUsers() {
  await navigateTo("/users");
}

const changeContent = (value) => {
  activePermissionTab.value = value
};

const toggleAllMenu = () => {
  const isAllSelected = form.menu_ids.length === manageRoleStore.allDataMenu.length;
  if (isAllSelected) {
    // Jika sudah centang semua, maka KOSONGKAN (uncheck all)
    form.menu_ids = [];
  } else {
    // Jika belum semua, maka MASUKKAN SEMUA ID ke dalam array (check all)
    form.menu_ids = manageRoleStore.allDataMenu.map(menu => menu.id);
  }
};

const toggleAllPerusahaan = () => {
  const isAllSelected = form.perusahaan_ids.length === allDataPerusahaan.value.length; // sesuaikan jika allDataPerusahaan adalah ref (.value)
  if (isAllSelected) {
    form.perusahaan_ids = [];
  } else {
    form.perusahaan_ids = allDataPerusahaan.value.map(p => p.id);
  }
};

const toggleAllTransaksi = () => {
  const isAllSelected = form.transaksi_ids.length === allDataTransaksi.value.length; // sesuaikan jika allDataTransaksi adalah ref (.value)
  if (isAllSelected) {
    form.transaksi_ids = [];
  } else {
    form.transaksi_ids = allDataTransaksi.value.map(t => t.id);
  }
};

const toggleAllEstate = () => { };

const togglePermission = (id) => {
  let targetArray = [];

  // Tentukan target array berdasarkan tab yang aktif saat ini
  if (activePermissionTab.value === 'menu') {
    targetArray = form.menu_ids;
  } else if (activePermissionTab.value === 'perusahaan') {
    targetArray = form.perusahaan_ids;
  } else if (activePermissionTab.value === 'transaksi') {
    targetArray = form.transaksi_ids;
  }

  // Cek apakah ID sudah ada di dalam array
  const index = targetArray.indexOf(id);
  if (index > -1) {
    targetArray.splice(index, 1); // Jika sudah ada, hapus (uncheck)
  } else {
    targetArray.push(id); // Jika belum ada, tambahkan (check)
  }
};

onMounted(async () => {
  await Promise.all([
    manageRoleStore.fetchRoles(),
    manageRoleStore.initDataMenu(),
    manageRoleStore.initDataPerusahaan(),
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

        <p class="text-sm font-semibold tracking-wide text-[#333d4e]">Management Role</p>
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

          <div class="md:col-span-2 rounded-xl border border-[#EEE6DE] p-4">
            <div class="mb-4 flex flex-wrap gap-2 border-b border-[#EEE6DE] pb-3">
              <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'menu'
                ? 'bg-[#4D392A] text-white'
                : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="changeContent('menu')">
                Akses Menu
              </button>
              <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'perusahaan'
                ? 'bg-[#4D392A] text-white'
                : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="changeContent('perusahaan')">
                Akses Perusahaan dan Akses estate
              </button>
              <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'transaksi'
                ? 'bg-[#4D392A] text-white'
                : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="changeContent('transaksi')">
                Akses transaksi
              </button>
            </div>

            <div v-show="activePermissionTab === 'menu'" class="rounded-xl border border-[#EEE6DE] p-4">
              <div class="mb-3 flex items-center justify-between gap-2">
                <p class="font-semibold text-[#4D392A]">List Menu</p>
                <button type="button"
                  class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm font-semibold text-[#4D392A]"
                  @click="toggleAllMenu">
                  Ceklis Semua
                </button>
              </div>

              <div v-if="!manageRoleStore.allDataMenu.length" class="text-[#8A817A]">
                Belum ada data permission menu.
              </div>

              <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                <label v-for="menu in manageRoleStore.allDataMenu" :key="menu.id"
                  class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                  <input :checked="form.menu_ids.includes(menu.id)" type="checkbox" class="h-4 w-4"
                    @change="togglePermission(menu.id)" />
                  <span>{{ menu.title }}</span>
                </label>
              </div>
            </div>

            <div v-show="activePermissionTab === 'perusahaan'" class="rounded-xl border border-[#EEE6DE] p-4">
              <div class="mb-3 flex items-center justify-between gap-2">

                <input v-model="searchQueryPerusahaan" type="text" placeholder="Cari perusahaan..."
                  class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm text-[#4D392A] focus:outline-none focus:ring-1 focus:ring-[#4D392A]" />

                <button type="button"
                  class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm font-semibold text-[#4D392A]"
                  @click="toggleAllPerusahaan">
                  Ceklis Semua
                </button>
              </div>

              <div v-if="!allDataPerusahaan.length" class="text-[#8A817A]">
                Belum ada data perusahaan master data.
              </div>

              <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                <label v-for="perusahaan in allDataPerusahaan" :key="perusahaan.id"
                  class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                  <input :checked="form.perusahaan_ids.includes(perusahaan.id)" type="checkbox" class="h-4 w-4"
                    @change="togglePermission(perusahaan.id)" />
                  <span>{{ perusahaan.nama_pt }}</span>
                </label>
              </div>
            </div>

            <div v-show="activePermissionTab === 'transaksi'" class="rounded-xl border border-[#EEE6DE] p-4">
              <div class="mb-3 flex items-center justify-between gap-2">
                <p class="font-semibold text-[#4D392A]">List data transaksi</p>
                <button type="button"
                  class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm font-semibold text-[#4D392A]"
                  @click="toggleAllTransaksi">
                  Ceklis Semua
                </button>
              </div>

              <div v-if="!allDataTransaksi.length" class="text-[#8A817A]">
                Belum ada data transaksi.
              </div>

              <div v-else class="space-y-2">
                <label v-for="transaksi in allDataTransaksi" :key="transaksi.id"
                  class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                  <input :checked="form.transaksi_ids.includes(transaksi.id)" type="checkbox" class="h-4 w-4"
                    @change="togglePermission(transaksi.id)" />
                  <span>{{ transaksi.kode }}</span>
                </label>
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

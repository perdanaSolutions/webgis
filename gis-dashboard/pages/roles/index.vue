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

const searchQueryArea = ref("");
const searchQueryPerusahaan = ref("");
const searchQueryEstate = ref("");
const searchQueryAfdeling = ref("");

const activePermissionTab = ref("menu");

const form = reactive({
  nama: "",
  deskripsi: "",
  menu_ids: [],
  area_ids: [],
  perusahaan_ids: [],
  estate_ids: [],
  afdeling_ids: [],
  transaksi_ids: [],
});

const perusahaanByAreaMap = ref({});
const estateByPerusahaanMap = ref({});
const afdelingByEstateMap = ref({});

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

const allDataArea = computed(() => {
  const areas = manageRoleStore.allDataArea ?? [];
  if (!searchQueryArea.value) return areas;

  const keyword = searchQueryArea.value.toLowerCase();
  return areas.filter((area) => {
    const name = String(area?.nama_area ?? area?.nama ?? area?.title ?? "").toLowerCase();
    const code = String(getAreaId(area)).toLowerCase();
    return name.includes(keyword) || code.includes(keyword);
  });
});

const selectedAreas = computed(() => {
  const selectedIds = new Set(form.area_ids.map((id) => String(id)));
  return (manageRoleStore.allDataArea ?? []).filter((area) =>
    selectedIds.has(String(area?.id)),
  );
});

const groupedPerusahaanByArea = computed(() => {
  return selectedAreas.value.map((area) => {
    const areaKey = getAreaId(area);
    return {
      area,
      areaKey,
      perusahaan: perusahaanByAreaMap.value[areaKey] ?? [],
    };
  });
});

const selectedPerusahaanList = computed(() => {
  const selectedIds = new Set(form.perusahaan_ids.map((id) => String(id)));
  return groupedPerusahaanByArea.value
    .flatMap((group) => group.perusahaan)
    .filter((item) => selectedIds.has(String(item?.id)));
});

const groupedEstateByPerusahaan = computed(() => {
  return selectedPerusahaanList.value.map((perusahaan) => {
    const perusahaanKey = getPerusahaanCode(perusahaan);
    return {
      perusahaan,
      perusahaanKey,
      estates: estateByPerusahaanMap.value[perusahaanKey] ?? [],
    };
  });
});

const selectedEstateList = computed(() => {
  const selectedIds = new Set(form.estate_ids.map((id) => String(id)));
  return groupedEstateByPerusahaan.value
    .flatMap((group) => group.estates)
    .filter((item) => selectedIds.has(String(getEstateCode(item))));
});

const groupedAfdelingByEstate = computed(() => {
  return selectedEstateList.value.map((estate) => {
    const estateKey = getEstateCode(estate);
    return {
      estate,
      estateKey,
      afdelings: afdelingByEstateMap.value[estateKey] ?? [],
    };
  });
});

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
  form.area_ids = [];
  form.perusahaan_ids = [];
  form.estate_ids = [];
  form.afdeling_ids = [];
  form.transaksi_ids = [];

  searchQueryArea.value = "";
  searchQueryPerusahaan.value = "";
  searchQueryEstate.value = "";
  searchQueryAfdeling.value = "";

  perusahaanByAreaMap.value = {};
  estateByPerusahaanMap.value = {};
  afdelingByEstateMap.value = {};

  activePermissionTab.value = "menu";
}

async function fillForm(role) {
  form.nama = role.nama ?? "";
  form.deskripsi = role.deskripsi ?? "";
  form.menu_ids = [];
  form.area_ids = [];
  form.perusahaan_ids = [];
  form.estate_ids = [];
  form.afdeling_ids = [];
  form.transaksi_ids = [];
  perusahaanByAreaMap.value = {};
  estateByPerusahaanMap.value = {};
  afdelingByEstateMap.value = {};
  activePermissionTab.value = "menu";

  const existingAkses = await manageRoleStore.getExistingAksesByRole(role.id);

  form.menu_ids = (existingAkses?.menu ?? [])
    .map((item) => String(item?.menu_id ?? ""))
    .filter((id) => !!id);

  const dataAkses = existingAkses?.data ?? [];
  if (dataAkses.length > 0) {
    const perusahaanCodes = Array.from(
      new Set(dataAkses.map((item) => String(item?.kode_pt ?? "")).filter(Boolean)),
    );

    const selectedPerusahaan = (manageRoleStore.allDataPerusahaan ?? []).filter(
      (item) => perusahaanCodes.includes(String(getPerusahaanCode(item))),
    );
    form.perusahaan_ids = selectedPerusahaan.map((item) => String(item.id));

    form.estate_ids = dataAkses
      .map((item) => String(item?.kode_est ?? ""))
      .filter((id) => !!id);

    form.afdeling_ids = dataAkses
      .map((item) => String(item?.kode_afd ?? ""))
      .filter((id) => !!id);
  }

  form.transaksi_ids = (existingAkses?.transaksi ?? [])
    .map((item) => String(item?.nama_table_transaksi ?? ""))
    .filter((id) => !!id);
}

function openCreateModal() {
  formMode.value = "create";
  selectedRoleId.value = "";
  resetForm();
  showFormModal.value = true;
}

async function openEditModal(role) {
  formMode.value = "edit";
  selectedRoleId.value = role.id;
  showFormModal.value = true;
  await fillForm(role);
}

function closeFormModal() {
  showFormModal.value = false;
}

async function submitForm() {
  if (formMode.value === "create") {
    await manageRoleStore.createRole(form);
  } else {
    await manageRoleStore.updateRole(selectedRoleId.value, form);
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
    form.menu_ids = [];
  } else {
    form.menu_ids = manageRoleStore.allDataMenu.map(menu => menu.id);
  }
};

const getAreaId = (area) =>
  String(area?.area_id ?? "");

const getPerusahaanCode = (perusahaan) =>
  String(perusahaan?.kode_pt ?? perusahaan?.kode ?? perusahaan?.id ?? "");

const getEstateCode = (estate) =>
  String(estate?.kode_estate ?? estate?.kode ?? estate?.id ?? "");

const getAfdelingCode = (afdeling) =>
  String(afdeling?.kode_afd ?? afdeling?.kode_afdeling ?? afdeling?.kode ?? afdeling?.id ?? "");

const getTransaksiCode = (transaksi) =>
  String(transaksi?.id ?? transaksi?.nama_table_transaksi ?? transaksi ?? "");

const pruneDownstreamSelections = () => {
  const availablePerusahaanMap = new Map();
  groupedPerusahaanByArea.value.forEach((group) => {
    (group.perusahaan ?? []).forEach((item) => {
      availablePerusahaanMap.set(String(item?.id), item);
    });
  });

  const validPerusahaanIds = new Set(availablePerusahaanMap.keys());
  form.perusahaan_ids = form.perusahaan_ids.filter((id) =>
    validPerusahaanIds.has(String(id)),
  );

  const selectedPerusahaanCodes = new Set(
    form.perusahaan_ids
      .map((id) => availablePerusahaanMap.get(String(id)))
      .filter(Boolean)
      .map((item) => String(getPerusahaanCode(item))),
  );

  Object.keys(estateByPerusahaanMap.value).forEach((kodePt) => {
    if (!selectedPerusahaanCodes.has(String(kodePt))) {
      delete estateByPerusahaanMap.value[kodePt];
    }
  });

  const availableEstateCodes = new Set();
  Object.values(estateByPerusahaanMap.value).forEach((estates) => {
    (estates ?? []).forEach((estate) => {
      availableEstateCodes.add(String(getEstateCode(estate)));
    });
  });

  form.estate_ids = form.estate_ids.filter((id) =>
    availableEstateCodes.has(String(id)),
  );

  const selectedEstateCodes = new Set(form.estate_ids.map((id) => String(id)));
  Object.keys(afdelingByEstateMap.value).forEach((kodeEst) => {
    if (!selectedEstateCodes.has(String(kodeEst))) {
      delete afdelingByEstateMap.value[kodeEst];
    }
  });

  const availableAfdelingCodes = new Set();
  Object.values(afdelingByEstateMap.value).forEach((afdelings) => {
    (afdelings ?? []).forEach((item) => {
      availableAfdelingCodes.add(String(getAfdelingCode(item)));
    });
  });

  form.afdeling_ids = form.afdeling_ids.filter((id) =>
    availableAfdelingCodes.has(String(id)),
  );
};

const toggleArea = async (area) => {
  const id = String(area?.id ?? "");
  if (!id) return;

  const areaId = getAreaId(area);
  const index = form.area_ids.indexOf(id);

  if (index > -1) {
    form.area_ids.splice(index, 1);

    delete perusahaanByAreaMap.value[areaId];
    pruneDownstreamSelections();
  } else {
    form.area_ids.push(id);
    if (!perusahaanByAreaMap.value[areaId]) {
      const data = await manageRoleStore.initDataPerusahaanByArea(areaId);
      perusahaanByAreaMap.value[areaId] = data ?? [];
    }
    pruneDownstreamSelections();
  }
};

const togglePerusahaan = async (perusahaan) => {
  const id = String(perusahaan?.id ?? "");
  if (!id) return;

  const perusahaanCode = getPerusahaanCode(perusahaan);
  const index = form.perusahaan_ids.indexOf(id);

  if (index > -1) {
    form.perusahaan_ids.splice(index, 1);
    delete estateByPerusahaanMap.value[perusahaanCode];
    pruneDownstreamSelections();
  } else {
    form.perusahaan_ids.push(id);
    if (!estateByPerusahaanMap.value[perusahaanCode]) {
      const data = await manageRoleStore.initDataEstate(perusahaanCode);
      estateByPerusahaanMap.value[perusahaanCode] = data ?? [];
    }
    pruneDownstreamSelections();
  }
};

const toggleEstate = async (estate) => {
  const code = String(getEstateCode(estate));
  if (!code) return;

  const index = form.estate_ids.indexOf(code);
  if (index > -1) {
    form.estate_ids.splice(index, 1);
    delete afdelingByEstateMap.value[code];
    pruneDownstreamSelections();
  } else {
    form.estate_ids.push(code);
    if (!afdelingByEstateMap.value[code]) {
      const data = await manageRoleStore.initDataAfdelingByEstate(code);
      afdelingByEstateMap.value[code] = data ?? [];
    }
    pruneDownstreamSelections();
  }
};

const toggleAfdeling = (id) => {
  const code = String(id ?? "");
  if (!code) return;

  const index = form.afdeling_ids.indexOf(code);
  if (index > -1) {
    form.afdeling_ids.splice(index, 1);
  } else {
    form.afdeling_ids.push(code);
  }
};

const toggleAllTransaksi = () => {
  const transaksiCodes = allDataTransaksi.value
    .map((transaksi) => getTransaksiCode(transaksi))
    .filter((code) => !!code);

  const isAllSelected =
    transaksiCodes.length > 0 &&
    transaksiCodes.every((code) => form.transaksi_ids.includes(code));

  if (isAllSelected) {
    form.transaksi_ids = form.transaksi_ids.filter(
      (id) => !transaksiCodes.includes(String(id)),
    );
  } else {
    const merged = new Set([
      ...form.transaksi_ids.map((id) => String(id)),
      ...transaksiCodes,
    ]);
    form.transaksi_ids = Array.from(merged);
  }
};

const togglePermission = (id) => {
  let targetArray = [];

  if (activePermissionTab.value === "menu") {
    targetArray = form.menu_ids;
  } else if (activePermissionTab.value === "transaksi") {
    targetArray = form.transaksi_ids;
  }

  const index = targetArray.indexOf(id);
  if (index > -1) {
    targetArray.splice(index, 1);
  } else {
    targetArray.push(id);
  }
};

onMounted(async () => {
  await Promise.all([
    manageRoleStore.fetchRoles(),
    manageRoleStore.initDataMenu(),
    manageRoleStore.initDataArea(),
    manageRoleStore.initDataTableTransaksi(),
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
                <th class="px-4 py-3 font-bold">Menu</th>
                <th class="px-4 py-3 font-bold">Perusahaan & Estate</th>
                <th class="px-4 py-3 font-bold">Transaksi</th>
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
                <td class="px-4 py-3">{{ item.akses_menu?.length ?? 0 }}</td>
                <td class="px-4 py-3">{{ item.akses_data?.length ?? 0 }}</td>
                <td class="px-4 py-3">{{ item.akses_transaksi?.length ?? 0 }}</td>
                <td class="px-4 py-3">
                  <button v-if="item.nama != 'superadmin'"
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

          <div class="md:col-span-2 rounded-xl border border-[#EEE6DE] p-4 max-h-[70vh] overflow-y-auto">
            <div class="mb-4 flex flex-wrap gap-2 border-b border-[#EEE6DE] pb-3">
              <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'menu'
                ? 'bg-[#4D392A] text-white'
                : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="changeContent('menu')">
                Akses Menu
              </button>
              <button type="button" class="rounded-xl px-4 py-2 text-sm font-semibold transition" :class="activePermissionTab === 'perusahaan'
                ? 'bg-[#4D392A] text-white'
                : 'border border-[#DDD1C7] bg-[#FFF8F2] text-[#4D392A]'" @click="changeContent('perusahaan')">
                Akses Data
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
              <div class="mb-4 rounded-xl border border-[#EEE6DE] p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-[#4D392A]">Level 1 - Area</p>
                  <!-- <input v-model="searchQueryArea" type="text" placeholder="Cari area..."
                    class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm text-[#4D392A] focus:outline-none focus:ring-1 focus:ring-[#4D392A]" /> -->
                </div>
                <div v-if="!allDataArea.length" class="text-[#8A817A]">
                  Belum ada data area.
                </div>
                <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <label v-for="area in allDataArea" :key="area.id ?? area.kode_area ?? area.kode"
                    class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                    <input :checked="form.area_ids.includes(String(area.id))" type="checkbox" class="h-4 w-4"
                      @change="toggleArea(area)" />
                    <span>{{ area.nama ?? '' }}</span>
                  </label>
                </div>
              </div>

              <div v-if="groupedPerusahaanByArea.length" class="mb-4 rounded-xl border border-[#EEE6DE] p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-[#4D392A]">Level 2 - Perusahaan</p>
                  <!-- <input v-model="searchQueryPerusahaan" type="text" placeholder="Cari perusahaan..."
                    class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm text-[#4D392A] focus:outline-none focus:ring-1 focus:ring-[#4D392A]" /> -->
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedPerusahaanByArea" :key="group.areaKey"
                    class="rounded-lg border border-[#EEE6DE] p-3">
                    <p class="mb-2 text-sm font-semibold text-[#6F645B]">
                      Area: {{ group.area?.nama_area ?? group.area?.nama ?? group.areaKey }}
                    </p>
                    <div v-if="!group.perusahaan.length" class="text-[#8A817A]">
                      Tidak ada perusahaan untuk area ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="perusahaan in group.perusahaan" :key="perusahaan.id"
                        class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                        <input :checked="form.perusahaan_ids.includes(String(perusahaan.id))" type="checkbox"
                          class="h-4 w-4" @change="togglePerusahaan(perusahaan)" />
                        <span>{{ perusahaan.nama_pt ?? perusahaan.nama ?? perusahaan.title ??
                          getPerusahaanCode(perusahaan) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedEstateByPerusahaan.length" class="mb-4 rounded-xl border border-[#EEE6DE] p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-[#4D392A]">Level 3 - Estate</p>
                  <!-- <input v-model="searchQueryEstate" type="text" placeholder="Cari estate..."
                    class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm text-[#4D392A] focus:outline-none focus:ring-1 focus:ring-[#4D392A]" /> -->
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedEstateByPerusahaan" :key="group.perusahaanKey"
                    class="rounded-lg border border-[#EEE6DE] p-3">
                    <p class="mb-2 text-sm font-semibold text-[#6F645B]">
                      Perusahaan: {{ group.perusahaan?.nama_pt ?? group.perusahaan?.nama ?? group.perusahaanKey }}
                    </p>
                    <div v-if="!group.estates.length" class="text-[#8A817A]">
                      Tidak ada estate untuk perusahaan ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="estate in group.estates" :key="getEstateCode(estate)"
                        class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                        <input :checked="form.estate_ids.includes(getEstateCode(estate))" type="checkbox"
                          class="h-4 w-4" @change="toggleEstate(estate)" />
                        <span>{{ estate.nama_estate ?? estate.nama ?? estate.title ?? getEstateCode(estate) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedAfdelingByEstate.length" class="rounded-xl border border-[#EEE6DE] p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-[#4D392A]">Level 4 - Afdeling</p>
                  <!-- <input v-model="searchQueryAfdeling" type="text" placeholder="Cari afdeling..."
                    class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 text-sm text-[#4D392A] focus:outline-none focus:ring-1 focus:ring-[#4D392A]" /> -->
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedAfdelingByEstate" :key="group.estateKey"
                    class="rounded-lg border border-[#EEE6DE] p-3">
                    <p class="mb-2 text-sm font-semibold text-[#6F645B]">
                      Estate: {{ group.estate?.nama_estate ?? group.estate?.nama ?? group.estateKey }}
                    </p>
                    <div v-if="!group.afdelings.length" class="text-[#8A817A]">
                      Tidak ada afdeling untuk estate ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="afdeling in group.afdelings" :key="getAfdelingCode(afdeling)"
                        class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                        <input :checked="form.afdeling_ids.includes(getAfdelingCode(afdeling))" type="checkbox"
                          class="h-4 w-4" @change="toggleAfdeling(getAfdelingCode(afdeling))" />
                        <span>{{ afdeling.nama_afdeling ?? afdeling.nama ?? afdeling.title ?? getAfdelingCode(afdeling)
                          }}</span>
                      </label>
                    </div>
                  </div>
                </div>
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

              <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                <label v-for="transaksi in allDataTransaksi" :key="getTransaksiCode(transaksi)"
                  class="flex items-center gap-2 rounded-lg border border-[#EEE6DE] p-2">
                  <input :checked="form.transaksi_ids.includes(getTransaksiCode(transaksi))" type="checkbox"
                    class="h-4 w-4" @change="togglePermission(getTransaksiCode(transaksi))" />
                  <span>{{ transaksi?.title ?? transaksi?.nama_table_transaksi ?? transaksi }}</span>
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

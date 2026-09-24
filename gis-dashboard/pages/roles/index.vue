<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import { useManageRoleStore } from "~/stores/manageRoleStore";
import {
  transformDataToForm,
} from "~/stores/roleStoreExtractData";
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
const loadingHierarchy = ref(false);

const form = reactive({
  nama: "",
  deskripsi: "",
  menu_ids: [],
  area_ids: [],
  perusahaan_ids: [],
  estate_ids: [],
  afdeling_ids: [],
  transaksi_ids: [],
  selected_area_items: [],
  selected_perusahaan_items: [],
  selected_estate_items: [],
  selected_afdeling_items: [],
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
  form.selected_area_items = [];
  form.selected_perusahaan_items = [];
  form.selected_estate_items = [];
  form.selected_afdeling_items = [];

  searchQueryArea.value = "";
  searchQueryPerusahaan.value = "";
  searchQueryEstate.value = "";
  searchQueryAfdeling.value = "";

  perusahaanByAreaMap.value = {};
  estateByPerusahaanMap.value = {};
  afdelingByEstateMap.value = {};

  activePermissionTab.value = "menu";
}

function resolveAreaIdsForForm(areaIds = [], selectedAreaItems = []) {
  const areas = manageRoleStore.allDataArea ?? [];

  const resolveOne = (id, areaCode = "") => {
    const idStr = String(id ?? "");
    if (areas.some((area) => String(area?.id) === idStr)) return idStr;

    const code = String(areaCode || id);
    const matchedArea = areas.find((area) => {
      const candidates = [
        getAreaId(area),
        area?.kode_area,
        area?.area_id,
        area?.id_area,
        area?.id,
      ].map((value) => String(value ?? ""));

      return candidates.includes(code);
    });

    return matchedArea ? String(matchedArea.id) : idStr;
  };

  if (selectedAreaItems.length > 0) {
    return selectedAreaItems.map((item) =>
      resolveOne(item?.id, item?.area_id),
    );
  }

  return areaIds.map((id) => resolveOne(id));
}

async function fillForm(role) {
  perusahaanByAreaMap.value = {};
  estateByPerusahaanMap.value = {};
  afdelingByEstateMap.value = {};

  const existingAkses = await manageRoleStore.getExistingAksesByRole(role.id);

  const result = transformDataToForm(existingAkses?.data ?? [], {
    nama: "",
    deskripsi: "",
  });

  Object.assign(form, result);

  form.nama = String(role.nama ?? "").toUpperCase();
  form.deskripsi = String(role.deskripsi ?? "").toUpperCase();
  activePermissionTab.value = "menu";

  form.menu_ids = (existingAkses?.menu ?? [])
    .map((item) => String(item?.menu_id ?? ""))
    .filter((id) => !!id);

  form.transaksi_ids = (existingAkses?.transaksi ?? [])
    .map((item) => String(item?.nama_table_transaksi ?? ""))
    .filter((id) => !!id);

  form.area_ids = resolveAreaIdsForForm(
    result.area_ids,
    result.selected_area_items,
  );

  form.afdeling_ids = normalizeAfdelingIds(
    result.afdeling_ids,
    result.selected_afdeling_items,
  );

  await loadHierarchyForEdit();
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
  form.nama = String(form.nama ?? "").toUpperCase();
  form.deskripsi = String(form.deskripsi ?? "").toUpperCase();

  if (formMode.value === "create") {
    await manageRoleStore.createRole(form);
  } else {
    await manageRoleStore.updateRole(selectedRoleId.value, form);
  }

  showFormModal.value = false;
  await manageRoleStore.fetchRoles();
}

function onNamaInput(event) {
  form.nama = String(event.target?.value ?? "").toUpperCase();
}

function onDeskripsiInput(event) {
  form.deskripsi = String(event.target?.value ?? "").toUpperCase();
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
  String(area?.area_id ?? area?.kode_area ?? area?.id_area ?? area?.id ?? "");

const getPerusahaanCode = (perusahaan) =>
  String(
    perusahaan?.kode_pt ??
    perusahaan?.kode ??
    perusahaan?.id_perusahaan ??
    perusahaan?.id ??
    "",
  );

const getEstateCode = (estate) =>
  String(estate?.kode_est ?? estate?.id_estate ?? estate?.id ?? "");

const AFDELING_KEY_SEPARATOR = "::";

const getAfdelingSelectionKey = (estateCode, afdelingCode) => {
  const kodeEst = String(estateCode ?? "");
  const kodeAfd = String(afdelingCode ?? "");
  if (!kodeEst || !kodeAfd) return "";
  return `${kodeEst}${AFDELING_KEY_SEPARATOR}${kodeAfd}`;
};

const parseAfdelingSelectionKey = (key) => {
  const [kodeEst = "", kodeAfd = ""] = String(key ?? "").split(
    AFDELING_KEY_SEPARATOR,
  );
  return { kodeEst, kodeAfd };
};

const isAfdelingSelected = (estateCode, afdelingCode) =>
  form.afdeling_ids.includes(
    getAfdelingSelectionKey(estateCode, afdelingCode),
  );

const normalizeAfdelingIds = (afdelingIds = [], selectedAfdelingItems = []) => {
  if (selectedAfdelingItems.length > 0) {
    return selectedAfdelingItems
      .map((item) =>
        getAfdelingSelectionKey(item?.kode_est, item?.kode_afd),
      )
      .filter(Boolean);
  }

  return afdelingIds
    .map((id) => {
      const key = String(id ?? "");
      if (key.includes(AFDELING_KEY_SEPARATOR)) return key;

      const { kodeAfd } = parseAfdelingSelectionKey(key);
      return kodeAfd || key;
    })
    .filter(Boolean);
};

const getAfdelingCode = (afdeling) =>
  String(
    afdeling?.kode_afd ??
    afdeling?.kode_afdeling ??
    afdeling?.id_afdeling ??
    afdeling?.kode ??
    afdeling?.id ??
    "",
  );

const getTransaksiCode = (transaksi) =>
  String(transaksi?.id ?? transaksi?.nama_table_transaksi ?? transaksi ?? "");

const syncSelectedItemsFromIds = () => {
  const areaMapById = new Map(
    (manageRoleStore.allDataArea ?? []).map((area) => [String(area?.id ?? ""), area]),
  );

  form.selected_area_items = form.area_ids
    .map((id) => areaMapById.get(String(id)))
    .filter(Boolean)
    .map((area) => ({
      id: String(area?.id ?? ""),
      area_id: String(getAreaId(area)),
      nama_area: String(area?.nama_area ?? area?.nama ?? ""),
    }));

  const perusahaanMapById = new Map();
  Object.values(perusahaanByAreaMap.value).forEach((perusahaanList) => {
    (perusahaanList ?? []).forEach((item) => {
      perusahaanMapById.set(String(item?.id ?? ""), item);
    });
  });

  form.selected_perusahaan_items = form.perusahaan_ids
    .map((id) => perusahaanMapById.get(String(id)))
    .filter(Boolean)
    .map((item) => ({
      id: String(item?.id ?? ""),
      kode_pt: String(getPerusahaanCode(item)),
      kode_area: String(item?.kode_area ?? item?.area_id ?? item?.area?.area_id ?? ""),
      nama_pt: String(item?.nama_pt ?? item?.nama_perusahaan ?? item?.nama ?? ""),
    }));

  const estateMapByCode = new Map();
  Object.values(estateByPerusahaanMap.value).forEach((estateList) => {
    (estateList ?? []).forEach((item) => {
      estateMapByCode.set(String(getEstateCode(item)), item);
    });
  });

  form.selected_estate_items = form.estate_ids
    .map((code) => estateMapByCode.get(String(code)))
    .filter(Boolean)
    .map((item) => ({
      id: String(item?.id ?? ""),
      kode_est: String(getEstateCode(item)),
      kode_pt: String(item?.kode_pt ?? item?.pt_kode ?? ""),
      nama_estate: String(item?.nama_estate ?? item?.nama ?? ""),
    }));

  const afdelingMapByKey = new Map();
  Object.entries(afdelingByEstateMap.value).forEach(([estateCode, afdelingList]) => {
    (afdelingList ?? []).forEach((item) => {
      const kodeAfd = String(getAfdelingCode(item));
      const selectionKey = getAfdelingSelectionKey(estateCode, kodeAfd);
      if (!selectionKey) return;
      afdelingMapByKey.set(selectionKey, { ...item, _estateCode: estateCode });
    });
  });

  form.selected_afdeling_items = form.afdeling_ids
    .map((key) => {
      const selectionKey = String(key ?? "");
      const mappedItem = afdelingMapByKey.get(selectionKey);
      if (mappedItem) return mappedItem;

      const { kodeEst, kodeAfd } = parseAfdelingSelectionKey(selectionKey);
      if (!kodeEst || !kodeAfd) return null;

      const estateAfdelings = afdelingByEstateMap.value[kodeEst] ?? [];
      return estateAfdelings.find(
        (item) => String(getAfdelingCode(item)) === kodeAfd,
      );
    })
    .filter(Boolean)
    .map((item) => ({
      id: String(item?.id ?? ""),
      kode_afd: String(getAfdelingCode(item)),
      kode_est: String(item?.kode_est ?? item?._estateCode ?? ""),
      nama_afdeling: String(item?.nama_afdeling ?? item?.nama ?? getAfdelingCode(item)),
    }));
};

const loadPerusahaanMapsForAreas = async (areaIds = []) => {
  const selectedAreaSet = new Set((areaIds ?? []).map((id) => String(id)));
  const selectedAreasLocal = (manageRoleStore.allDataArea ?? []).filter((area) =>
    selectedAreaSet.has(String(area?.id ?? "")),
  );

  for (const area of selectedAreasLocal) {
    const areaCode = String(getAreaId(area));
    if (!areaCode || perusahaanByAreaMap.value[areaCode]) continue;

    const data = await manageRoleStore.initDataPerusahaanByArea(areaCode);
    perusahaanByAreaMap.value[areaCode] = data ?? [];
  }

  return selectedAreasLocal;
};

const loadHierarchyForEdit = async () => {
  loadingHierarchy.value = true;
  try {
    const selectedAreasLocal = await loadPerusahaanMapsForAreas(form.area_ids);
    const selectedPerusahaanIdSet = new Set(
      form.perusahaan_ids.map((id) => String(id)),
    );
    const perusahaanCodesToLoad = new Set(
      form.selected_perusahaan_items
        .map((item) => String(item?.kode_pt ?? ""))
        .filter(Boolean),
    );

    for (const area of selectedAreasLocal) {
      const areaCode = String(getAreaId(area));
      const perusahaanList = perusahaanByAreaMap.value[areaCode] ?? [];

      for (const perusahaan of perusahaanList) {
        if (!selectedPerusahaanIdSet.has(String(perusahaan?.id ?? ""))) continue;

        const perusahaanCode = String(getPerusahaanCode(perusahaan));
        if (perusahaanCode) perusahaanCodesToLoad.add(perusahaanCode);
      }
    }

    for (const perusahaanCode of perusahaanCodesToLoad) {
      if (estateByPerusahaanMap.value[perusahaanCode]) continue;

      const estates = await manageRoleStore.initDataEstate(perusahaanCode);
      estateByPerusahaanMap.value[perusahaanCode] = estates ?? [];
    }

    const selectedEstateSet = new Set(form.estate_ids.map((id) => String(id)));
    for (const perusahaanCode of perusahaanCodesToLoad) {
      const estateList = estateByPerusahaanMap.value[perusahaanCode] ?? [];

      for (const estate of estateList) {
        const estateCode = String(getEstateCode(estate));
        if (!estateCode || !selectedEstateSet.has(estateCode)) continue;
        if (afdelingByEstateMap.value[estateCode]) continue;

        const afdelings = await manageRoleStore.initDataAfdelingByEstate(estateCode);
        afdelingByEstateMap.value[estateCode] = afdelings ?? [];
      }
    }

    syncSelectedItemsFromIds();
    pruneDownstreamSelections();
  } finally {
    loadingHierarchy.value = false;
  }
};

const autoSelectHierarchyFromAreas = async (areaIds = []) => {
  loadingHierarchy.value = true;
  try {
    const selectedAreasLocal = await loadPerusahaanMapsForAreas(areaIds);

    const perusahaanIds = [];
    const perusahaanCodes = [];
    for (const area of selectedAreasLocal) {
      const areaCode = String(getAreaId(area));
      const perusahaanList = perusahaanByAreaMap.value[areaCode] ?? [];

      for (const perusahaan of perusahaanList) {
        const perusahaanId = String(perusahaan?.id ?? "");
        const perusahaanCode = String(getPerusahaanCode(perusahaan));
        if (perusahaanId) perusahaanIds.push(perusahaanId);
        if (perusahaanCode) perusahaanCodes.push(perusahaanCode);

        if (perusahaanCode && !estateByPerusahaanMap.value[perusahaanCode]) {
          const estates = await manageRoleStore.initDataEstate(perusahaanCode);
          estateByPerusahaanMap.value[perusahaanCode] = estates ?? [];
        }
      }
    }

    form.perusahaan_ids = Array.from(new Set(perusahaanIds));

    const estateCodes = [];
    for (const perusahaanCode of Array.from(new Set(perusahaanCodes))) {
      const estateList = estateByPerusahaanMap.value[perusahaanCode] ?? [];
      for (const estate of estateList) {
        const estateCode = String(getEstateCode(estate));
        if (!estateCode) continue;
        estateCodes.push(estateCode);

        if (!afdelingByEstateMap.value[estateCode]) {
          const afdelings = await manageRoleStore.initDataAfdelingByEstate(estateCode);
          afdelingByEstateMap.value[estateCode] = afdelings ?? [];
        }
      }
    }

    form.estate_ids = Array.from(new Set(estateCodes));

    const afdelingKeys = [];
    form.estate_ids.forEach((estateCode) => {
      const afdelingList = afdelingByEstateMap.value[String(estateCode)] ?? [];
      afdelingList.forEach((afdeling) => {
        const kodeAfd = String(getAfdelingCode(afdeling));
        const selectionKey = getAfdelingSelectionKey(estateCode, kodeAfd);
        if (selectionKey) afdelingKeys.push(selectionKey);
      });
    });

    form.afdeling_ids = Array.from(new Set(afdelingKeys));
    syncSelectedItemsFromIds();
    pruneDownstreamSelections();
  } finally {
    loadingHierarchy.value = false;
  }
};

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

  const availableAfdelingKeys = new Set();
  Object.entries(afdelingByEstateMap.value).forEach(([estateCode, afdelings]) => {
    (afdelings ?? []).forEach((item) => {
      const selectionKey = getAfdelingSelectionKey(
        estateCode,
        getAfdelingCode(item),
      );
      if (selectionKey) availableAfdelingKeys.add(selectionKey);
    });
  });

  form.afdeling_ids = form.afdeling_ids.filter((id) =>
    availableAfdelingKeys.has(String(id)),
  );
  form.selected_afdeling_items = form.selected_afdeling_items.filter((item) =>
    availableAfdelingKeys.has(
      getAfdelingSelectionKey(item?.kode_est, item?.kode_afd),
    ),
  );
};

const toggleArea = async (area) => {
  const id = String(area?.id ?? "");
  if (!id) return;

  const areaId = getAreaId(area);
  const index = form.area_ids.indexOf(id);

  if (index > -1) {
    form.area_ids.splice(index, 1);
    form.selected_area_items = form.selected_area_items.filter(
      (item) => String(item?.id ?? "") !== id,
    );

    delete perusahaanByAreaMap.value[areaId];
    pruneDownstreamSelections();
  } else {
    form.area_ids.push(id);
    await autoSelectHierarchyFromAreas(form.area_ids);
  }
};

const togglePerusahaan = async (perusahaan) => {
  const id = String(perusahaan?.id ?? "");
  if (!id) return;

  const perusahaanCode = getPerusahaanCode(perusahaan);
  const index = form.perusahaan_ids.indexOf(id);

  if (index > -1) {
    form.perusahaan_ids.splice(index, 1);
    form.selected_perusahaan_items = form.selected_perusahaan_items.filter(
      (item) => String(item?.id ?? "") !== id,
    );
    delete estateByPerusahaanMap.value[perusahaanCode];
    pruneDownstreamSelections();
  } else {
    form.perusahaan_ids.push(id);
    form.selected_perusahaan_items = [
      ...form.selected_perusahaan_items,
      {
        id: String(perusahaan?.id ?? ""),
        kode_pt: String(perusahaan?.kode_pt ?? perusahaan?.kode ?? ""),
        kode_area: String(
          perusahaan?.kode_area ?? perusahaan?.area_id ?? perusahaan?.area?.area_id ?? "",
        ),
        nama_pt: String(
          perusahaan?.nama_pt ?? perusahaan?.nama_perusahaan ?? perusahaan?.nama ?? "",
        ),
      },
    ];
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
    form.selected_estate_items = form.selected_estate_items.filter(
      (item) => String(item?.kode_est ?? "") !== code,
    );
    delete afdelingByEstateMap.value[code];
    pruneDownstreamSelections();
  } else {
    form.estate_ids.push(code);
    form.selected_estate_items = [
      ...form.selected_estate_items,
      {
        id: String(estate?.id ?? ""),
        kode_est: String(estate?.kode_est ?? ""),
        kode_pt: String(estate?.kode_pt ?? estate?.pt_kode ?? ""),
        nama_estate: String(estate?.nama_estate ?? estate?.nama ?? ""),
      },
    ];
    if (!afdelingByEstateMap.value[code]) {
      const data = await manageRoleStore.initDataAfdelingByEstate(code);
      afdelingByEstateMap.value[code] = data ?? [];
    }
    pruneDownstreamSelections();
  }
};

const toggleAfdeling = (afdeling, estateCode = "") => {
  const afdelingCode = getAfdelingCode(afdeling);
  const selectionKey = getAfdelingSelectionKey(estateCode, afdelingCode);
  if (!selectionKey) return;

  const index = form.afdeling_ids.indexOf(selectionKey);
  if (index > -1) {
    form.afdeling_ids.splice(index, 1);
    form.selected_afdeling_items = form.selected_afdeling_items.filter(
      (item) =>
        getAfdelingSelectionKey(item?.kode_est, item?.kode_afd) !==
        selectionKey,
    );
  } else {
    form.afdeling_ids.push(selectionKey);
    form.selected_afdeling_items = [
      ...form.selected_afdeling_items,
      {
        id: String(afdeling?.id ?? ""),
        kode_afd: afdelingCode,
        kode_est: String(afdeling?.kode_est ?? estateCode ?? ""),
        nama_afdeling: String(
          afdeling?.nama_afdeling ?? afdeling?.nama ?? afdeling?.kode_afd ?? afdelingCode,
        ),
      },
    ];
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
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Management Role" brand-subtitle="Kelola role dan mapping permission" />

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
            <h2 class="text-20 font-bold">Daftar Role</h2>
            <p class="text-muted">Kelola role dan permission bertingkat berdasarkan scope akses.</p>
          </div>

          <button class="rounded-full bg-brand px-5 py-2.5 font-semibold text-on-brand" @click="openCreateModal">
            + Tambah Role
          </button>
        </div>

        <div class="mb-4">
          <input v-model="search" type="text" placeholder="Cari role..."
            class="h-11 w-full rounded-xl border border-default px-4 outline-none placeholder-text-placeholder" />
        </div>

        <p v-if="manageRoleStore.errorMessage" class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ manageRoleStore.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-4 py-3 font-bold">Nama</th>
                <th class="px-4 py-3 font-bold">Deskripsi</th>
                <th class="px-4 py-3 font-bold">Menu</th>
                <th class="px-4 py-3 font-bold">Akses Data</th>
                <th class="px-4 py-3 font-bold">Transaksi</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="manageRoleStore.loadingList" class="border-t border-row">
                <td colspan="4" class="px-4 py-8 text-center text-muted">
                  Memuat data role...
                </td>
              </tr>

              <tr v-for="item in filteredRoles" :key="item.id" class="border-t border-row">
                <td class="px-4 py-3">{{ item.nama }}</td>
                <td class="px-4 py-3">{{ item.deskripsi }}</td>
                <td class="px-4 py-3">{{ item.akses_menu?.length ?? 0 }}</td>
                <td class="px-4 py-3">{{ item.akses_data?.length ?? 0 }}</td>
                <td class="px-4 py-3">{{ item.akses_transaksi?.length ?? 0 }}</td>
                <td class="px-4 py-3">
                  <button v-if="item.nama != 'superadmin'"
                    class="rounded-lg border border-tan bg-cream px-3 py-1.5 font-semibold text-brand"
                    @click="openEditModal(item)">
                    Edit
                  </button>
                </td>
              </tr>

              <tr v-if="!manageRoleStore.loadingList && filteredRoles.length === 0" class="border-t border-row">
                <td colspan="4" class="px-4 py-8 text-center text-muted">
                  Belum ada data role.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="showFormModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
      <div class="w-full max-w-4xl rounded-2xl bg-surface p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-18 font-bold">{{ pageTitle }}</h3>
          <button class="text-muted" @click="closeFormModal">✕</button>
        </div>

        <form class="grid grid-cols-1 gap-3 md:grid-cols-2" @submit.prevent="submitForm">
          <div>
            <label class="mb-1 block text-label">Nama Role</label>
            <input :value="form.nama" @input="onNamaInput" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 uppercase outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-label">Deskripsi</label>
            <input :value="form.deskripsi" @input="onDeskripsiInput" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 uppercase outline-none" />
          </div>

          <div class="md:col-span-2 rounded-xl border border-default p-4 max-h-[70vh] overflow-y-auto">
            <div class="mb-4 flex flex-wrap gap-2 border-b border-default pb-3">
              <button type="button" class="rounded-xl px-4 py-2 text-size-sm font-semibold transition" :class="activePermissionTab === 'menu'
                ? 'bg-brand text-on-brand'
                : 'border border-tan bg-cream text-brand'" @click="changeContent('menu')">
                Akses Menu
              </button>
              <button type="button" class="rounded-xl px-4 py-2 text-size-sm font-semibold transition" :class="activePermissionTab === 'perusahaan'
                ? 'bg-brand text-on-brand'
                : 'border border-tan bg-cream text-brand'" @click="changeContent('perusahaan')">
                Akses Data
              </button>
              <button type="button" class="rounded-xl px-4 py-2 text-size-sm font-semibold transition" :class="activePermissionTab === 'transaksi'
                ? 'bg-brand text-on-brand'
                : 'border border-tan bg-cream text-brand'" @click="changeContent('transaksi')">
                Akses transaksi
              </button>
            </div>

            <div v-show="activePermissionTab === 'menu'" class="rounded-xl border border-default p-4">
              <div class="mb-3 flex items-center justify-between gap-2">
                <p class="font-semibold text-brand">List Menu</p>
                <button type="button"
                  class="rounded-lg border border-tan bg-cream px-3 py-1.5 text-size-sm font-semibold text-brand"
                  @click="toggleAllMenu">
                  Ceklis Semua
                </button>
              </div>

              <div v-if="!manageRoleStore.allDataMenu.length" class="text-muted">
                Belum ada data permission menu.
              </div>

              <div v-else class="grid grid-cols-1 gap-2">
                <label v-for="menu in manageRoleStore.allDataMenu" :key="menu.id"
                  class="flex items-center gap-2 rounded-lg border border-default p-2"
                  :style="{ marginLeft: `${(Number(menu.level || 1) - 1) * 20}px` }">
                  <input :checked="form.menu_ids.includes(menu.id)" type="checkbox" class="h-4 w-4"
                    @change="togglePermission(menu.id)" />
                  <span>
                    <span v-if="Number(menu.level) > 1" class="text-muted">↳ </span>
                    {{ menu.title }}
                    <span class="text-muted">· Level {{ menu.level || 1 }}</span>
                  </span>
                </label>
              </div>
            </div>

            <div v-show="activePermissionTab === 'perusahaan'" class="rounded-xl border border-default p-4">
              <div class="mb-4 rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 1 - Area</p>
                  <!-- <input v-model="searchQueryArea" type="text" placeholder="Cari area..."
                    class="rounded-lg border border-tan bg-cream px-3 py-1.5 text-size-sm text-brand focus:outline-none focus:ring-1 focus-ring-brand" /> -->
                </div>
                <div v-if="!allDataArea.length" class="text-muted">
                  Belum ada data area.
                </div>
                <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <label v-for="area in allDataArea" :key="area.id ?? area.kode_area ?? area.kode"
                    class="flex items-center gap-2 rounded-lg border border-default p-2">
                    <input :checked="form.area_ids.includes(String(area.id))" type="checkbox" class="h-4 w-4"
                      @change="toggleArea(area)" />
                    <span>{{ area.nama ?? '' }}</span>
                  </label>
                </div>
              </div>

              <div v-if="loadingHierarchy" class="mb-4 rounded-xl border border-default p-4 text-muted">
                Memuat data hierarchy (perusahaan, estate, afdeling)...
              </div>

              <div v-if="groupedPerusahaanByArea.length" class="mb-4 rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 2 - Perusahaan</p>
                  <!-- <input v-model="searchQueryPerusahaan" type="text" placeholder="Cari perusahaan..."
                    class="rounded-lg border border-tan bg-cream px-3 py-1.5 text-size-sm text-brand focus:outline-none focus:ring-1 focus-ring-brand" /> -->
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedPerusahaanByArea" :key="group.areaKey"
                    class="rounded-lg border border-default p-3">
                    <p class="mb-2 text-size-sm font-semibold text-label">
                      Area: {{ group.area?.nama_area ?? group.area?.nama ?? group.areaKey }}
                    </p>
                    <div v-if="!group.perusahaan.length" class="text-muted">
                      Tidak ada perusahaan untuk area ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="perusahaan in group.perusahaan" :key="perusahaan.id"
                        class="flex items-center gap-2 rounded-lg border border-default p-2">
                        <input :checked="form.perusahaan_ids.includes(String(perusahaan.id))" type="checkbox"
                          class="h-4 w-4" @change="togglePerusahaan(perusahaan)" />
                        <span>{{ perusahaan.nama_pt ?? perusahaan.nama ?? perusahaan.title ??
                          getPerusahaanCode(perusahaan) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedEstateByPerusahaan.length" class="mb-4 rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 3 - Estate</p>
                  <!-- <input v-model="searchQueryEstate" type="text" placeholder="Cari estate..."
                    class="rounded-lg border border-tan bg-cream px-3 py-1.5 text-size-sm text-brand focus:outline-none focus:ring-1 focus-ring-brand" /> -->
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedEstateByPerusahaan" :key="group.perusahaanKey"
                    class="rounded-lg border border-default p-3">
                    <p class="mb-2 text-size-sm font-semibold text-label">
                      Perusahaan: {{ group.perusahaan?.nama_pt ?? group.perusahaan?.nama ?? group.perusahaanKey }}
                    </p>
                    <div v-if="!group.estates.length" class="text-muted">
                      Tidak ada estate untuk perusahaan ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="estate in group.estates" :key="getEstateCode(estate)"
                        class="flex items-center gap-2 rounded-lg border border-default p-2">
                        <input :checked="form.estate_ids.includes(getEstateCode(estate))" type="checkbox"
                          class="h-4 w-4" @change="toggleEstate(estate)" />
                        <span>{{ estate.nama_estate ?? estate.nama ?? estate.title ?? getEstateCode(estate) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedAfdelingByEstate.length" class="rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 4 - Afdeling</p>
                  <!-- <input v-model="searchQueryAfdeling" type="text" placeholder="Cari afdeling..."
                    class="rounded-lg border border-tan bg-cream px-3 py-1.5 text-size-sm text-brand focus:outline-none focus:ring-1 focus-ring-brand" /> -->
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedAfdelingByEstate" :key="group.estateKey"
                    class="rounded-lg border border-default p-3">
                    <p class="mb-2 text-size-sm font-semibold text-label">
                      Estate: {{ group.estate?.nama_estate ?? group.estate?.nama ?? group.estateKey }}
                    </p>
                    <div v-if="!group.afdelings.length" class="text-muted">
                      Tidak ada afdeling untuk estate ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="afdeling in group.afdelings"
                        :key="getAfdelingSelectionKey(group.estateKey, getAfdelingCode(afdeling))"
                        class="flex items-center gap-2 rounded-lg border border-default p-2">
                        <input :checked="isAfdelingSelected(group.estateKey, getAfdelingCode(afdeling))" type="checkbox"
                          class="h-4 w-4" @change="toggleAfdeling(afdeling, group.estateKey)" />
                        <span>{{ afdeling.nama_afdeling ?? afdeling.nama ?? afdeling.title ?? getAfdelingCode(afdeling)
                        }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-show="activePermissionTab === 'transaksi'" class="rounded-xl border border-default p-4">
              <div class="mb-3 flex items-center justify-between gap-2">
                <p class="font-semibold text-brand">List data transaksi</p>
                <button type="button"
                  class="rounded-lg border border-tan bg-cream px-3 py-1.5 text-size-sm font-semibold text-brand"
                  @click="toggleAllTransaksi">
                  Ceklis Semua
                </button>
              </div>

              <div v-if="!allDataTransaksi.length" class="text-muted">
                Belum ada data transaksi.
              </div>

              <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                <label v-for="transaksi in allDataTransaksi" :key="getTransaksiCode(transaksi)"
                  class="flex items-center gap-2 rounded-lg border border-default p-2">
                  <input :checked="form.transaksi_ids.includes(getTransaksiCode(transaksi))" type="checkbox"
                    class="h-4 w-4" @change="togglePermission(getTransaksiCode(transaksi))" />
                  <span>{{ transaksi?.title ?? transaksi?.nama_table_transaksi ?? transaksi }}</span>
                </label>
              </div>
            </div>
          </div>

          <div class="md:col-span-2 mt-2 flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
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
  </main>
</template>

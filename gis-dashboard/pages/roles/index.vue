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

const searchQueryGroup = ref("");
const searchQueryPerusahaan = ref("");
const searchQueryArea = ref("");
const searchQueryEstate = ref("");
const searchQueryAfdeling = ref("");

const activePermissionTab = ref("menu");
const hierarchyLoadCount = ref(0);
const loadingRoleData = ref(false);
const grantCatalogReady = ref(true);
const loadingHierarchy = computed(() => hierarchyLoadCount.value > 0);

const beginDataLoad = () => {
  hierarchyLoadCount.value += 1;
};

const endDataLoad = () => {
  hierarchyLoadCount.value = Math.max(0, hierarchyLoadCount.value - 1);
};

const form = reactive({
  nama: "",
  deskripsi: "",
  menu_ids: [],
  group_ids: [],
  perusahaan_ids: [],
  area_ids: [],
  estate_ids: [],
  afdeling_ids: [],
  blok_ids: [],
  layer_ids: [],
  transaksi_ids: [],
  preserved_grant_ids: [],
  selected_area_items: [],
  selected_perusahaan_items: [],
  selected_estate_items: [],
  selected_afdeling_items: [],
});

const perusahaanByGroupMap = ref({});
const areaByPerusahaanMap = ref({});
const estateByAreaMap = ref({});
const afdelingByEstateMap = ref({});
const blokByAfdelingMap = ref({});

const AREA_KEY_SEPARATOR = "::";

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

const formDataLoading = computed(
  () => loadingRoleData.value || loadingHierarchy.value,
);

const saveDisabled = computed(
  () => submitLoading.value || formDataLoading.value || !grantCatalogReady.value,
);

const saveButtonLabel = computed(() => {
  if (submitLoading.value) return "Menyimpan...";
  if (formDataLoading.value) return "Memuat data...";
  return "Simpan";
});

const getGroupCode = (group) =>
  String(group?.kode_grup ?? group?.code ?? "").trim();

const getPerusahaanCode = (perusahaan) =>
  String(
    perusahaan?.kode_pt ??
    perusahaan?.kode ??
    perusahaan?.id_perusahaan ??
    perusahaan?.id ??
    "",
  ).trim();

const getAreaId = (area) =>
  String(area?.area_id ?? area?.kode_area ?? area?.id_area ?? area?.id ?? "").trim();

const getAreaSelectionKey = (ptCode, areaCode) => {
  const pt = String(ptCode ?? "").trim();
  const area = String(areaCode ?? "").trim();
  if (!pt || !area) return "";
  return `${pt}${AREA_KEY_SEPARATOR}${area}`;
};

const allDataGroup = computed(() => {
  const groups = manageRoleStore.allDataGroup ?? [];
  if (!searchQueryGroup.value) return groups;

  const keyword = searchQueryGroup.value.toLowerCase();
  return groups.filter((group) => {
    const name = String(group?.nama_grup ?? group?.nama ?? "").toLowerCase();
    const code = getGroupCode(group).toLowerCase();
    return name.includes(keyword) || code.includes(keyword);
  });
});

const groupIdentityValues = (group) =>
  [group?.id, group?.kode_grup, group?.code, getGroupCode(group)]
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);

const isGroupSelected = (group) => {
  const saved = new Set(form.group_ids.map((id) => String(id)));
  return groupIdentityValues(group).some((value) => saved.has(value));
};

const perusahaanIdentityValues = (perusahaan) =>
  [
    perusahaan?.id,
    perusahaan?.kode_pt,
    perusahaan?.kode,
    perusahaan?.id_perusahaan,
    getPerusahaanCode(perusahaan),
  ]
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);

const isPerusahaanSelected = (perusahaan) => {
  const saved = new Set(form.perusahaan_ids.map((id) => String(id)));
  return perusahaanIdentityValues(perusahaan).some((value) => saved.has(value));
};

const isAreaSelected = (ptCode, area) =>
  form.area_ids.map((id) => String(id)).includes(getAreaSelectionKey(ptCode, getAreaId(area)));

const selectedGroups = computed(() =>
  (manageRoleStore.allDataGroup ?? []).filter((group) => isGroupSelected(group)),
);

const groupedPerusahaanByGroup = computed(() =>
  selectedGroups.value.map((group) => {
    const groupKey = getGroupCode(group);
    return {
      group,
      groupKey,
      perusahaan: perusahaanByGroupMap.value[groupKey] ?? [],
    };
  }),
);

const selectedPerusahaanList = computed(() =>
  groupedPerusahaanByGroup.value.flatMap((group) =>
    (group.perusahaan ?? [])
      .filter((item) => isPerusahaanSelected(item))
      .map((item) => ({ ...item, _groupCode: group.groupKey })),
  ),
);

const groupedAreaByPerusahaan = computed(() =>
  selectedPerusahaanList.value.map((perusahaan) => {
    const perusahaanKey = getPerusahaanCode(perusahaan);
    return {
      perusahaan,
      perusahaanKey,
      groupCode: String(perusahaan?._groupCode ?? perusahaan?.kode_grup ?? ""),
      areas: areaByPerusahaanMap.value[perusahaanKey] ?? [],
    };
  }),
);

const selectedAreaEntries = computed(() =>
  groupedAreaByPerusahaan.value.flatMap((group) =>
    (group.areas ?? [])
      .filter((area) => isAreaSelected(group.perusahaanKey, area))
      .map((area) => ({
        area,
        perusahaan: group.perusahaan,
        perusahaanKey: group.perusahaanKey,
        groupCode: group.groupCode,
        areaKey: getAreaSelectionKey(group.perusahaanKey, getAreaId(area)),
      })),
  ),
);

const groupedEstateByArea = computed(() =>
  selectedAreaEntries.value.map((entry) => ({
    ...entry,
    estates: estateByAreaMap.value[entry.areaKey] ?? [],
  })),
);

const estateMatchesSelection = (estate, selectedIds) => {
  const kode = String(getEstateCode(estate) ?? "");
  const id = String(estate?.id ?? "");
  return (kode && selectedIds.has(kode)) || (id && selectedIds.has(id));
};

const selectedEstateList = computed(() => {
  const selectedIds = new Set(form.estate_ids.map((id) => String(id)));
  const seen = new Set();
  return groupedEstateByArea.value
    .flatMap((group) => group.estates)
    .filter((item) => {
      if (!estateMatchesSelection(item, selectedIds)) return false;
      const code = String(getEstateCode(item) ?? "");
      if (!code || seen.has(code)) return false;
      seen.add(code);
      return true;
    });
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

const groupedBlokByAfdeling = computed(() => {
  return groupedAfdelingByEstate.value.flatMap((group) =>
    (group.afdelings ?? [])
      .filter((afdeling) => isAfdelingSelected(group.estate, afdeling))
      .map((afdeling) => {
        const mapKey = getAfdelingSelectionKey(
          group.estateKey,
          getAfdelingCode(afdeling),
        );
        return {
          mapKey,
          estate: group.estate,
          estateKey: group.estateKey,
          afdeling,
          bloks: blokByAfdelingMap.value[mapKey] ?? [],
        };
      }),
  );
});

const allDataLayer = computed(
  () => manageRoleStore.allDataLayer ?? [],
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
  form.group_ids = [];
  form.perusahaan_ids = [];
  form.area_ids = [];
  form.estate_ids = [];
  form.afdeling_ids = [];
  form.blok_ids = [];
  form.layer_ids = [];
  form.transaksi_ids = [];
  form.preserved_grant_ids = [];
  form.selected_area_items = [];
  form.selected_perusahaan_items = [];
  form.selected_estate_items = [];
  form.selected_afdeling_items = [];

  searchQueryGroup.value = "";
  searchQueryPerusahaan.value = "";
  searchQueryArea.value = "";
  searchQueryEstate.value = "";
  searchQueryAfdeling.value = "";

  perusahaanByGroupMap.value = {};
  areaByPerusahaanMap.value = {};
  estateByAreaMap.value = {};
  afdelingByEstateMap.value = {};
  blokByAfdelingMap.value = {};

  activePermissionTab.value = "menu";
}

function clearWilayahSelection() {
  form.group_ids = [];
  form.perusahaan_ids = [];
  form.area_ids = [];
  form.estate_ids = [];
  form.afdeling_ids = [];
  form.blok_ids = [];
  perusahaanByGroupMap.value = {};
  areaByPerusahaanMap.value = {};
  estateByAreaMap.value = {};
  afdelingByEstateMap.value = {};
  blokByAfdelingMap.value = {};
}

async function fillForm(role) {
  loadingRoleData.value = true;
  grantCatalogReady.value = false;
  form.layer_ids = [];
  form.transaksi_ids = [];
  form.preserved_grant_ids = [];
  clearWilayahSelection();

  try {
    const existingAkses = await manageRoleStore.getExistingAksesByRole(role.id);

    if (!(manageRoleStore.allDataGroup ?? []).length) {
      await manageRoleStore.initDataGroup();
    }
    if (!(manageRoleStore.allDataMenu ?? []).length) {
      await manageRoleStore.initDataMenu();
    }
    if (!(manageRoleStore.allDataLayer ?? []).length) {
      await manageRoleStore.initDataLayer();
    }
    if (!(manageRoleStore.allDataTransaksi ?? []).length) {
      await manageRoleStore.initDataTableTransaksi();
    }

    form.nama = String(role.nama ?? "").toUpperCase();
    form.deskripsi = String(role.deskripsi ?? "").toUpperCase();
    activePermissionTab.value = "menu";

    form.menu_ids = (existingAkses?.menu ?? [])
      .map((item) => String(item?.menu_id ?? ""))
      .filter((id) => !!id);

    const savedGrants = manageRoleStore.splitSavedGrants(existingAkses?.transaksi ?? []);
    form.layer_ids = savedGrants.layer_ids;
    form.transaksi_ids = savedGrants.transaksi_ids;
    form.preserved_grant_ids = savedGrants.preserved_grant_ids;
    grantCatalogReady.value = true;

    await applySavedGroupTree(existingAkses?.grup ?? []);
  } finally {
    loadingRoleData.value = false;
  }
}

function openCreateModal() {
  manageRoleStore.clearError();
  grantCatalogReady.value = true;
  formMode.value = "create";
  selectedRoleId.value = "";
  resetForm();
  showFormModal.value = true;
}

async function openEditModal(role) {
  manageRoleStore.clearError();
  formMode.value = "edit";
  selectedRoleId.value = role.id;
  showFormModal.value = true;
  await fillForm(role);
}

function closeFormModal() {
  showFormModal.value = false;
}

function mapHas(map, key) {
  return Object.prototype.hasOwnProperty.call(map, key);
}

function estateIsFull(estate) {
  const code = String(getEstateCode(estate) ?? "");
  if (!code || !mapHas(afdelingByEstateMap.value, code)) return false;
  const afdelings = afdelingByEstateMap.value[code] ?? [];
  if (!afdelings.length) return true;
  return afdelings.every((afdeling) => isAfdelingSelected(estate, afdeling));
}

function areaIsFull(ptCode, area) {
  const key = getAreaSelectionKey(ptCode, getAreaId(area));
  if (!key || !mapHas(estateByAreaMap.value, key)) return false;
  const estates = estateByAreaMap.value[key] ?? [];
  if (!estates.length) return true;
  return estates.every((estate) => isEstateSelected(estate) && estateIsFull(estate));
}

function companyIsFull(perusahaan) {
  const ptCode = getPerusahaanCode(perusahaan);
  if (!ptCode || !mapHas(areaByPerusahaanMap.value, ptCode)) return false;
  const areas = areaByPerusahaanMap.value[ptCode] ?? [];
  if (!areas.length) return true;
  return areas.every((area) => isAreaSelected(ptCode, area) && areaIsFull(ptCode, area));
}

function groupIsFull(group) {
  const groupCode = getGroupCode(group);
  if (!groupCode || !mapHas(perusahaanByGroupMap.value, groupCode)) return false;
  const companies = perusahaanByGroupMap.value[groupCode] ?? [];
  if (!companies.length) return true;
  return companies.every((perusahaan) => isPerusahaanSelected(perusahaan) && companyIsFull(perusahaan));
}

function buildAksesData() {
  const items = [];
  const areaNodes = new Map();

  for (const group of selectedGroups.value) {
    if (groupIsFull(group)) {
      const groupCode = getGroupCode(group);
      if (groupCode) items.push({ kode_grup: groupCode });
      continue;
    }

    const companies = (perusahaanByGroupMap.value[getGroupCode(group)] ?? [])
      .filter((perusahaan) => isPerusahaanSelected(perusahaan));

    for (const perusahaan of companies) {
      const ptCode = getPerusahaanCode(perusahaan);
      if (companyIsFull(perusahaan)) {
        if (ptCode) items.push({ kode_pt: ptCode });
        continue;
      }

      for (const area of areaByPerusahaanMap.value[ptCode] ?? []) {
        if (!isAreaSelected(ptCode, area)) continue;
        const areaCode = getAreaId(area);
        const areaKey = getAreaSelectionKey(ptCode, areaCode);
        const estates = (estateByAreaMap.value[areaKey] ?? [])
          .filter((estate) => isEstateSelected(estate))
          .map((estate) => {
            const estateCode = String(getEstateCode(estate));
            const afdeling = (afdelingByEstateMap.value[estateCode] ?? [])
              .filter((item) => isAfdelingSelected(estate, item))
              .map((item) => ({
                id_afdeling: String(item?.id ?? getAfdelingCode(item)),
                nama_afdeling: String(item?.nama_afdeling ?? item?.nama ?? getAfdelingCode(item)),
              }));
            if (estateIsFull(estate)) {
              return {
                id_estate: String(estate?.id ?? estateCode),
                nama_estate: String(estate?.nama_estate ?? estate?.nama ?? estateCode),
                afdeling: [],
              };
            }
            if (!afdeling.length) return null;
            return {
              id_estate: String(estate?.id ?? estateCode),
              nama_estate: String(estate?.nama_estate ?? estate?.nama ?? estateCode),
              afdeling,
            };
          })
          .filter(Boolean);
        if (!estates.length) continue;

        const node = areaNodes.get(areaCode) ?? {
          id_area: areaCode,
          nama_area: String(area?.nama_area ?? area?.nama ?? areaCode),
          perusahaan: [],
        };
        node.perusahaan.push({
          id_perusahaan: String(perusahaan?.id ?? ptCode),
          nama_perusahaan: String(
            perusahaan?.nama_pt ?? perusahaan?.nama_perusahaan ?? perusahaan?.nama ?? ptCode,
          ),
          estate: estates,
        });
        areaNodes.set(areaCode, node);
      }
    }
  }

  return [...items, ...areaNodes.values()];
}

async function submitForm() {
  if (saveDisabled.value) return;

  syncSelectedItemsFromIds();
  form.nama = String(form.nama ?? "").toUpperCase();
  form.deskripsi = String(form.deskripsi ?? "").toUpperCase();

  const payload = {
    ...form,
    akses_data: buildAksesData(),
  };

  try {
    if (formMode.value === "create") {
      await manageRoleStore.createRole(payload);
    } else {
      await manageRoleStore.updateRole(selectedRoleId.value, payload);
    }

    showFormModal.value = false;
    await manageRoleStore.fetchRoles();
  } catch {
    // Pesan error ditampilkan di dalam modal.
  }
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

const getMenuDescendantIds = (menuId) => {
  const menus = manageRoleStore.allDataMenu ?? [];
  const ids = [];
  const walk = (parentId) => {
    menus.forEach((menu) => {
      if (String(menu.parent_id ?? "") === String(parentId)) {
        const childId = String(menu.id);
        ids.push(childId);
        walk(childId);
      }
    });
  };
  walk(menuId);
  return ids;
};

const getMenuAncestorIds = (menuId) => {
  const menus = manageRoleStore.allDataMenu ?? [];
  const byId = new Map(menus.map((menu) => [String(menu.id), menu]));
  const ids = [];
  let current = byId.get(String(menuId));

  while (current?.parent_id) {
    const parentId = String(current.parent_id);
    ids.push(parentId);
    current = byId.get(parentId);
  }

  return ids;
};

const toggleMenuPermission = (menuId) => {
  const id = String(menuId);
  const selected = new Set(form.menu_ids.map((value) => String(value)));
  const isSelected = selected.has(id);

  if (isSelected) {
    selected.delete(id);
    getMenuDescendantIds(id).forEach((childId) => selected.delete(childId));
  } else {
    selected.add(id);
    getMenuDescendantIds(id).forEach((childId) => selected.add(childId));
    getMenuAncestorIds(id).forEach((parentId) => selected.add(parentId));
  }

  form.menu_ids = Array.from(selected);
};

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

const isEstateSelected = (estate) =>
  estateMatchesSelection(
    estate,
    new Set(form.estate_ids.map((id) => String(id))),
  );

const isAfdelingSelected = (estate, afdeling) => {
  const estateCode = String(getEstateCode(estate) ?? "");
  const estateId = String(estate?.id ?? "");
  const kodeAfd = String(getAfdelingCode(afdeling) ?? "");
  const afdelingId = String(afdeling?.id ?? "");
  return [
    getAfdelingSelectionKey(estateCode, kodeAfd),
    getAfdelingSelectionKey(estateId, afdelingId),
    getAfdelingSelectionKey(estateId, kodeAfd),
    getAfdelingSelectionKey(estateCode, afdelingId),
  ]
    .filter(Boolean)
    .some((key) => form.afdeling_ids.includes(key));
};

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

const getLayerCode = (layer) =>
  String(
    layer?.nama_table_transaksi ||
    layer?.table_name ||
    layer?.id ||
    "",
  );

const getTransaksiCode = (transaksi) =>
  String(
    transaksi?.physical_table ||
    transaksi?.nama_table_transaksi ||
    transaksi?.table_name ||
    transaksi?.id ||
    "",
  );

function countRoleAccess(role, kind) {
  const rows = role?.akses_transaksi ?? [];
  const catalogsReady =
    (manageRoleStore.allDataLayer ?? []).length > 0
    || (manageRoleStore.allDataTransaksi ?? []).length > 0;

  if (!catalogsReady) {
    return rows.filter((item) => {
      const name = String(item?.nama_table_transaksi ?? "").toLowerCase();
      return kind === "layer"
        ? name.startsWith("spatial.")
        : name.startsWith("trx.") || name.startsWith("trx_");
    }).length;
  }

  const split = manageRoleStore.splitSavedGrants(rows);
  return kind === "layer" ? split.layer_ids.length : split.transaksi_ids.length;
}

const syncSelectedItemsFromIds = () => {
  const areaByKey = new Map();
  Object.entries(areaByPerusahaanMap.value).forEach(([ptCode, areas]) => {
    (areas ?? []).forEach((area) => {
      const key = getAreaSelectionKey(ptCode, getAreaId(area));
      if (key) areaByKey.set(key, area);
    });
  });

  form.selected_area_items = form.area_ids
    .map((id) => areaByKey.get(String(id)))
    .filter(Boolean)
    .map((area) => ({
      id: String(area?.id ?? ""),
      area_id: String(getAreaId(area)),
      nama_area: String(area?.nama_area ?? area?.nama ?? ""),
    }));

  const perusahaanMapById = new Map();
  Object.values(perusahaanByGroupMap.value).forEach((perusahaanList) => {
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
  Object.values(estateByAreaMap.value).forEach((estateList) => {
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

function uniqueIds(values = []) {
  return Array.from(new Set((values ?? []).map((value) => String(value ?? "").trim()).filter(Boolean)));
}

function mergeIds(current, values) {
  return uniqueIds([...current, ...values]);
}

async function ensureCompanies(groupCode) {
  const code = String(groupCode ?? "").trim();
  if (!code || mapHas(perusahaanByGroupMap.value, code)) {
    return perusahaanByGroupMap.value[code] ?? [];
  }
  const list = await manageRoleStore.initDataPerusahaanByGroup(code);
  perusahaanByGroupMap.value[code] = list ?? [];
  return perusahaanByGroupMap.value[code];
}

async function ensureAreas(groupCode, ptCode) {
  const code = String(ptCode ?? "").trim();
  if (!code || mapHas(areaByPerusahaanMap.value, code)) {
    return areaByPerusahaanMap.value[code] ?? [];
  }
  const list = await manageRoleStore.initDataAreaByPerusahaan(groupCode, code);
  areaByPerusahaanMap.value[code] = list ?? [];
  return areaByPerusahaanMap.value[code];
}

async function ensureEstates(groupCode, ptCode, areaCode) {
  const key = getAreaSelectionKey(ptCode, areaCode);
  if (!key || mapHas(estateByAreaMap.value, key)) {
    return estateByAreaMap.value[key] ?? [];
  }
  const list = await manageRoleStore.initDataEstateByScope(groupCode, ptCode, areaCode);
  estateByAreaMap.value[key] = list ?? [];
  return estateByAreaMap.value[key];
}

async function collectUnderPerusahaan(groupCode, perusahaan) {
  const ptCode = getPerusahaanCode(perusahaan);
  const areas = await ensureAreas(groupCode, ptCode);
  const areaResults = await Promise.all(areas.map(async (area) => {
    const areaCode = getAreaId(area);
    const estates = await ensureEstates(groupCode, ptCode, areaCode);
    return {
      areaKey: getAreaSelectionKey(ptCode, areaCode),
      estateCodes: estates.map((estate) => getEstateCode(estate)).filter(Boolean),
    };
  }));
  const estateCodes = areaResults.flatMap((item) => item.estateCodes);
  await ensureAfdelingsLoaded(estateCodes);
  return {
    areaKeys: areaResults.map((item) => item.areaKey).filter(Boolean),
    estateCodes,
    afdelingKeys: afdelingKeysForEstates(estateCodes),
  };
}

async function expandGroup(groupCode) {
  const companies = await ensureCompanies(groupCode);
  const results = await Promise.all(
    companies.map((perusahaan) => collectUnderPerusahaan(groupCode, perusahaan)),
  );
  return {
    ptIds: companies.map((perusahaan) => String(perusahaan?.id ?? "")).filter(Boolean),
    areaKeys: results.flatMap((item) => item.areaKeys),
    estateCodes: results.flatMap((item) => item.estateCodes),
    afdelingKeys: results.flatMap((item) => item.afdelingKeys),
  };
}

function applyExpanded(result, { replace = false } = {}) {
  form.perusahaan_ids = replace
    ? uniqueIds(result.ptIds)
    : mergeIds(form.perusahaan_ids, result.ptIds);
  form.area_ids = replace ? uniqueIds(result.areaKeys) : mergeIds(form.area_ids, result.areaKeys);
  form.estate_ids = replace
    ? uniqueIds(result.estateCodes)
    : mergeIds(form.estate_ids, result.estateCodes);
  form.afdeling_ids = replace
    ? uniqueIds(result.afdelingKeys)
    : mergeIds(form.afdeling_ids, result.afdelingKeys);
}

async function autoSelectHierarchyFromGroups(groupCodes = []) {
  beginDataLoad();
  try {
    const codes = uniqueIds(groupCodes);
    const collected = await Promise.all(codes.map((code) => expandGroup(code)));
    const result = {
      ptIds: collected.flatMap((item) => item.ptIds),
      areaKeys: collected.flatMap((item) => item.areaKeys),
      estateCodes: collected.flatMap((item) => item.estateCodes),
      afdelingKeys: collected.flatMap((item) => item.afdelingKeys),
    };
    applyExpanded(result, { replace: true });
    await ensureBloksForAfdelingKeys(form.afdeling_ids);
    form.blok_ids = collectBlokIds(form.afdeling_ids);
    pruneDownstreamSelections();
  } finally {
    endDataLoad();
  }
}

function findCompany(groupCode, node) {
  const list = perusahaanByGroupMap.value[groupCode] ?? [];
  const id = String(node?.id_perusahaan ?? "");
  const code = String(node?.kode_pt ?? "");
  return list.find((item) => String(item?.id ?? "") === id || getPerusahaanCode(item) === code);
}

function findArea(ptCode, node) {
  const code = String(node?.kode_area ?? "");
  return (areaByPerusahaanMap.value[ptCode] ?? []).find((area) => {
    const values = [getAreaId(area), area?.kode_area, area?.area_id, area?.id]
      .map((value) => String(value ?? ""));
    return code && values.includes(code);
  });
}

function findEstate(areaKey, node) {
  const code = String(node?.kode_est ?? "");
  const id = String(node?.id_estate ?? "");
  return (estateByAreaMap.value[areaKey] ?? []).find((estate) =>
    getEstateCode(estate) === code
    || String(estate?.id ?? "") === id
    || getEstateCode(estate) === id,
  );
}

async function applySavedGroupTree(trees = []) {
  beginDataLoad();
  try {
    for (const node of trees ?? []) {
      const groupCode = String(node?.kode_grup ?? "").trim();
      if (!groupCode) continue;
      form.group_ids = mergeIds(form.group_ids, [groupCode]);

      if (node.penuh || !(node.perusahaan ?? []).length) {
        applyExpanded(await expandGroup(groupCode));
        await ensureBloksForAfdelingKeys(form.afdeling_ids);
        mergeBlokIds(form.afdeling_ids);
        continue;
      }

      await ensureCompanies(groupCode);
      for (const ptNode of node.perusahaan ?? []) {
        const perusahaan = findCompany(groupCode, ptNode);
        if (!perusahaan) continue;
        const ptId = String(perusahaan?.id ?? "");
        const ptCode = getPerusahaanCode(perusahaan);
        if (ptId) form.perusahaan_ids = mergeIds(form.perusahaan_ids, [ptId]);

        if (ptNode.penuh || !(ptNode.area ?? []).length) {
          const result = await collectUnderPerusahaan(groupCode, perusahaan);
          form.area_ids = mergeIds(form.area_ids, result.areaKeys);
          form.estate_ids = mergeIds(form.estate_ids, result.estateCodes);
          form.afdeling_ids = mergeIds(form.afdeling_ids, result.afdelingKeys);
          await ensureBloksForAfdelingKeys(result.afdelingKeys);
          mergeBlokIds(result.afdelingKeys);
          continue;
        }

        await ensureAreas(groupCode, ptCode);
        for (const areaNode of ptNode.area ?? []) {
          const area = findArea(ptCode, areaNode);
          if (!area) continue;
          const areaCode = getAreaId(area);
          const areaKey = getAreaSelectionKey(ptCode, areaCode);
          if (areaKey) form.area_ids = mergeIds(form.area_ids, [areaKey]);

          if (areaNode.penuh || !(areaNode.estate ?? []).length) {
            const estates = await ensureEstates(groupCode, ptCode, areaCode);
            const estateCodes = estates.map((estate) => getEstateCode(estate)).filter(Boolean);
            await ensureAfdelingsLoaded(estateCodes);
            const afdelingKeys = afdelingKeysForEstates(estateCodes);
            form.estate_ids = mergeIds(form.estate_ids, estateCodes);
            form.afdeling_ids = mergeIds(form.afdeling_ids, afdelingKeys);
            await ensureBloksForAfdelingKeys(afdelingKeys);
            mergeBlokIds(afdelingKeys);
            continue;
          }

          await ensureEstates(groupCode, ptCode, areaCode);
          for (const estateNode of areaNode.estate ?? []) {
            const estate = findEstate(areaKey, estateNode);
            if (!estate) continue;
            const estateCode = getEstateCode(estate);
            if (!estateCode) continue;
            form.estate_ids = mergeIds(form.estate_ids, [estateCode]);
            await ensureAfdelingsLoaded([estateCode]);
            const keys = estateNode.penuh || !(estateNode.afdeling ?? []).length
              ? afdelingKeysForEstates([estateCode])
              : (estateNode.afdeling ?? [])
                .map((afdeling) => getAfdelingSelectionKey(
                  estateCode,
                  String(afdeling?.kode_afd ?? afdeling?.id_afdeling ?? ""),
                ))
                .filter(Boolean);
            form.afdeling_ids = mergeIds(form.afdeling_ids, keys);
            await ensureBloksForAfdelingKeys(keys);
            mergeBlokIds(keys);
          }
        }
      }
    }
  } finally {
    endDataLoad();
  }
}

const pruneDownstreamSelections = () => {
  const selectedGroupCodes = new Set(form.group_ids.map((id) => String(id)));
  Object.keys(perusahaanByGroupMap.value).forEach((groupCode) => {
    if (!selectedGroupCodes.has(String(groupCode))) {
      delete perusahaanByGroupMap.value[groupCode];
    }
  });

  const availablePerusahaanMap = new Map();
  Object.values(perusahaanByGroupMap.value).forEach((list) => {
    (list ?? []).forEach((item) => {
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

  Object.keys(areaByPerusahaanMap.value).forEach((kodePt) => {
    if (!selectedPerusahaanCodes.has(String(kodePt))) {
      delete areaByPerusahaanMap.value[kodePt];
    }
  });

  const availableAreaKeys = new Set();
  Object.entries(areaByPerusahaanMap.value).forEach(([ptCode, areas]) => {
    (areas ?? []).forEach((area) => {
      const key = getAreaSelectionKey(ptCode, getAreaId(area));
      if (key) availableAreaKeys.add(key);
    });
  });
  form.area_ids = form.area_ids.filter((id) => availableAreaKeys.has(String(id)));

  const selectedAreaKeys = new Set(form.area_ids.map((id) => String(id)));
  Object.keys(estateByAreaMap.value).forEach((areaKey) => {
    if (!selectedAreaKeys.has(String(areaKey))) {
      delete estateByAreaMap.value[areaKey];
    }
  });

  const availableEstateKeys = new Set();
  const selectedEstateCodes = new Set();
  const keptEstateIds = new Set(form.estate_ids.map((id) => String(id)));
  Object.values(estateByAreaMap.value).forEach((estates) => {
    (estates ?? []).forEach((estate) => {
      const code = String(getEstateCode(estate) ?? "");
      const id = String(estate?.id ?? "");
      if (code) availableEstateKeys.add(code);
      if (id) availableEstateKeys.add(id);
      if (estateMatchesSelection(estate, keptEstateIds) && code) {
        selectedEstateCodes.add(code);
      }
    });
  });

  form.estate_ids = form.estate_ids.filter((id) =>
    availableEstateKeys.has(String(id)),
  );

  Object.keys(afdelingByEstateMap.value).forEach((kodeEst) => {
    if (!selectedEstateCodes.has(String(kodeEst))) {
      delete afdelingByEstateMap.value[kodeEst];
    }
  });

  const availableAfdelingKeys = new Set();
  Object.entries(afdelingByEstateMap.value).forEach(([estateCode, afdelings]) => {
    const estate = Object.values(estateByAreaMap.value)
      .flat()
      .find((item) => String(getEstateCode(item)) === String(estateCode));
    const estateId = String(estate?.id ?? "");
    (afdelings ?? []).forEach((item) => {
      const kodeAfd = String(getAfdelingCode(item) ?? "");
      const afdelingId = String(item?.id ?? "");
      [
        getAfdelingSelectionKey(estateCode, kodeAfd),
        getAfdelingSelectionKey(estateId, afdelingId),
        getAfdelingSelectionKey(estateId, kodeAfd),
        getAfdelingSelectionKey(estateCode, afdelingId),
      ]
        .filter(Boolean)
        .forEach((key) => availableAfdelingKeys.add(key));
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

  const selectedAfdelingKeys = new Set(form.afdeling_ids.map((id) => String(id)));
  const nextBlokMap = {};
  Object.entries(blokByAfdelingMap.value).forEach(([key, bloks]) => {
    if (selectedAfdelingKeys.has(String(key))) nextBlokMap[key] = bloks;
  });
  blokByAfdelingMap.value = nextBlokMap;
  form.blok_ids = form.blok_ids.filter((id) =>
    selectedAfdelingKeys.has(parentAfdelingKeyFromBlok(id)),
  );
};

const getBlokCode = (blok) =>
  String(blok?.kode_blok ?? blok?.blok ?? blok?.code ?? blok?.id ?? "");

const getBlokSelectionKey = (estateCode, afdelingCode, blokCode) => {
  const parentKey = getAfdelingSelectionKey(estateCode, afdelingCode);
  const kodeBlok = String(blokCode ?? "");
  if (!parentKey || !kodeBlok) return "";
  return `${parentKey}${AFDELING_KEY_SEPARATOR}${kodeBlok}`;
};

const parentAfdelingKeyFromBlok = (blokKey) => {
  const parts = String(blokKey ?? "").split(AFDELING_KEY_SEPARATOR);
  if (parts.length < 3) return "";
  return getAfdelingSelectionKey(parts[0], parts[1]);
};

const hasBlokCache = (key) =>
  Object.prototype.hasOwnProperty.call(blokByAfdelingMap.value, key);

const dedupeBloks = (list = []) => {
  const seen = new Set();
  return (list ?? []).filter((blok) => {
    const key = String(blok?.id ?? getBlokCode(blok));
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const ensureAfdelingsLoaded = async (estateCodes = []) => {
  const missing = [...new Set(estateCodes.map((code) => String(code)).filter(Boolean))]
    .filter((estateCode) => !afdelingByEstateMap.value[estateCode]);
  if (!missing.length) return;

  beginDataLoad();
  try {
    const lists = await Promise.all(
      missing.map((estateCode) => manageRoleStore.initDataAfdelingByEstate(estateCode)),
    );
    missing.forEach((estateCode, index) => {
      afdelingByEstateMap.value[estateCode] = lists[index] ?? [];
    });
  } finally {
    endDataLoad();
  }
};

const afdelingKeysForEstates = (estateCodes = []) => {
  const keys = [];
  estateCodes.forEach((estateCode) => {
    (afdelingByEstateMap.value[String(estateCode)] ?? []).forEach((afdeling) => {
      const key = getAfdelingSelectionKey(estateCode, getAfdelingCode(afdeling));
      if (key) keys.push(key);
    });
  });
  return keys;
};

const mergeAfdelingIds = (estateCodes = []) => {
  const keys = afdelingKeysForEstates(estateCodes);
  form.afdeling_ids = Array.from(new Set([
    ...form.afdeling_ids.map((value) => String(value)),
    ...keys,
  ]));
  return keys;
};

const collectBlokIds = (afdelingKeys = []) => {
  const selected = new Set((afdelingKeys ?? []).map((key) => String(key)));
  const ids = [];
  Object.entries(blokByAfdelingMap.value).forEach(([afdKey, bloks]) => {
    if (!selected.has(String(afdKey))) return;
    const { kodeEst, kodeAfd } = parseAfdelingSelectionKey(afdKey);
    (bloks ?? []).forEach((blok) => {
      const selectionKey = getBlokSelectionKey(kodeEst, kodeAfd, getBlokCode(blok));
      if (selectionKey) ids.push(selectionKey);
    });
  });
  return Array.from(new Set(ids));
};

const mergeBlokIds = (afdelingKeys = []) => {
  form.blok_ids = Array.from(new Set([
    ...form.blok_ids.map((value) => String(value)),
    ...collectBlokIds(afdelingKeys),
  ]));
};

const ensureBloksForAfdelingKeys = async (afdelingKeys = []) => {
  const pairs = [];
  for (const key of afdelingKeys) {
    const selectionKey = String(key ?? "");
    const { kodeEst, kodeAfd } = parseAfdelingSelectionKey(selectionKey);
    if (!kodeEst || !kodeAfd || hasBlokCache(selectionKey)) continue;
    pairs.push({ key: selectionKey, kodeEst, kodeAfd });
  }
  if (!pairs.length) return;

  beginDataLoad();
  try {
    const next = { ...blokByAfdelingMap.value };
    const chunkSize = 6;
    for (let index = 0; index < pairs.length; index += chunkSize) {
      const chunk = pairs.slice(index, index + chunkSize);
      const lists = await Promise.all(
        chunk.map((pair) => manageRoleStore.initDataBlokByAfdeling(pair.kodeEst, pair.kodeAfd)),
      );
      chunk.forEach((pair, chunkIndex) => {
        next[pair.key] = dedupeBloks(lists[chunkIndex] ?? []);
      });
    }
    blokByAfdelingMap.value = next;
  } finally {
    endDataLoad();
  }
};

const isBlokSelected = (estateCode, afdeling, blok) => {
  const key = getBlokSelectionKey(
    estateCode,
    getAfdelingCode(afdeling),
    getBlokCode(blok),
  );
  return !!key && form.blok_ids.includes(key);
};

const toggleBlok = (blok, estateCode, afdeling) => {
  const key = getBlokSelectionKey(
    estateCode,
    getAfdelingCode(afdeling),
    getBlokCode(blok),
  );
  if (!key) return;

  const index = form.blok_ids.indexOf(key);
  if (index > -1) {
    form.blok_ids.splice(index, 1);
  } else {
    form.blok_ids.push(key);
  }
};

const toggleGroup = async (group) => {
  const code = getGroupCode(group);
  if (!code) return;

  const index = form.group_ids.map((id) => String(id)).indexOf(code);
  if (index > -1) {
    form.group_ids.splice(index, 1);
    delete perusahaanByGroupMap.value[code];
    pruneDownstreamSelections();
    return;
  }

  form.group_ids.push(code);
  await autoSelectHierarchyFromGroups(form.group_ids);
};

const togglePerusahaan = async (perusahaan, groupCode = "") => {
  const id = String(perusahaan?.id ?? "");
  if (!id) return;

  const code = String(groupCode || perusahaan?._groupCode || perusahaan?.kode_grup || "");
  const index = form.perusahaan_ids.map((value) => String(value)).indexOf(id);
  if (index > -1) {
    form.perusahaan_ids.splice(index, 1);
    delete areaByPerusahaanMap.value[getPerusahaanCode(perusahaan)];
    pruneDownstreamSelections();
    return;
  }

  form.perusahaan_ids.push(id);
  beginDataLoad();
  try {
    const result = await collectUnderPerusahaan(code, perusahaan);
    form.area_ids = mergeIds(form.area_ids, result.areaKeys);
    form.estate_ids = mergeIds(form.estate_ids, result.estateCodes);
    form.afdeling_ids = mergeIds(form.afdeling_ids, result.afdelingKeys);
    await ensureBloksForAfdelingKeys(result.afdelingKeys);
    mergeBlokIds(result.afdelingKeys);
    pruneDownstreamSelections();
  } finally {
    endDataLoad();
  }
};

const toggleArea = async (area, perusahaan, groupCode = "") => {
  const ptCode = getPerusahaanCode(perusahaan);
  const key = getAreaSelectionKey(ptCode, getAreaId(area));
  if (!key) return;

  const index = form.area_ids.indexOf(key);
  if (index > -1) {
    form.area_ids.splice(index, 1);
    delete estateByAreaMap.value[key];
    pruneDownstreamSelections();
    return;
  }

  form.area_ids.push(key);
  beginDataLoad();
  try {
    const estates = await ensureEstates(groupCode, ptCode, getAreaId(area));
    const estateCodes = estates.map((estate) => getEstateCode(estate)).filter(Boolean);
    await ensureAfdelingsLoaded(estateCodes);
    const afdelingKeys = afdelingKeysForEstates(estateCodes);
    form.estate_ids = mergeIds(form.estate_ids, estateCodes);
    form.afdeling_ids = mergeIds(form.afdeling_ids, afdelingKeys);
    await ensureBloksForAfdelingKeys(afdelingKeys);
    mergeBlokIds(afdelingKeys);
    pruneDownstreamSelections();
  } finally {
    endDataLoad();
  }
};

const toggleEstate = async (estate) => {
  const code = String(getEstateCode(estate));
  if (!code) return;

  const aliases = new Set(
    [code, String(estate?.id ?? "")].filter(Boolean),
  );
  const alreadySelected = form.estate_ids.some((id) => aliases.has(String(id)));

  if (alreadySelected) {
    form.estate_ids = form.estate_ids.filter((id) => !aliases.has(String(id)));
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
    await ensureAfdelingsLoaded([code]);
    const afdelingKeys = mergeAfdelingIds([code]);
    await ensureBloksForAfdelingKeys(afdelingKeys);
    mergeBlokIds(afdelingKeys);
    syncSelectedItemsFromIds();
    pruneDownstreamSelections();
  }
};

const toggleAfdeling = async (afdeling, estateCode = "") => {
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
    const nextBlokMap = { ...blokByAfdelingMap.value };
    delete nextBlokMap[selectionKey];
    blokByAfdelingMap.value = nextBlokMap;
    form.blok_ids = form.blok_ids.filter(
      (id) => parentAfdelingKeyFromBlok(id) !== selectionKey,
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
    await ensureBloksForAfdelingKeys([selectionKey]);
    mergeBlokIds([selectionKey]);
    syncSelectedItemsFromIds();
  }
};

const toggleAllInList = (codes, target) => {
  const isAllSelected =
    codes.length > 0 &&
    codes.every((code) => target.includes(code));

  if (isAllSelected) {
    return target.filter((id) => !codes.includes(String(id)));
  }

  return Array.from(new Set([
    ...target.map((id) => String(id)),
    ...codes,
  ]));
};

const toggleAllLayer = () => {
  const codes = allDataLayer.value
    .map((layer) => getLayerCode(layer))
    .filter((code) => !!code);
  form.layer_ids = toggleAllInList(codes, form.layer_ids);
};

const toggleAllTransaksi = () => {
  const codes = allDataTransaksi.value
    .map((transaksi) => getTransaksiCode(transaksi))
    .filter((code) => !!code);
  form.transaksi_ids = toggleAllInList(codes, form.transaksi_ids);
};

const togglePermission = (id) => {
  let targetArray = [];

  if (activePermissionTab.value === "menu") {
    targetArray = form.menu_ids;
  } else if (activePermissionTab.value === "layer") {
    targetArray = form.layer_ids;
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
    manageRoleStore.initDataGroup(),
    manageRoleStore.initDataLayer(),
    manageRoleStore.initDataTableTransaksi(),
  ]).catch(() => {
    // Pesan error sudah diisi store.
  });
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
                <th class="px-4 py-3 font-bold">Layer Data</th>
                <th class="px-4 py-3 font-bold">Transaksi</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="manageRoleStore.loadingList" class="border-t border-row">
                <td colspan="7" class="px-4 py-8 text-center text-muted">
                  Memuat data role...
                </td>
              </tr>

              <tr v-for="item in filteredRoles" :key="item.id" class="border-t border-row">
                <td class="px-4 py-3">{{ item.nama }}</td>
                <td class="px-4 py-3">{{ item.deskripsi }}</td>
                <td class="px-4 py-3">{{ item.akses_menu?.length ?? 0 }}</td>
                <td class="px-4 py-3">{{ item.akses_data?.length ?? 0 }}</td>
                <td class="px-4 py-3">{{ countRoleAccess(item, "layer") }}</td>
                <td class="px-4 py-3">{{ countRoleAccess(item, "transaksi") }}</td>
                <td class="px-4 py-3">
                  <button class="rounded-lg border border-tan bg-cream px-3 py-1.5 font-semibold text-brand"
                    @click="openEditModal(item)">
                    Edit
                  </button>
                </td>
              </tr>

              <tr v-if="!manageRoleStore.loadingList && filteredRoles.length === 0" class="border-t border-row">
                <td colspan="7" class="px-4 py-8 text-center text-muted">
                  Belum ada data role.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <AppModalTeleport>
    <div v-if="showFormModal" class="app-modal-backdrop bg-overlay">
      <div class="app-modal-panel app-modal-size-2xl w-full rounded-2xl bg-surface">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-18 font-bold">{{ pageTitle }}</h3>
          <button class="text-muted" @click="closeFormModal">✕</button>
        </div>

        <p v-if="manageRoleStore.errorMessage" class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ manageRoleStore.errorMessage }}
        </p>

        <form class="grid grid-cols-1 gap-3 md:grid-cols-2" @submit.prevent="submitForm">
          <div>
            <label class="mb-1 block text-label">Nama Role <span class="text-error">*</span></label>
            <input :value="form.nama" @input="onNamaInput" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 uppercase outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-label">Deskripsi <span class="text-error">*</span></label>
            <input :value="form.deskripsi" @input="onDeskripsiInput" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 uppercase outline-none" />
          </div>

          <div class="app-modal-permission-box md:col-span-2 rounded-xl border border-default p-4">
            <div class="app-modal-tabs mb-4 border-b border-default pb-3">
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
              <button type="button" class="rounded-xl px-4 py-2 text-size-sm font-semibold transition" :class="activePermissionTab === 'layer'
                ? 'bg-brand text-on-brand'
                : 'border border-tan bg-cream text-brand'" @click="changeContent('layer')">
                Akses Layer Data
              </button>
              <button type="button" class="rounded-xl px-4 py-2 text-size-sm font-semibold transition" :class="activePermissionTab === 'transaksi'
                ? 'bg-brand text-on-brand'
                : 'border border-tan bg-cream text-brand'" @click="changeContent('transaksi')">
                Akses Transaksi
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
                  <input :checked="form.menu_ids.map((id) => String(id)).includes(String(menu.id))" type="checkbox"
                    class="h-4 w-4" @change="toggleMenuPermission(menu.id)" />
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
                  <p class="font-semibold text-brand">Level 1 - Group</p>
                </div>
                <div v-if="!allDataGroup.length" class="text-muted">
                  Belum ada data group.
                </div>
                <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <label v-for="group in allDataGroup" :key="getGroupCode(group) || group.id"
                    class="flex items-center gap-2 rounded-lg border border-default p-2">
                    <input :checked="isGroupSelected(group)" type="checkbox" class="h-4 w-4"
                      @change="toggleGroup(group)" />
                    <span>{{ group.nama_grup ?? group.nama ?? getGroupCode(group) }}</span>
                  </label>
                </div>
              </div>

              <div v-if="loadingHierarchy" class="mb-4 rounded-xl border border-default p-4 text-muted">
                Memuat data hierarchy (perusahaan, area, estate, afdeling, blok)...
              </div>

              <div v-if="groupedPerusahaanByGroup.length" class="mb-4 rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 2 - Perusahaan</p>
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedPerusahaanByGroup" :key="group.groupKey"
                    class="rounded-lg border border-default p-3">
                    <p class="mb-2 text-size-sm font-semibold text-label">
                      Group: {{ group.group?.nama_grup ?? group.group?.nama ?? group.groupKey }}
                    </p>
                    <div v-if="!group.perusahaan.length" class="text-muted">
                      Tidak ada perusahaan untuk group ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="perusahaan in group.perusahaan" :key="perusahaan.id"
                        class="flex items-center gap-2 rounded-lg border border-default p-2">
                        <input :checked="isPerusahaanSelected(perusahaan)" type="checkbox" class="h-4 w-4"
                          @change="togglePerusahaan(perusahaan, group.groupKey)" />
                        <span>{{ perusahaan.nama_pt ?? perusahaan.nama ?? perusahaan.title ??
                          getPerusahaanCode(perusahaan) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedAreaByPerusahaan.length" class="mb-4 rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 3 - Area</p>
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedAreaByPerusahaan" :key="group.perusahaanKey"
                    class="rounded-lg border border-default p-3">
                    <p class="mb-2 text-size-sm font-semibold text-label">
                      Perusahaan: {{ group.perusahaan?.nama_pt ?? group.perusahaan?.nama ?? group.perusahaanKey }}
                    </p>
                    <div v-if="!group.areas.length" class="text-muted">
                      Tidak ada area untuk perusahaan ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="area in group.areas"
                        :key="getAreaSelectionKey(group.perusahaanKey, getAreaId(area))"
                        class="flex items-center gap-2 rounded-lg border border-default p-2">
                        <input :checked="isAreaSelected(group.perusahaanKey, area)" type="checkbox" class="h-4 w-4"
                          @change="toggleArea(area, group.perusahaan, group.groupCode)" />
                        <span>{{ area.nama_area ?? area.nama ?? getAreaId(area) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedEstateByArea.length" class="mb-4 rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 4 - Estate</p>
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedEstateByArea" :key="group.areaKey"
                    class="rounded-lg border border-default p-3">
                    <p class="mb-2 text-size-sm font-semibold text-label">
                      Area: {{ group.area?.nama_area ?? group.area?.nama ?? getAreaId(group.area) }}
                      <span class="text-muted">
                        · {{ group.perusahaan?.nama_pt ?? group.perusahaan?.nama ?? group.perusahaanKey }}
                      </span>
                    </p>
                    <div v-if="!group.estates.length" class="text-muted">
                      Tidak ada estate untuk area ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="estate in group.estates" :key="getEstateCode(estate)"
                        class="flex items-center gap-2 rounded-lg border border-default p-2">
                        <input :checked="isEstateSelected(estate)" type="checkbox" class="h-4 w-4"
                          @change="toggleEstate(estate)" />
                        <span>{{ estate.nama_estate ?? estate.nama ?? estate.title ?? getEstateCode(estate) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedAfdelingByEstate.length" class="rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 5 - Afdeling</p>
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
                        <input :checked="isAfdelingSelected(group.estate, afdeling)" type="checkbox" class="h-4 w-4"
                          @change="toggleAfdeling(afdeling, group.estateKey)" />
                        <span>{{ afdeling.nama_afdeling ?? afdeling.nama ?? afdeling.title ?? getAfdelingCode(afdeling)
                        }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="groupedBlokByAfdeling.length" class="mt-4 rounded-xl border border-default p-4">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <p class="font-semibold text-brand">Level 6 - Blok</p>
                </div>

                <div class="space-y-3">
                  <div v-for="group in groupedBlokByAfdeling" :key="group.mapKey"
                    class="rounded-lg border border-default p-3">
                    <p class="mb-2 text-size-sm font-semibold text-label">
                      Afdeling: {{ group.afdeling?.nama_afdeling ?? group.afdeling?.nama ??
                      getAfdelingCode(group.afdeling) }}
                      <span class="text-muted">
                        · Estate {{ group.estate?.nama_estate ?? group.estate?.nama ?? group.estateKey }}
                      </span>
                    </p>
                    <div v-if="loadingHierarchy && !group.bloks.length" class="text-muted">
                      Memuat blok...
                    </div>
                    <div v-else-if="!group.bloks.length" class="text-muted">
                      Tidak ada blok untuk afdeling ini.
                    </div>
                    <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <label v-for="blok in group.bloks"
                        :key="getBlokSelectionKey(group.estateKey, getAfdelingCode(group.afdeling), getBlokCode(blok))"
                        class="flex items-center gap-2 rounded-lg border border-default p-2">
                        <input :checked="isBlokSelected(group.estateKey, group.afdeling, blok)" type="checkbox"
                          class="h-4 w-4" @change="toggleBlok(blok, group.estateKey, group.afdeling)" />
                        <span>{{ blok.nama_blok ?? blok.nama ?? getBlokCode(blok) }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-show="activePermissionTab === 'layer'" class="rounded-xl border border-default p-4">
              <div class="mb-3 flex items-center justify-between gap-2">
                <p class="font-semibold text-brand">List layer data</p>
                <button type="button"
                  class="rounded-lg border border-tan bg-cream px-3 py-1.5 text-size-sm font-semibold text-brand"
                  @click="toggleAllLayer">
                  Ceklis Semua
                </button>
              </div>

              <div v-if="manageRoleStore.loadingLayer" class="text-muted">
                Memuat data layer...
              </div>
              <div v-else-if="!allDataLayer.length" class="text-muted">
                Belum ada data layer.
              </div>

              <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                <label v-for="layer in allDataLayer" :key="getLayerCode(layer)"
                  class="flex items-center gap-2 rounded-lg border border-default p-2">
                  <input :checked="form.layer_ids.includes(getLayerCode(layer))" type="checkbox" class="h-4 w-4"
                    @change="togglePermission(getLayerCode(layer))" />
                  <span>{{ layer?.title ?? layer?.nama_table_transaksi ?? layer }}</span>
                </label>
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

              <div v-if="manageRoleStore.loadingTransaction" class="text-muted">
                Memuat data transaksi...
              </div>
              <div v-else-if="!allDataTransaksi.length" class="text-muted">
                Belum ada data transaksi.
              </div>

              <div v-else class="grid grid-cols-1 gap-2 md:grid-cols-2">
                <label v-for="transaksi in allDataTransaksi" :key="getTransaksiCode(transaksi)"
                  class="flex items-center gap-2 rounded-lg border border-default p-2">
                  <input :checked="form.transaksi_ids.includes(getTransaksiCode(transaksi))" type="checkbox"
                    class="h-4 w-4" @change="togglePermission(getTransaksiCode(transaksi))" />
                  <span>{{ transaksi?.label ?? transaksi?.title ?? transaksi?.table }}</span>
                </label>
              </div>
            </div>
          </div>

          <div class="md:col-span-2 mt-2 flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              @click="closeFormModal">
              Batal
            </button>
            <button type="submit"
              class="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="saveDisabled">
              <span v-if="saveDisabled"
                class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              {{ saveButtonLabel }}
            </button>
          </div>
        </form>
      </div>
    </div>
    </AppModalTeleport>
  </main>
</template>

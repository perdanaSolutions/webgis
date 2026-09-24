<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import {
  useManageMenuStore,
  type CreateMenuPayload,
  type MenuFormState,
  type MenuItem,
  type UpdateMenuPayload,
} from "~/stores/manageMenuStore";
import { useAuthStore } from "~/stores/authStore";
import { menuIconPath } from "~/utils/menuThemeOptions";
import { menuSubtreeDepth } from "~/utils/menuTree";

defineOptions({
  name: "MenusManagementPage",
});

const manageMenuStore = useManageMenuStore();
const authStore = useAuthStore();

const search = ref("");
const showFormModal = ref(false);
const showDeleteModal = ref(false);
const formMode = ref<"create" | "edit">("create");
const selectedMenuId = ref<string>("");
const selectedMenu = ref<MenuItem | null>(null);

const form = reactive<MenuFormState>({
  title: "",
  description: "",
  bg_class: "bg-blue-50",
  icon_class: "text-blue-500",
  arrow_class: "text-blue-500",
  to: "",
  icon: "report",
  order_position: 0,
  parent_id: "",
});

const submitLoading = computed(
  () => manageMenuStore.loadingCreate || manageMenuStore.loadingUpdate,
);

const informasiUser = computed(() => authStore.user);

const pageTitle = computed(() =>
  formMode.value === "create" ? "Tambah Menu" : "Edit Menu",
);

const flatMenus = computed(() => manageMenuStore.flatMenus);

const blockedParentIds = computed(() => {
  if (formMode.value !== "edit" || !selectedMenu.value) return new Set<string>();
  const ids = new Set<string>();
  const walk = (node: MenuItem) => {
    ids.add(node.id);
    node.children.forEach(walk);
  };
  walk(selectedMenu.value);
  return ids;
});

const movingDepth = computed(() =>
  formMode.value === "edit" ? menuSubtreeDepth(selectedMenu.value) : 0,
);

const parentOptions = computed(() =>
  flatMenus.value.filter((menu) => {
    if (menu.level >= 3) return false;
    if (blockedParentIds.value.has(menu.id)) return false;
    return menu.level + 1 + movingDepth.value <= 3;
  }),
);

const formLevel = computed(() => {
  if (!form.parent_id) return 1;
  const parent = flatMenus.value.find((menu) => menu.id === form.parent_id);
  return Math.min(3, (parent?.level ?? 1) + 1);
});

const parentNameById = computed(() => {
  const names = new Map<string, string>();
  flatMenus.value.forEach((menu) => names.set(menu.id, menu.title));
  return names;
});

const filteredMenus = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  if (!keyword) return flatMenus.value;

  return flatMenus.value.filter((item) => {
    const parentName = item.parent_id
      ? parentNameById.value.get(item.parent_id) ?? ""
      : "";
    return (
      item.title.toLowerCase().includes(keyword) ||
      item.description.toLowerCase().includes(keyword) ||
      item.to.toLowerCase().includes(keyword) ||
      item.icon.toLowerCase().includes(keyword) ||
      parentName.toLowerCase().includes(keyword)
    );
  });
});

const deleteHasChildren = computed(
  () => (selectedMenu.value?.children.length ?? 0) > 0,
);

function resetForm() {
  form.title = "";
  form.description = "";
  form.bg_class = "bg-blue-50";
  form.icon_class = "text-blue-500";
  form.arrow_class = "text-blue-500";
  form.to = "";
  form.icon = "report";
  form.order_position = 0;
  form.parent_id = "";
}

function fillFormFromMenu(menu: MenuItem) {
  form.title = menu.title;
  form.description = menu.description;
  form.bg_class = menu.bg_class || "bg-blue-50";
  form.icon_class = menu.icon_class || "text-blue-500";
  form.arrow_class = menu.arrow_class || "text-blue-500";
  form.to = menu.to;
  form.icon = menu.icon || "report";
  form.order_position = Number(menu.order_position ?? 0);
  form.parent_id = menu.parent_id ?? "";
}

function openCreateModal(parentId: string | null = null) {
  formMode.value = "create";
  selectedMenuId.value = "";
  selectedMenu.value = null;
  resetForm();
  form.parent_id = parentId ?? "";
  manageMenuStore.clearError();
  showFormModal.value = true;
}

function openEditModal(menu: MenuItem) {
  formMode.value = "edit";
  selectedMenuId.value = menu.id;
  selectedMenu.value = menu;
  fillFormFromMenu(menu);
  manageMenuStore.clearError();
  showFormModal.value = true;
}

function closeFormModal() {
  showFormModal.value = false;
}

function openDeleteModal(menu: MenuItem) {
  selectedMenuId.value = menu.id;
  selectedMenu.value = menu;
  manageMenuStore.clearError();
  showDeleteModal.value = true;
}

function closeDeleteModal() {
  showDeleteModal.value = false;
}

function parentLabel(menu: MenuItem) {
  if (!menu.parent_id) return "Menu utama";
  return parentNameById.value.get(menu.parent_id) ?? "-";
}

async function submitForm() {
  const payload: CreateMenuPayload | UpdateMenuPayload = {
    title: form.title,
    description: form.description,
    bg_class: form.bg_class,
    icon_class: form.icon_class,
    arrow_class: form.arrow_class,
    to: form.to,
    icon: form.icon,
    order_position: Number(form.order_position ?? 0),
    parent_id: form.parent_id || null,
  };

  try {
    if (formMode.value === "create") {
      await manageMenuStore.createMenu(payload);
    } else {
      await manageMenuStore.updateMenu(selectedMenuId.value, payload);
    }

    showFormModal.value = false;
    await manageMenuStore.fetchMenus();
  } catch {
    // Pesan error sudah disimpan di store.
  }
}

async function confirmDelete() {
  if (deleteHasChildren.value) return;

  try {
    await manageMenuStore.deleteMenu(selectedMenuId.value);
    showDeleteModal.value = false;
    await manageMenuStore.fetchMenus();
  } catch {
    // Pesan error sudah disimpan di store.
  }
}

async function gotoUsers() {
  await navigateTo("/users");
}

onMounted(async () => {
  if (informasiUser.value?.role !== "superadmin") {
    await navigateTo("/dashboard");
    return;
  }

  await manageMenuStore.fetchMenus();
});
</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Management Menu" brand-subtitle="Kelola menu dashboard sampai 3 tingkat" />

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center gap-3">
        <button type="button" aria-label="Back"
          class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-light bg-surface text-icon shadow-sm transition-all duration-200 hover-border-navy hover-bg-slate-light hover-text-navy"
          @click="gotoUsers">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
            stroke="currentColor" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>

        <p class="text-size-sm font-semibold tracking-wide text-subtitle">
          Management Menu
        </p>
      </div>

      <section class="rounded-2xl border border-default bg-surface p-5">
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-20 font-bold">Daftar Menu</h2>
            <p class="text-muted">
              Susun menu utama, submenu, dan menu tingkat ketiga.
            </p>
          </div>

          <button class="rounded-full bg-brand px-5 py-2.5 font-semibold text-on-brand" @click="openCreateModal(null)">
            + Tambah Menu
          </button>
        </div>

        <div class="mb-4">
          <input v-model="search" type="text" placeholder="Cari title / deskripsi / route / induk..."
            class="h-11 w-full rounded-xl border border-default px-4 outline-none placeholder-text-placeholder" />
        </div>

        <p v-if="manageMenuStore.errorMessage && !showFormModal && !showDeleteModal"
          class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ manageMenuStore.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-4 py-3 font-bold">Menu</th>
                <th class="px-4 py-3 font-bold">Level</th>
                <th class="px-4 py-3 font-bold">Induk</th>
                <th class="px-4 py-3 font-bold">Route</th>
                <th class="px-4 py-3 font-bold">Icon</th>
                <th class="px-4 py-3 font-bold">Urutan</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="manageMenuStore.loadingList" class="border-t border-row">
                <td colspan="7" class="px-4 py-8 text-center text-muted">
                  Memuat data menu...
                </td>
              </tr>

              <tr v-for="item in filteredMenus" :key="item.id" class="border-t border-row">
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2" :style="{ paddingLeft: `${(item.level - 1) * 20}px` }">
                    <span v-if="item.level > 1" class="text-muted">↳</span>
                    <div>
                      <p class="font-semibold">{{ item.title }}</p>
                      <p class="text-size-sm text-muted">{{ item.description }}</p>
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3">
                  <span class="rounded-full bg-surface-warm px-2.5 py-1 text-size-sm font-semibold text-brand">
                    Level {{ item.level }}
                  </span>
                </td>
                <td class="px-4 py-3">{{ parentLabel(item) }}</td>
                <td class="px-4 py-3">{{ item.to || "-" }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-surface-warm text-brand">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
                        stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                          :d="menuIconPath(item.icon || 'report')" />
                      </svg>
                    </span>
                    <span class="text-size-sm text-label">{{ item.icon }}</span>
                  </div>
                </td>
                <td class="px-4 py-3">{{ item.order_position }}</td>
                <td class="px-4 py-3">
                  <div class="flex flex-wrap items-center gap-2">
                    <button v-if="item.level < 3"
                      class="rounded-lg border border-default bg-surface px-3 py-1.5 font-semibold text-brand"
                      @click="openCreateModal(item.id)">
                      Submenu
                    </button>
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

              <tr v-if="!manageMenuStore.loadingList && manageMenuStore.hasMenus && !filteredMenus.length"
                class="border-t border-row">
                <td colspan="7" class="px-4 py-8 text-center text-muted">
                  Tidak ada menu yang cocok dengan pencarian.
                </td>
              </tr>

              <tr v-if="!manageMenuStore.loadingList && !manageMenuStore.hasMenus" class="border-t border-row">
                <td colspan="7" class="px-4 py-8 text-center text-muted">
                  Belum ada data menu.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="showFormModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
      <div class="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-surface p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-18 font-bold">{{ pageTitle }}</h3>
          <button class="text-muted" @click="closeFormModal">✕</button>
        </div>

        <p v-if="manageMenuStore.errorMessage" class="mb-4 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ manageMenuStore.errorMessage }}
        </p>

        <div class="mb-5 rounded-2xl border border-default bg-page p-4">
          <div class="mb-3 flex items-center justify-between gap-3">
            <p class="text-size-sm font-semibold text-brand">Preview Menu</p>
            <span class="rounded-full bg-surface-warm px-2.5 py-1 text-size-sm font-semibold text-brand">
              Level {{ formLevel }}
            </span>
          </div>
          <div class="flex items-center gap-4 rounded-2xl border border-default bg-surface p-4">
            <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl" :class="form.bg_class">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24"
                stroke="currentColor" :class="form.icon_class">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" :d="menuIconPath(form.icon)" />
              </svg>
            </div>

            <div class="min-w-0 flex-1">
              <p class="truncate text-16 font-bold leading-tight">
                {{ form.title || "Judul Menu" }}
              </p>
              <p class="mt-1 line-clamp-2 text-14 leading-snug text-muted">
                {{ form.description || "Deskripsi menu akan tampil di sini." }}
              </p>
            </div>

            <span class="text-16 font-bold" :class="form.arrow_class">→</span>
          </div>
        </div>

        <form class="grid grid-cols-1 gap-4 md:grid-cols-2" @submit.prevent="submitForm">
          <div class="md:col-span-2">
            <label class="mb-1 block text-label">Menu induk</label>
            <select v-model="form.parent_id"
              class="h-11 w-full rounded-xl border border-default bg-surface px-3 outline-none">
              <option value="">Menu utama (Level 1)</option>
              <option v-for="option in parentOptions" :key="option.id" :value="option.id">
                {{ option.level === 2 ? "— " : "" }}{{ option.title }} (Level {{ option.level }})
              </option>
            </select>
            <p class="mt-1 text-size-sm text-muted">
              Level 1 adalah menu utama. Level 2 berada di bawah level 1. Level 3 berada di bawah level 2.
            </p>
          </div>

          <div>
            <label class="mb-1 block text-label">Title</label>
            <input v-model="form.title" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-label">Route (to)</label>
            <input v-model="form.to" :required="formLevel === 3" type="text" placeholder="/dashboard"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
            <p v-if="formLevel < 3" class="mt-1 text-size-sm text-muted">
              Route boleh kosong jika menu ini hanya pengelompok submenu.
            </p>
          </div>

          <div class="md:col-span-2">
            <label class="mb-1 block text-label">Description</label>
            <input v-model="form.description" required type="text"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
          </div>

          <div class="md:col-span-2">
            <label class="mb-2 block font-semibold text-brand">Warna Background (bg_class)</label>
            <MenuBgClassPicker v-model="form.bg_class" />
          </div>

          <div>
            <label class="mb-2 block font-semibold text-brand">Warna Icon (icon_class)</label>
            <MenuTextClassPicker v-model="form.icon_class" preview-type="icon" :preview-icon="form.icon" />
          </div>

          <div>
            <label class="mb-2 block font-semibold text-brand">Warna Panah (arrow_class)</label>
            <MenuTextClassPicker v-model="form.arrow_class" preview-type="arrow" />
          </div>

          <div class="md:col-span-2">
            <label class="mb-2 block font-semibold text-brand">Icon Menu</label>
            <MenuIconPicker v-model="form.icon" />
          </div>

          <div>
            <label class="mb-1 block text-label">order_position</label>
            <input v-model.number="form.order_position" required type="number" min="0"
              class="h-11 w-full rounded-xl border border-default px-3 outline-none" />
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

    <div v-if="showDeleteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
      <div class="w-full max-w-md rounded-2xl bg-surface p-5">
        <h3 class="text-18 font-bold">Konfirmasi Hapus</h3>
        <p v-if="deleteHasChildren" class="mt-2 text-error">
          "{{ selectedMenu?.title }}" masih punya submenu. Hapus submenu di bawahnya terlebih dahulu.
        </p>
        <p v-else class="mt-2 text-muted">
          Apakah Anda yakin ingin menghapus menu "{{ selectedMenu?.title }}"?
        </p>
        <p v-if="manageMenuStore.errorMessage" class="mt-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ manageMenuStore.errorMessage }}
        </p>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
            @click="closeDeleteModal">
            Batal
          </button>
          <button
            class="rounded-xl border border-error bg-error-light px-4 py-2 font-semibold text-error disabled:opacity-50"
            :disabled="manageMenuStore.loadingDelete || deleteHasChildren" @click="confirmDelete">
            {{ manageMenuStore.loadingDelete ? "Menghapus..." : "Hapus" }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

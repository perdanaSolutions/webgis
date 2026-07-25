<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import Header from "~/components/Header.vue";
import {
  useManageMenuStore,
  type CreateMenuPayload,
  type MenuItem,
  type UpdateMenuPayload,
} from "~/stores/manageMenuStore";
import { useAuthStore } from "~/stores/authStore";

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

const form = reactive<CreateMenuPayload>({
  title: "",
  description: "",
  bg_class: "bg-blue-50",
  icon_class: "text-blue-500",
  arrow_class: "text-blue-500",
  to: "",
  icon: "",
  order_position: 0,
});

const submitLoading = computed(
  () => manageMenuStore.loadingCreate || manageMenuStore.loadingUpdate,
);

const informasiUser = computed(() => authStore.user);

const pageTitle = computed(() =>
  formMode.value === "create" ? "Tambah Menu" : "Edit Menu",
);

const filteredMenus = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  if (!keyword) return manageMenuStore.menus;

  return manageMenuStore.menus.filter((item) => {
    return (
      String(item.title ?? "").toLowerCase().includes(keyword) ||
      String(item.description ?? "").toLowerCase().includes(keyword) ||
      String(item.to ?? "").toLowerCase().includes(keyword) ||
      String(item.icon ?? "").toLowerCase().includes(keyword)
    );
  });
});

function resetForm() {
  form.title = "";
  form.description = "";
  form.bg_class = "bg-blue-50";
  form.icon_class = "text-blue-500";
  form.arrow_class = "text-blue-500";
  form.to = "";
  form.icon = "";
  form.order_position = 0;
}

function fillFormFromMenu(menu: MenuItem) {
  form.title = String(menu.title ?? "");
  form.description = String(menu.description ?? "");
  form.bg_class = String(menu.bg_class ?? "bg-blue-50");
  form.icon_class = String(menu.icon_class ?? "text-blue-500");
  form.arrow_class = String(menu.arrow_class ?? "text-blue-500");
  form.to = String(menu.to ?? "");
  form.icon = String(menu.icon ?? "");
  form.order_position = Number(menu.order_position ?? 0);
}

function openCreateModal() {
  formMode.value = "create";
  selectedMenuId.value = "";
  resetForm();
  showFormModal.value = true;
}

function openEditModal(menu: MenuItem) {
  formMode.value = "edit";
  selectedMenuId.value = menu.id;
  fillFormFromMenu(menu);
  showFormModal.value = true;
}

function closeFormModal() {
  showFormModal.value = false;
}

function openDeleteModal(menu: MenuItem) {
  selectedMenuId.value = menu.id;
  showDeleteModal.value = true;
}

function closeDeleteModal() {
  showDeleteModal.value = false;
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
  };

  if (formMode.value === "create") {
    await manageMenuStore.createMenu(payload as CreateMenuPayload);
  } else {
    await manageMenuStore.updateMenu(
      selectedMenuId.value,
      payload as UpdateMenuPayload,
    );
  }

  showFormModal.value = false;
  await manageMenuStore.fetchMenus();
}

async function confirmDelete() {
  await manageMenuStore.deleteMenu(selectedMenuId.value);
  showDeleteModal.value = false;
  await manageMenuStore.fetchMenus();
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
  <main class="min-h-screen bg-[#FBFAF8] text-[14px] text-[#2E1F18]">
    <Header brand-title="Management Menu" brand-subtitle="Kelola data menu dashboard" />

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center gap-3">
        <button type="button" aria-label="Back"
          class="flex h-8 w-8 items-center justify-center rounded-full border border-[#D8DEE8] bg-white text-[#566074] shadow-sm transition-all duration-200 hover:border-[#1A315B] hover:bg-slate-50 hover:text-[#1A315B]"
          @click="gotoUsers">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
            stroke="currentColor" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>

        <p class="text-sm font-semibold tracking-wide text-[#333d4e]">
          Management Menu
        </p>
      </div>

      <section class="rounded-2xl border border-[#EEE6DE] bg-white p-5">
        <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 class="text-[20px] font-bold">Daftar Menu</h2>
            <p class="text-[#8A817A]">Kelola menu modul dashboard.</p>
          </div>

          <button class="rounded-full bg-[#4D392A] px-5 py-2.5 font-semibold text-white" @click="openCreateModal">
            + Tambah Menu
          </button>
        </div>

        <div class="mb-4">
          <input v-model="search" type="text" placeholder="Cari title / deskripsi / route..."
            class="h-11 w-full rounded-xl border border-[#EEE6DE] px-4 outline-none placeholder:text-[#A6A29D]" />
        </div>

        <p v-if="manageMenuStore.errorMessage" class="mb-3 rounded-xl bg-red-50 px-4 py-3 text-red-600">
          {{ manageMenuStore.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-[#EEE6DE]">
          <table class="min-w-full bg-white">
            <thead class="bg-[#F8F3EE] text-left text-[#4D392A]">
              <tr>
                <th class="px-4 py-3 font-bold">Title</th>
                <th class="px-4 py-3 font-bold">Deskripsi</th>
                <th class="px-4 py-3 font-bold">Route</th>
                <th class="px-4 py-3 font-bold">Icon</th>
                <th class="px-4 py-3 font-bold">Order</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="manageMenuStore.loadingList" class="border-t border-[#F0E8E0]">
                <td colspan="6" class="px-4 py-8 text-center text-[#8A817A]">
                  Memuat data menu...
                </td>
              </tr>

              <tr v-for="item in filteredMenus" :key="item.id" class="border-t border-[#F0E8E0]">
                <td class="px-4 py-3">{{ item.title }}</td>
                <td class="px-4 py-3">{{ item.description }}</td>
                <td class="px-4 py-3">{{ item.to }}</td>
                <td class="px-4 py-3">{{ item.icon }}</td>
                <td class="px-4 py-3">{{ item.order_position }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <button
                      class="rounded-lg border border-[#DDD1C7] bg-[#FFF8F2] px-3 py-1.5 font-semibold text-[#4D392A]"
                      @click="openEditModal(item)">
                      Edit
                    </button>
                    <button class="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 font-semibold text-red-600"
                      @click="openDeleteModal(item)">
                      Hapus
                    </button>
                  </div>
                </td>
              </tr>

              <tr v-if="!manageMenuStore.loadingList && !manageMenuStore.hasMenus" class="border-t border-[#F0E8E0]">
                <td colspan="6" class="px-4 py-8 text-center text-[#8A817A]">
                  Belum ada data menu.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="showFormModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-3xl rounded-2xl bg-white p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-[18px] font-bold">{{ pageTitle }}</h3>
          <button class="text-[#8A817A]" @click="closeFormModal">✕</button>
        </div>

        <form class="grid grid-cols-1 gap-3 md:grid-cols-2" @submit.prevent="submitForm">
          <div>
            <label class="mb-1 block text-[#6F645B]">Title</label>
            <input v-model="form.title" required type="text"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">Route (to)</label>
            <input v-model="form.to" required type="text" placeholder="/dashboard"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div class="md:col-span-2">
            <label class="mb-1 block text-[#6F645B]">Description</label>
            <input v-model="form.description" required type="text"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">bg_class</label>
            <input v-model="form.bg_class" required type="text" placeholder="bg-blue-50"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">icon_class</label>
            <input v-model="form.icon_class" required type="text" placeholder="text-blue-500"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">arrow_class</label>
            <input v-model="form.arrow_class" required type="text" placeholder="text-blue-500"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">icon</label>
            <input v-model="form.icon" required type="text" placeholder="report"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] px-3 outline-none" />
          </div>

          <div>
            <label class="mb-1 block text-[#6F645B]">order_position</label>
            <input v-model.number="form.order_position" required type="number" min="0"
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

    <div v-if="showDeleteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-md rounded-2xl bg-white p-5">
        <h3 class="text-[18px] font-bold">Konfirmasi Hapus</h3>
        <p class="mt-2 text-[#8A817A]">
          Apakah Anda yakin ingin menghapus menu ini?
        </p>

        <div class="mt-5 flex justify-end gap-2">
          <button class="rounded-xl border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-2 font-semibold text-[#4D392A]"
            @click="closeDeleteModal">
            Batal
          </button>
          <button
            class="rounded-xl border border-red-200 bg-red-50 px-4 py-2 font-semibold text-red-600 disabled:opacity-50"
            :disabled="manageMenuStore.loadingDelete" @click="confirmDelete">
            {{ manageMenuStore.loadingDelete ? "Menghapus..." : "Hapus" }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { MENU_TEXT_OPTIONS, menuIconPath } from "~/utils/menuThemeOptions";

const props = defineProps<{
  previewType?: "icon" | "arrow";
  previewIcon?: string;
}>();

const model = defineModel<string>({ required: true });

const previewType = computed(() => props.previewType ?? "icon");
const placeholder = computed(() =>
  previewType.value === "arrow" ? "Cari warna panah" : "Cari warna icon",
);

const options = computed(() => {
  if (MENU_TEXT_OPTIONS.some((item) => item.value === model.value)) {
    return MENU_TEXT_OPTIONS;
  }

  return [
    {
      value: model.value,
      label: `Tersimpan (${model.value || "kosong"})`,
      swatch: "bg-slate-icon",
    },
    ...MENU_TEXT_OPTIONS,
  ];
});

function onPick(value: unknown) {
  if (value == null || value === "") return;
  model.value = String(value);
}
</script>

<template>
  <v-autocomplete
    :model-value="model"
    class="bp-autocomplete"
    :items="options"
    item-title="label"
    item-value="value"
    :placeholder="placeholder"
    variant="solo"
    flat
    density="comfortable"
    hide-details
    single-line
    color="#638840"
    base-color="#d5dcc8"
    menu-icon="mdi-chevron-down"
    autocomplete="off"
    no-data-text="Tidak ditemukan"
    :menu-props="{ contentClass: 'bp-filter-menu', zIndex: 2600 }"
    @update:model-value="onPick"
  >
    <template #prepend-inner>
      <svg
        v-if="previewType === 'icon'"
        xmlns="http://www.w3.org/2000/svg"
        class="h-5 w-5 shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        :class="model"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.7"
          :d="menuIconPath(previewIcon || 'report')"
        />
      </svg>
      <span v-else class="text-16 font-bold" :class="model">→</span>
    </template>
    <template #item="{ props: itemProps, item }">
      <v-list-item v-bind="itemProps">
        <template #prepend>
          <span class="h-4 w-4 shrink-0 rounded-full border border-default" :class="item.swatch" />
        </template>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { MENU_ICON_OPTIONS, menuIconPath } from "~/utils/menuThemeOptions";

const model = defineModel<string>({ required: true });

const options = computed(() => {
  if (MENU_ICON_OPTIONS.some((item) => item.value === model.value)) {
    return MENU_ICON_OPTIONS;
  }

  return [
    {
      value: model.value,
      label: model.value || "Tersimpan",
    },
    ...MENU_ICON_OPTIONS,
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
    placeholder="Cari icon menu"
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
        xmlns="http://www.w3.org/2000/svg"
        class="h-5 w-5 shrink-0 text-brand"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.7"
          :d="menuIconPath(model)"
        />
      </svg>
    </template>
    <template #item="{ props: itemProps, item }">
      <v-list-item v-bind="itemProps">
        <template #prepend>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 shrink-0 text-brand"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.7"
              :d="menuIconPath(item.value)"
            />
          </svg>
        </template>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>

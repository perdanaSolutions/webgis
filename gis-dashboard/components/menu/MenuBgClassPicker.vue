<script setup lang="ts">
import { computed } from "vue";
import { MENU_BG_OPTIONS } from "~/utils/menuThemeOptions";

const model = defineModel<string>({ required: true });

const options = computed(() => {
  if (MENU_BG_OPTIONS.some((item) => item.value === model.value)) {
    return MENU_BG_OPTIONS;
  }

  return [
    {
      value: model.value,
      label: `Tersimpan (${model.value || "kosong"})`,
    },
    ...MENU_BG_OPTIONS,
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
    placeholder="Cari warna background"
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
      <span class="h-5 w-5 shrink-0 rounded-md border border-default" :class="model" />
    </template>
    <template #item="{ props: itemProps, item }">
      <v-list-item v-bind="itemProps">
        <template #prepend>
          <span class="h-5 w-5 shrink-0 rounded-md border border-default" :class="item.value" />
        </template>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>

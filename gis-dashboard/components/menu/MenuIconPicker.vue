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
      label: model.value || "Custom",
    },
    ...MENU_ICON_OPTIONS,
  ];
});
</script>

<template>
  <div>
    <div class="grid grid-cols-3 gap-2 sm:grid-cols-4">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="flex flex-col items-center gap-2 rounded-xl border p-3 transition-all duration-200"
        :class="
          model === option.value
            ? 'picker-selected ring-2 ring-tan'
            : 'picker-default hover:shadow-sm'
        "
        :title="option.label"
        @click="model = option.value"
      >
        <span
          class="flex h-11 w-11 items-center justify-center rounded-2xl bg-surface-warm text-brand"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.7"
              :d="menuIconPath(option.value)"
            />
          </svg>
        </span>
        <span class="text-center text-11 font-semibold text-brand">
          {{ option.label }}
        </span>
      </button>
    </div>

    <p class="mt-2 text-size-xs text-muted">
      Terpilih: <span class="font-semibold text-brand">{{ model }}</span>
    </p>
  </div>
</template>

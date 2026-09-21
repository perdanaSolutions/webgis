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
      label: "Custom",
      ring: "ring-slate-300",
    },
    ...MENU_BG_OPTIONS,
  ];
});
</script>

<template>
  <div>
    <div class="grid grid-cols-4 gap-2 sm:grid-cols-6">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="group flex flex-col items-center gap-1.5 rounded-xl border p-2 transition-all duration-200"
        :class="
          model === option.value
            ? `picker-selected ring-2 ${option.ring}`
            : 'picker-default hover:shadow-sm'
        "
        :title="option.label"
        @click="model = option.value"
      >
        <span
          class="flex h-10 w-10 items-center justify-center rounded-xl shadow-inner"
          :class="option.value"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 text-slate-icon opacity-70"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.7"
              d="M4 7h16v10H4V7Z"
            />
          </svg>
        </span>
        <span class="text-11 font-medium text-label">{{ option.label }}</span>
      </button>
    </div>
    <p class="mt-2 text-size-xs text-muted">
      Terpilih: <span class="font-semibold text-brand">{{ model }}</span>
    </p>
  </div>
</template>

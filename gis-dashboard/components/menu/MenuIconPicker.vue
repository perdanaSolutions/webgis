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
            ? 'border-[#4D392A] bg-[#FFF8F2] ring-2 ring-[#C9B5A5]'
            : 'border-[#EEE6DE] bg-white hover:border-[#D8CFC6] hover:shadow-sm'
        "
        :title="option.label"
        @click="model = option.value"
      >
        <span
          class="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#F8F3EE] text-[#4D392A]"
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
        <span class="text-center text-[11px] font-semibold text-[#4D392A]">
          {{ option.label }}
        </span>
      </button>
    </div>

    <p class="mt-2 text-xs text-[#8A817A]">
      Terpilih: <span class="font-semibold text-[#4D392A]">{{ model }}</span>
    </p>
  </div>
</template>

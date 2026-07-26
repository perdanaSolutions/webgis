<script setup lang="ts">
import { computed } from "vue";
import { MENU_TEXT_OPTIONS, menuIconPath } from "~/utils/menuThemeOptions";

const props = defineProps<{
  previewType?: "icon" | "arrow";
  previewIcon?: string;
}>();

const model = defineModel<string>({ required: true });

const previewType = computed(() => props.previewType ?? "icon");

const options = computed(() => {
  if (MENU_TEXT_OPTIONS.some((item) => item.value === model.value)) {
    return MENU_TEXT_OPTIONS;
  }

  return [
    {
      value: model.value,
      label: "Custom",
      swatch: "bg-slate-400",
      ring: "ring-slate-300",
    },
    ...MENU_TEXT_OPTIONS,
  ];
});
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-center rounded-xl border border-[#EEE6DE] bg-[#FBFAF8] p-4">
      <div
        v-if="previewType === 'icon'"
        class="flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-sm"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-7 w-7"
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
      </div>
      <span v-else class="text-2xl font-bold" :class="model">→</span>
    </div>

    <div class="grid grid-cols-5 gap-2 sm:grid-cols-7">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="flex flex-col items-center gap-1 rounded-xl border p-2 transition-all duration-200"
        :class="
          model === option.value
            ? `border-[#4D392A] bg-[#FFF8F2] ring-2 ${option.ring}`
            : 'border-[#EEE6DE] bg-white hover:border-[#D8CFC6] hover:shadow-sm'
        "
        :title="option.label"
        @click="model = option.value"
      >
        <span
          class="h-7 w-7 rounded-full shadow-sm"
          :class="option.swatch"
        />
        <span class="text-[10px] font-medium text-[#6F645B]">{{ option.label }}</span>
      </button>
    </div>

    <p class="mt-2 text-xs text-[#8A817A]">
      Terpilih: <span class="font-semibold text-[#4D392A]">{{ model }}</span>
    </p>
  </div>
</template>

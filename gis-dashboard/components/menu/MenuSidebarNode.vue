<script setup lang="ts">
import { ref } from "vue";
import { dashboardStore, type ModuleItem } from "~/stores/dashboardStore";

defineOptions({
  name: "MenuSidebarNode",
});

const props = withDefaults(
  defineProps<{
    items: ModuleItem[];
    depth?: number;
  }>(),
  {
    depth: 0,
  },
);

const emit = defineEmits<{
  navigate: [];
}>();

const dashboardService = dashboardStore();
const expanded = ref<Record<string, boolean>>({});

function itemKey(item: ModuleItem, index: number) {
  return item.id || `${item.title}-${index}`;
}

function toggle(key: string) {
  expanded.value[key] = !expanded.value[key];
}

async function openItem(item: ModuleItem) {
  if (!item.to) return;
  await navigateTo(item.to);
  emit("navigate");
}
</script>

<template>
  <div class="space-y-2">
    <div v-for="(item, index) in items" :key="itemKey(item, index)">
      <div class="flex items-stretch gap-1" :style="{ marginLeft: `${props.depth * 12}px` }">
        <button
          type="button"
          class="flex min-w-0 flex-1 items-center gap-3 rounded-xl border border-menu px-3 py-2.5 text-left transition hover-bg-cream"
          @click="item.children?.length ? toggle(itemKey(item, index)) : openItem(item)"
        >
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
            :class="item.bgClass"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              :class="item.iconClass"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.7"
                :d="dashboardService.iconPath(item.icon)"
              />
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate text-14 font-bold text-brand">
              {{ item.title }}
            </p>
            <p class="line-clamp-1 text-12 text-muted-light">
              {{ item.description }}
            </p>
          </div>
          <span v-if="item.children?.length" class="text-12 font-bold text-label">
            {{ expanded[itemKey(item, index)] ? "▾" : "▸" }}
          </span>
        </button>

        <button
          v-if="item.children?.length && item.to"
          type="button"
          class="rounded-xl border border-menu px-3 text-12 font-semibold text-brand hover-bg-cream"
          @click="openItem(item)"
        >
          Buka
        </button>
      </div>

      <MenuSidebarNode
        v-if="item.children?.length && expanded[itemKey(item, index)]"
        class="mt-2"
        :items="item.children"
        :depth="props.depth + 1"
        @navigate="emit('navigate')"
      />
    </div>
  </div>
</template>

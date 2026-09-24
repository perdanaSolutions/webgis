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

function isExpanded(item: ModuleItem, index: number) {
  return Boolean(expanded.value[itemKey(item, index)]);
}

function toggle(item: ModuleItem, index: number) {
  const key = itemKey(item, index);
  expanded.value[key] = !expanded.value[key];
}

async function openItem(item: ModuleItem) {
  if (!item.to) return;
  await navigateTo(item.to);
  emit("navigate");
}

function onPrimaryClick(item: ModuleItem, index: number) {
  if (item.children?.length) {
    toggle(item, index);
    return;
  }
  openItem(item);
}
</script>

<template>
  <div class="menu-sidebar-tree space-y-1" :class="props.depth > 0 ? 'menu-sidebar-tree--nested' : ''">
    <div
      v-for="(item, index) in items"
      :key="itemKey(item, index)"
      class="menu-sidebar-node"
      :class="isExpanded(item, index) ? 'menu-sidebar-node--open' : ''"
    >
      <div class="flex items-stretch gap-1">
        <button
          type="button"
          class="menu-sidebar-btn group flex min-w-0 flex-1 items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition-colors duration-200 hover-bg-cream"
          :class="isExpanded(item, index) ? 'bg-cream' : ''"
          :aria-expanded="item.children?.length ? isExpanded(item, index) : undefined"
          @click="onPrimaryClick(item, index)"
        >
          <div
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-transform duration-200 group-hover:scale-[1.04]"
            :class="item.bgClass"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-4 w-4"
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
            <p class="truncate text-13 font-bold text-brand">
              {{ item.title }}
            </p>
            <p class="line-clamp-1 text-11 text-muted-light">
              {{ item.description }}
            </p>
          </div>

          <span
            v-if="item.children?.length"
            class="menu-sidebar-chevron flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-label transition-colors duration-200"
            :class="isExpanded(item, index) ? 'bg-surface text-brand' : 'bg-transparent'"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2.2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </span>
          <span
            v-else-if="item.to"
            class="text-14 font-bold text-chevron opacity-0 transition-opacity duration-200 group-hover:opacity-100"
          >
            →
          </span>
        </button>

        <button
          v-if="item.children?.length && item.to"
          type="button"
          class="rounded-xl px-2.5 text-11 font-semibold text-brand transition-colors duration-200 hover-bg-cream"
          title="Buka halaman"
          @click="openItem(item)"
        >
          Buka
        </button>
      </div>

      <Transition name="menu-sidebar-collapse">
        <div
          v-if="item.children?.length && isExpanded(item, index)"
          class="menu-sidebar-children mt-1 ml-4 border-l border-menu pl-2"
        >
          <MenuSidebarNode
            :items="item.children"
            :depth="props.depth + 1"
            @navigate="emit('navigate')"
          />
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.menu-sidebar-chevron svg {
  transition: transform 0.2s ease;
}

.menu-sidebar-node--open .menu-sidebar-chevron svg {
  transform: rotate(90deg);
}

.menu-sidebar-collapse-enter-active,
.menu-sidebar-collapse-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.menu-sidebar-collapse-enter-from,
.menu-sidebar-collapse-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>

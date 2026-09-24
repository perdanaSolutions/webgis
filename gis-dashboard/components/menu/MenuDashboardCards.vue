<script setup lang="ts">
import { ref } from "vue";
import { dashboardStore, type ModuleItem } from "~/stores/dashboardStore";

defineOptions({
  name: "MenuDashboardCards",
});

const props = withDefaults(
  defineProps<{
    items: ModuleItem[];
    depth?: number;
  }>(),
  {
    depth: 1,
  },
);

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
}

function childCount(item: ModuleItem) {
  return item.children?.length ?? 0;
}
</script>

<template>
  <div
    class="menu-dashboard-tree"
    :class="
      props.depth === 1
        ? 'grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3'
        : 'flex flex-col gap-2'
    "
  >
    <article
      v-for="(item, index) in items"
      :key="itemKey(item, index)"
      class="menu-dashboard-item group"
      :class="[
        item.children?.length && isExpanded(item, index)
          ? 'menu-dashboard-item--open'
          : '',
        props.depth === 1 && item.children?.length && isExpanded(item, index)
          ? 'md:col-span-2 xl:col-span-3'
          : '',
      ]"
    >
      <!-- Parent with children -->
      <div v-if="item.children?.length" class="overflow-hidden rounded-2xl border border-default bg-surface transition-all duration-200">
        <div class="flex items-stretch">
          <button
            type="button"
            class="flex min-w-0 flex-1 items-center gap-3 px-4 py-3.5 text-left transition-colors duration-200 hover-bg-cream sm:gap-4 sm:px-5 sm:py-4"
            :aria-expanded="isExpanded(item, index)"
            @click="toggle(item, index)"
          >
            <div
              class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-[1.03] sm:h-14 sm:w-14 sm:rounded-2xl"
              :class="item.bgClass"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="h-6 w-6 sm:h-7 sm:w-7"
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
              <div class="flex flex-wrap items-center gap-2">
                <p class="truncate text-15 font-bold leading-tight text-content sm:text-16">
                  {{ item.title }}
                </p>
                <span
                  class="rounded-full bg-surface-warm px-2 py-0.5 text-11 font-semibold text-label"
                >
                  {{ childCount(item) }} submenu
                </span>
              </div>
              <p class="mt-1 line-clamp-1 text-13 leading-snug text-muted sm:line-clamp-2 sm:text-14">
                {{ item.description }}
              </p>
            </div>

            <span
              class="menu-chevron flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-warm text-label transition-all duration-200"
              :class="isExpanded(item, index) ? 'menu-chevron--open bg-cream text-brand' : ''"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="h-4 w-4"
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
          </button>

          <button
            v-if="item.to"
            type="button"
            class="shrink-0 border-l border-default px-4 text-13 font-semibold text-brand transition-colors duration-200 hover-bg-cream sm:px-5"
            @click="openItem(item)"
          >
            Buka
          </button>
        </div>

        <Transition name="menu-collapse">
          <div
            v-if="isExpanded(item, index)"
            class="border-t border-default bg-page px-3 py-3 sm:px-4 sm:py-4"
          >
            <div class="mb-2 flex items-center gap-2 px-1">
              <span class="h-px flex-1 bg-progress-track" />
              <span class="text-11 font-semibold uppercase tracking-wide text-label">
                Isi {{ item.title }}
              </span>
              <span class="h-px flex-1 bg-progress-track" />
            </div>
            <MenuDashboardCards :items="item.children" :depth="props.depth + 1" />
          </div>
        </Transition>
      </div>

      <!-- Leaf with route -->
      <NuxtLink
        v-else-if="item.to"
        :to="item.to"
        class="flex items-center gap-3 rounded-2xl border border-default bg-surface px-4 py-3.5 transition-all duration-200 hover-border-tan hover:shadow-sm sm:gap-4 sm:px-5 sm:py-4"
      >
        <div
          class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl sm:h-14 sm:w-14 sm:rounded-2xl"
          :class="item.bgClass"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-6 w-6 sm:h-7 sm:w-7"
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
          <p class="truncate text-15 font-bold leading-tight text-content sm:text-16">
            {{ item.title }}
          </p>
          <p class="mt-1 line-clamp-1 text-13 leading-snug text-muted sm:line-clamp-2 sm:text-14">
            {{ item.description }}
          </p>
        </div>

        <span
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-warm text-16 font-bold transition-colors duration-200 group-hover:bg-cream"
          :class="item.arrowClass"
        >
          →
        </span>
      </NuxtLink>

      <!-- Leaf without route -->
      <div
        v-else
        class="flex items-center gap-3 rounded-2xl border border-dashed border-tan bg-surface-warm px-4 py-3.5 sm:gap-4 sm:px-5 sm:py-4"
      >
        <div
          class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl sm:h-14 sm:w-14 sm:rounded-2xl"
          :class="item.bgClass"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-6 w-6 sm:h-7 sm:w-7"
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
          <p class="truncate text-15 font-bold leading-tight text-content sm:text-16">
            {{ item.title }}
          </p>
          <p class="mt-1 line-clamp-1 text-13 leading-snug text-muted sm:text-14">
            {{ item.description || "Belum ada rute tujuan" }}
          </p>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.menu-dashboard-item--open > div {
  border-color: var(--color-border-tan);
  box-shadow: 0 8px 24px rgb(77 57 42 / 6%);
}

.menu-chevron svg {
  transition: transform 0.2s ease;
}

.menu-chevron--open svg {
  transform: rotate(90deg);
}

.menu-collapse-enter-active,
.menu-collapse-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.menu-collapse-enter-from,
.menu-collapse-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

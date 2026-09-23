<script setup lang="ts">
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
</script>

<template>
  <div
    :class="
      props.depth === 1
        ? 'grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4'
        : 'mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2'
    "
  >
    <template v-for="item in items" :key="item.id || item.title">
      <article
        v-if="item.children?.length"
        class="rounded-2xl border border-default bg-surface p-4"
        :class="props.depth === 1 ? 'xl:col-span-2' : 'sm:col-span-2'"
      >
        <div class="flex items-center gap-4">
          <div
            class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl"
            :class="item.bgClass"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-8 w-8"
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
            <p class="truncate text-16 font-bold leading-tight">
              {{ item.title }}
            </p>
            <p class="mt-1 line-clamp-2 text-14 leading-snug text-muted">
              {{ item.description }}
            </p>
          </div>

          <NuxtLink
            v-if="item.to"
            :to="item.to"
            class="text-16 font-bold"
            :class="item.arrowClass"
          >
            →
          </NuxtLink>
        </div>

        <MenuDashboardCards :items="item.children" :depth="props.depth + 1" />
      </article>

      <NuxtLink
        v-else-if="item.to"
        :to="item.to"
        class="flex items-center gap-4 rounded-2xl border border-default bg-surface p-4 transition hover:shadow-sm"
      >
        <div
          class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl"
          :class="item.bgClass"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-8 w-8"
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
          <p class="truncate text-16 font-bold leading-tight">
            {{ item.title }}
          </p>
          <p class="mt-1 line-clamp-2 text-14 leading-snug text-muted">
            {{ item.description }}
          </p>
        </div>

        <span class="text-16 font-bold" :class="item.arrowClass">→</span>
      </NuxtLink>

      <div
        v-else
        class="flex items-center gap-4 rounded-2xl border border-default bg-surface p-4"
      >
        <div
          class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl"
          :class="item.bgClass"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-8 w-8"
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
          <p class="truncate text-16 font-bold leading-tight">
            {{ item.title }}
          </p>
          <p class="mt-1 line-clamp-2 text-14 leading-snug text-muted">
            {{ item.description }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

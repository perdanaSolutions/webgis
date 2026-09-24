<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '~/stores/authStore'
import Header from '~/components/Header.vue'
import { dashboardStore } from '~/stores/dashboardStore'

const authStore = useAuthStore()
const dashboardService = dashboardStore()

const informasiUser = computed(() => authStore.user)

defineOptions({
  name: 'DashboardPage',
})

onMounted(async () => {
  if (!authStore.token) {
    await navigateTo('/login')
  }
  dashboardService.initDataMenu()
})
</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header :brand-title="dashboardService.dashboardConfig.brandTitle"
      :brand-subtitle="dashboardService.dashboardConfig.brandSubtitle" />
    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <section class="grid grid-cols-1 items-center gap-4 lg:grid-cols-[1fr_2fr]">
        <div>
          <p class="text-14 text-muted">
            {{ dashboardService.dashboardConfig.greetingTop }}
          </p>
          <h2 class="text-20 font-bold leading-tight">
            {{ authStore.user?.nama_lengkap }}
          </h2>
          <p class="text-14 text-muted">
            {{ dashboardService.dashboardConfig.greetingDesc }}
          </p>
        </div>

        <div class="flex items-center gap-3 rounded-full border border-default bg-surface p-3 shadow-sm">
          <input type="text" :placeholder="dashboardService.dashboardConfig.searchPlaceholder"
            class="h-11 flex-1 rounded-full px-5 text-14 outline-none placeholder-text-placeholder">
          <button class="rounded-full bg-brand px-8 py-3 text-14 font-semibold text-on-brand">
            {{ dashboardService.dashboardConfig.searchButtonLabel }}
          </button>
        </div>
      </section>

      <section class="mt-6 grid grid-cols-1 gap-6">
        <!-- CONTENT QUICK ACCESS AND ANNOUNCEMENT -->
        <!-- xl:grid-cols-[1.1fr_1.4fr] -->
        <!-- <div class="rounded-2xl border border-default bg-surface p-5">
          <h3 class="text-16 font-bold">
            {{ dashboardService.dashboardConfig.quickAccessTitle }}
          </h3>
          <p class="text-14 text-muted">
            {{ dashboardService.dashboardConfig.quickAccessDesc }}
          </p>

          <div class="mt-5 grid grid-cols-3 gap-4 sm:grid-cols-5">
            <NuxtLink v-for="item in dashboardService.quickAccessItems" :key="`quick-${item.title}`" :to="item.to"
              class="flex flex-col items-center gap-2">
              <div class="flex h-16 w-16 items-center justify-center rounded-2xl" :class="item.bgClass">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor" :class="item.iconClass">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                    :d="dashboardService.iconPath(item.icon)" />
                </svg>
              </div>
              <span class="text-center text-14 font-semibold">{{ item.title }}</span>
            </NuxtLink>
          </div>
        </div> -->

        <div class="rounded-2xl bg-brand p-5 text-on-brand">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-16 font-bold">
              {{ dashboardService.dashboardConfig.announcementTitle }}
            </h3>
            <button class="text-14 font-semibold">
              {{ dashboardService.dashboardConfig.announcementSeeAll }}
            </button>
          </div>

          <div class="space-y-3 rounded-xl bg-surface p-4 text-content">
            <div v-for="(item, index) in dashboardService.announcements" :key="`announcement-${item.title}`"
              class="flex items-center gap-4 py-2" :class="{
                'border-b border-announce':
                  index < dashboardService.announcements.length - 1,
              }">
              <div class="w-14 rounded-xl bg-sidebar-hover py-2 text-center">
                <p class="text-16 font-bold leading-none">
                  {{ item.date }}
                </p>
                <p class="text-14 text-muted">
                  {{ item.month }}
                </p>
              </div>
              <div class="flex-1">
                <p class="text-16 font-bold">
                  {{ item.title }}
                </p>
                <p class="text-14 text-desc">
                  {{ item.description }}
                </p>
              </div>
              <span class="text-16 text-chevron">›</span>
            </div>
          </div>
        </div>
      </section>

      <section class="mt-7">
        <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 class="text-20 font-bold">
              {{ dashboardService.dashboardConfig.moduleTitle }}
            </h3>
            <p class="mt-1 text-14 text-muted">
              Buka modul langsung, atau perluas kelompok menu untuk melihat submenu.
            </p>
          </div>

          <NuxtLink v-if="informasiUser?.role === 'superadmin'" to="/menus"
            class="rounded-full border border-tan bg-cream px-4 py-2 text-size-sm font-semibold text-brand transition hover-bg-cream-active">
            Management Menu
          </NuxtLink>
        </div>

        <div v-if="dashboardService.loading" class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div v-for="i in 8" :key="`skeleton-${i}`"
            class="flex items-center gap-4 rounded-2xl border border-default bg-surface p-4 animate-pulse">
            <div class="h-14 w-14 shrink-0 rounded-2xl bg-slate-muted" />

            <div class="min-w-0 flex-1 space-y-2">
              <div class="h-4 w-3/4 rounded bg-slate-muted" />
              <div class="h-3 w-full rounded bg-slate-muted" />
            </div>

            <div class="h-4 w-4 rounded bg-slate-muted" />
          </div>
        </div>

        <MenuDashboardCards v-else :items="dashboardService.moduleItems" />
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import palmImage from '~/assets/image/Palm.jpeg'
import { useAuthStore } from '~/stores/authStore'
import Header from '~/components/Header.vue'
import { dashboardStore, type ModuleItem } from '~/stores/dashboardStore'

const authStore = useAuthStore()
const dashboardService = dashboardStore()

const menuKeyword = ref('')

function menuMatches(item: ModuleItem, keyword: string) {
  return [item.title, item.description, item.to]
    .join(' ')
    .toLowerCase()
    .includes(keyword)
}

function filterMenus(items: ModuleItem[], keyword: string): ModuleItem[] {
  return items.flatMap((item) => {
    const children = filterMenus(item.children ?? [], keyword)
    if (!menuMatches(item, keyword) && !children.length) return []
    return [{
      ...item,
      children: menuMatches(item, keyword) ? item.children : children,
    }]
  })
}

const appliedKeyword = computed(() => menuKeyword.value.trim().toLowerCase())

const visibleMenus = computed(() => {
  if (!appliedKeyword.value) return dashboardService.moduleItems
  return filterMenus(dashboardService.moduleItems, appliedKeyword.value)
})

function searchMenus() {
  document.getElementById('menu-modul')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

defineOptions({
  name: 'DashboardPage',
})

onMounted(async () => {
  const session = await authStore.ensureSession()
  if (!session) {
    window.location.replace('/login')
    return
  }
  dashboardService.initDataMenu()
})
</script>

<template>
  <main class="flex min-h-screen flex-col bg-page text-14 text-content">
    <Header :brand-title="dashboardService.dashboardConfig.brandTitle"
      :brand-subtitle="dashboardService.dashboardConfig.brandSubtitle" />
    <div class="mx-auto flex w-full max-w-[1400px] flex-1 flex-col px-6 py-6 lg:px-10">
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

        <form class="flex items-center gap-3 rounded-full border border-default bg-surface p-3 shadow-sm"
          @submit.prevent="searchMenus">
          <input v-model="menuKeyword" type="search" :placeholder="dashboardService.dashboardConfig.searchPlaceholder"
            class="h-11 flex-1 rounded-full px-5 text-14 outline-none placeholder-text-placeholder"
            aria-label="Cari menu">
        </form>

      </section>

      <section id="menu-modul" class="mt-7">
        <div class="mb-4">
          <h3 class="text-20 font-bold">
            {{ dashboardService.dashboardConfig.moduleTitle }}
          </h3>
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

        <p v-else-if="appliedKeyword && !visibleMenus.length"
          class="rounded-2xl border border-default bg-surface px-5 py-8 text-center text-14 text-muted">
          Tidak ada menu yang cocok dengan "{{ menuKeyword.trim() }}".
        </p>
        <MenuDashboardCards v-else :items="visibleMenus" :expand-all="Boolean(appliedKeyword)" />
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

        <!-- PENGUMUMAN -->
        <!-- <div class="rounded-2xl bg-brand p-5 text-on-brand">
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
        </div> -->
      </section>

      <section class="palm-banner" aria-label="Every Palm Matters">
        <img :src="palmImage" alt="" class="palm-banner__photo">
        <div class="palm-banner__veil" aria-hidden="true" />
        <div class="palm-banner__stage">
          <div class="palm-banner__card">
            <p class="palm-banner__kicker">When</p>
            <h2 class="palm-banner__title">EVERY PALM MATTERS</h2>
            <p class="palm-banner__lead">
              <span>Optimalisasi produktivitas</span>
              <span>dan sumber daya dengan pendekatan</span>
              <span>teknologi dan ilmu pengetahuan terkini</span>
              <span>yang terhubung dengan tata kelola dan teknis</span>
              <span>budidaya perkebunan sawit terbaik dan berkelanjutan.</span>
            </p>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.palm-banner {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 440px;
  margin-top: 1.75rem;
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 55%);
  border-radius: 28px;
  box-shadow: 0 18px 40px rgb(31 42 24 / 10%);
}

.palm-banner__photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 42%;
}

.palm-banner__veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgb(18 36 10 / 18%) 0%, rgb(18 36 10 / 4%) 34%, rgb(12 24 8 / 22%) 100%);
}

.palm-banner__stage {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  align-items: flex-end;
  justify-content: center;
  padding: 1.5rem 1.25rem 1.35rem;
}

.palm-banner__card {
  width: min(860px, 100%);
  border-radius: 24px;
  background: rgb(255 255 255 / 94%);
  padding: 1.35rem 1.6rem 1.45rem;
  text-align: left;
  box-shadow:
    0 22px 50px rgb(16 32 8 / 22%),
    0 0 0 1px rgb(255 255 255 / 70%);
  backdrop-filter: blur(10px);
}

.palm-banner__kicker {
  margin: 0;
  color: #3a9a32;
  font-size: clamp(1.35rem, 2vw, 1.85rem);
  font-style: italic;
  font-weight: 700;
  line-height: 1;
}

.palm-banner__title {
  margin: 0.15rem 0 0;
  color: #111111;
  font-size: clamp(1.85rem, 4.2vw, 3.55rem);
  font-weight: 800;
  letter-spacing: -0.035em;
  line-height: 1.02;
  text-transform: uppercase;
  text-wrap: balance;
}

.palm-banner__lead {
  margin: 0.95rem auto 0;
  max-width: 40rem;
  color: #161616;
  font-size: clamp(0.98rem, 1.35vw, 1.15rem);
  font-weight: 600;
  line-height: 1.4;
  text-align: center;
}

.palm-banner__lead span {
  display: block;
}

@media (max-width: 640px) {
  .palm-banner {
    min-height: 520px;
    border-radius: 22px;
  }

  .palm-banner__card {
    padding: 1.15rem 1rem 1.2rem;
    border-radius: 18px;
  }

  .palm-banner__lead span {
    display: inline;
  }

  .palm-banner__lead span:not(:last-child)::after {
    content: " ";
  }
}
</style>

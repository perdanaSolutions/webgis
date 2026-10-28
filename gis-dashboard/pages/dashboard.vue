<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import logoImage from '~/assets/image/logo-1.svg'
import handsImage from '~/assets/image/hand-deskripsi.svg'
import modulesImage from '~/assets/image/base_modul_overlay.svg'
import estateImage from '~/assets/image/kebun_dashboard.svg'
import { useAuthStore } from '~/stores/authStore'
import { useAppFullscreenStore } from '~/stores/appFullscreenStore'
import Header from '~/components/Header.vue'
import BannerCharts from '~/components/dashboard/BannerCharts.vue'

const authStore = useAuthStore()
const appFullscreen = useAppFullscreenStore()
const { isFullscreen } = storeToRefs(appFullscreen)

defineOptions({
  name: 'DashboardPage',
})

onMounted(async () => {
  const session = await authStore.ensureSession()
  if (!session) {
    window.location.replace('/login')
  }
})
</script>

<template>
  <main class="dash-page">
    <Header />
    <div class="dash-stage">
      <img :src="estateImage" alt="" class="dash-home__estate">
      <section class="dash-home" aria-label="Ringkasan perkebunan">
        <div class="dash-home__panel">
          <div class="dash-home__topline">
            <img :src="logoImage" alt="Teladan Prima Agro" class="dash-home__logo">
          </div>
          <BannerCharts />
        </div>
        <div class="dash-home__hero">
          <div class="dash-home__story">
            <!-- <img :src="sloganImage" alt="When Every Palm Matters" class="dash-home__slogan">
            <p class="dash-home__lead">
              Optimalisasi produktivitas dan sumber daya
              dengan pendekatan teknologi dan ilmu pengetahuan terkini
              yang terhubung dengan tata kelola dan teknis budidaya
              perkebunan kelapa sawit terbaik dan berkelanjutan.
            </p> -->
          </div>
          <img :src="handsImage" alt="" class="dash-home__hands">
          <img :src="modulesImage" alt="Modul teknologi perkebunan Teladan Prima Agro" class="dash-home__modules">
        </div>
      </section>

      <button
        type="button"
        class="dash-fs-btn"
        :aria-label="isFullscreen ? 'Keluar layar penuh' : 'Layar penuh'"
        :title="isFullscreen ? 'Keluar layar penuh' : 'Layar penuh'"
        :aria-pressed="isFullscreen"
        @click="appFullscreen.toggleFullscreen()"
      >
        <svg
          v-if="!isFullscreen"
          viewBox="0 0 24 24"
          class="dash-fs-btn__icon"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 9V4h5M15 4h5v5M4 15v5h5M20 15v5h-5" />
        </svg>
        <svg
          v-else
          viewBox="0 0 24 24"
          class="dash-fs-btn__icon"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
        </svg>
      </button>
    </div>
  </main>
</template>

<style scoped>
.dash-page {
  position: relative;
  z-index: 0;
  display: flex;
  min-height: 100dvh;
  flex-direction: column;
  background: transparent;
  color: #1f2a18;
}

.dash-stage {
  position: relative;
  z-index: 0;
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  overflow: hidden;
  background: transparent;
}

.dash-fs-btn {
  position: fixed;
  z-index: 50;
  right: max(0.75rem, env(safe-area-inset-right, 0px));
  bottom: max(0.75rem, env(safe-area-inset-bottom, 0px));
  display: flex;
  height: 2.75rem;
  width: 2.75rem;
  align-items: center;
  justify-content: center;
  border: 1px solid rgb(255 255 255 / 55%);
  border-radius: 1rem;
  background: rgb(255 253 249 / 77.4%);
  color: #1f2a18;
  box-shadow: 0 10px 30px rgb(31 42 24 / 12%);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  cursor: pointer;
}

.dash-fs-btn:hover {
  background: #eef3e7;
}

.dash-fs-btn__icon {
  height: 1.25rem;
  width: 1.25rem;
}

@media (min-width: 640px) {
  .dash-fs-btn {
    height: 3rem;
    width: 3rem;
  }
}

.dash-home {
  position: relative;
  z-index: 1;
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  background: transparent;
}

.dash-home__panel {
  padding: 0.35rem 0.85rem 0.25rem;
}

.dash-home__topline {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.2rem;
}

.dash-home__logo {
  display: block;
  height: 34px;
  width: auto;
  object-fit: contain;
}

.dash-home__hero {
  position: relative;
  min-height: 340px;
  flex: 1 1 auto;
  overflow: hidden;
}

.dash-home__estate {
  position: absolute;
  z-index: 0;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 72%;
  pointer-events: none;
}

.dash-home__story {
  position: absolute;
  z-index: 3;
  top: 6%;
  left: 4%;
  display: flex;
  width: min(24rem, 34%);
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.dash-home__story::before {
  content: "";
  position: absolute;
  z-index: -1;
  inset: -18% -10% -8%;
  background: radial-gradient(ellipse at center, rgb(10 24 8 / 46%), transparent 72%);
}

.dash-home__slogan {
  display: block;
  width: 100%;
  height: auto;
  filter:
    drop-shadow(0 1px 1px rgb(8 20 6 / 95%))
    drop-shadow(0 0 8px rgb(8 20 6 / 75%));
}

.dash-home__lead {
  margin: 0.35rem 0 0;
  color: #fff8e8;
  font-size: clamp(0.68rem, 0.95vw, 0.92rem);
  font-weight: 650;
  line-height: 1.4;
  text-shadow:
    0 1px 2px rgb(8 18 6 / 95%),
    0 0 8px rgb(8 18 6 / 80%);
}

.dash-home__hands,
.dash-home__modules {
  position: absolute;
  z-index: 2;
  width: auto;
  object-fit: contain;
  pointer-events: none;
  user-select: none;
}

.dash-home__hands {
  bottom: 0;
  left: 18%;
  height: 62%;
  max-width: 42%;
  object-position: center bottom;
}

.dash-home__modules {
  right: 2%;
  bottom: 4%;
  height: 78%;
  max-width: 32%;
  object-position: right bottom;
}

@media (min-width: 1024px) {
  .dash-page {
    height: 100dvh;
    overflow: hidden;
  }

  .dash-stage {
    min-height: 0;
  }

  .dash-home__panel {
    padding: 0.28rem 1rem 0.15rem;
  }

  .dash-home__logo {
    height: 50px;
  }

  .dash-home__hero {
    min-height: 0;
  }
}

@media (min-width: 1024px) and (max-height: 760px) {
  .dash-home__panel {
    padding-top: 0.15rem;
  }

  .dash-home__logo {
    height: 24px;
  }

  .dash-home__panel :deep(.kpi__svg) {
    height: 4.7rem;
  }

  .dash-home__panel :deep(.kpi__chart) {
    min-height: 4.7rem;
  }

  .dash-home__panel :deep(.kpi__foot p) {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
}

@media (max-width: 1023px) {
  .dash-page {
    height: auto;
    overflow: visible;
  }

  .dash-home__panel {
    padding: 0.7rem 0.7rem 0.2rem;
  }

  .dash-home__hero {
    height: 72vw;
    min-height: 300px;
    flex: none;
  }

  .dash-home__story {
    top: 5%;
    left: 3%;
    width: min(15rem, 62%);
  }

  .dash-home__lead {
    font-size: 0.68rem;
  }

  .dash-home__hands {
    left: 0;
    height: 50%;
    max-width: 72%;
  }

  .dash-home__modules {
    right: 0;
    bottom: 8%;
    height: 58%;
    max-width: 58%;
  }
}

@media (max-width: 767px) {
  .dash-home__topline {
    display: none;
  }
}

@media (max-width: 640px) {
  .dash-home__hero {
    height: auto;
    min-height: 420px;
    aspect-ratio: 4 / 5;
  }

  .dash-home__story {
    width: min(13.5rem, 70%);
  }

  .dash-home__hands {
    height: 42%;
    max-width: 78%;
  }

  .dash-home__modules {
    bottom: 10%;
    height: 48%;
    max-width: 62%;
  }
}
</style>

<script setup lang="ts">
import { onMounted, watch } from "vue";
import {
  clearMenuAccessDenied,
  isShellPath,
  MENU_ACCESS_DENIED_KEY,
  MENU_ROUTE_CHECKING_KEY,
  MENU_ROUTE_UNLOCKED_KEY,
  menuAccessDeniedPending,
} from "~/utils/menuRouteAccess";
import { useAppFullscreenStore } from "~/stores/appFullscreenStore";
import { storeToRefs } from "pinia";

const router = useRouter();
const menuRouteUnlocked = useState(MENU_ROUTE_UNLOCKED_KEY, () => false);
const menuRouteChecking = useState(MENU_ROUTE_CHECKING_KEY, () => false);
const menuAccessDenied = useState(MENU_ACCESS_DENIED_KEY, () => false);
const accessDeniedOpen = ref(false);
const appFullscreen = useAppFullscreenStore();
const { pseudoFullscreen } = storeToRefs(appFullscreen);
const fsHostRef = ref<HTMLElement | null>(null);

// Pakai currentRoute, bukan useRoute(): saat NuxtPage belum dipasang, useRoute()
// bisa tetap di URL lama sementara router sudah pindah ke dashboard.
const currentPath = computed(() => router.currentRoute.value.path);
const isShell = computed(() => isShellPath(currentPath.value));
const showPage = computed(() => isShell.value || (menuRouteUnlocked.value && !menuRouteChecking.value));
const showGate = computed(() => !showPage.value);

function syncDeniedNotice() {
  if (menuAccessDeniedPending()) accessDeniedOpen.value = true;
}

function dismissDenied() {
  accessDeniedOpen.value = false;
  clearMenuAccessDenied();
}

onMounted(() => {
  syncDeniedNotice();
  appFullscreen.registerHost(fsHostRef.value);
});
watch(fsHostRef, (el) => {
  appFullscreen.registerHost(el);
});
watch(menuAccessDenied, syncDeniedNotice);
watch(isShell, (shell) => {
  if (shell) menuRouteChecking.value = false;
});
</script>

<template>
  <div
    ref="fsHostRef"
    class="app-fs-host"
    :class="{ 'app-fs-host--pseudo-fs': pseudoFullscreen }"
  >
    <NuxtPage v-if="showPage" />
    <div v-if="showGate" class="menu-route-gate" role="status" aria-live="polite">
      <span class="menu-route-gate__spinner" aria-hidden="true" />
      <p>Memeriksa akses menu...</p>
    </div>
    <ClientOnly>
      <AppAlert />
      <AppModalTeleport>
        <div
          v-if="accessDeniedOpen"
          class="app-modal-backdrop app-modal-backdrop--top bg-[#1f2a18]/45"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="menu-access-denied-title"
          @click.self="dismissDenied"
        >
          <div class="app-modal-panel app-modal-size-sm w-full rounded-2xl bg-white shadow-2xl">
            <h2 id="menu-access-denied-title" class="text-base font-bold text-[#1f2a18]">Akses ditolak</h2>
            <p class="mt-2 text-13 leading-relaxed text-[#3d4a34]">Anda tidak memiliki akses</p>
            <div class="mt-4 flex justify-end">
              <button
                type="button"
                class="rounded-xl bg-[#638840] px-4 py-2 text-13 font-semibold text-white"
                @click="dismissDenied"
              >
                Mengerti
              </button>
            </div>
          </div>
        </div>
      </AppModalTeleport>
    </ClientOnly>
  </div>
</template>

<style scoped>
.app-fs-host {
  min-height: 100dvh;
}

.app-fs-host:fullscreen,
.app-fs-host:-webkit-full-screen {
  width: 100%;
  height: 100%;
  max-height: none;
  overflow: auto;
  background: #f4f7f1;
}

.app-fs-host--pseudo-fs {
  position: fixed;
  inset: 0;
  z-index: 40;
  height: 100dvh;
  max-height: none;
  overflow: auto;
  background: #f4f7f1;
}

.menu-route-gate {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: #f4f7f1;
  color: #4b5563;
  font-size: 14px;
}

.menu-route-gate p {
  margin: 0;
}

.menu-route-gate__spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgb(99 136 64 / 20%);
  border-top-color: #638840;
  border-radius: 999px;
  animation: menu-route-spin 0.8s linear infinite;
}

@keyframes menu-route-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

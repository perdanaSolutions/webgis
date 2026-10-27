<script setup lang="ts">
import bannerImage from '~/assets/image/banner-login.png'
import logoImage from '~/assets/image/logo-1.svg'
import { MAINTENANCE_DEFAULT_MESSAGE, MAINTENANCE_STATE_KEY, type MaintenanceStatus } from '~/utils/maintenance'
import {
  checkBackendHealth,
  isServerErrorReason,
  sanitizeReturnPath,
  SERVER_RECOVERY_POLL_MS,
} from '~/utils/serverError'

defineOptions({ name: 'MaintenancePage' })
useHead({ title: 'Website Sedang Dalam Perbaikan' })

const SERVER_ERROR_MESSAGE = 'Terjadi gangguan pada server, kami sedang menanganinya.'

const route = useRoute()
const config = useRuntimeConfig()
const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null)

const isServerError = computed(() => isServerErrorReason(route.query.reason))
const returnPath = computed(() => sanitizeReturnPath(route.query.from))
const message = computed(() =>
  isServerError.value ? SERVER_ERROR_MESSAGE : state.value?.message || MAINTENANCE_DEFAULT_MESSAGE,
)
const checking = ref(false)
const stillDown = ref(false)

let timer: ReturnType<typeof setInterval> | null = null

async function checkRecovery() {
  if (checking.value) return
  checking.value = true
  try {
    const health = await checkBackendHealth(String(config.public.apiBaseUrlPython || ''))
    if (!health.ok) {
      stillDown.value = true
      return
    }
    stillDown.value = false
    if (health.maintenance) {
      // Server pulih tetapi mode maintenance aktif: tampilkan pesan maintenance dari DB.
      state.value = { maintenance: true, message: health.message || MAINTENANCE_DEFAULT_MESSAGE }
      await navigateTo('/maintenance', { replace: true })
      return
    }
    // Muat ulang penuh agar data halaman asal diambil ulang dari server yang sudah pulih.
    window.location.replace(returnPath.value)
  }
  finally {
    checking.value = false
  }
}

function startPolling() {
  stopPolling()
  if (isServerError.value) timer = setInterval(checkRecovery, SERVER_RECOVERY_POLL_MS)
}
function stopPolling() {
  if (timer) clearInterval(timer)
  timer = null
}

function retry() {
  if (isServerError.value) return checkRecovery()
  window.location.replace('/')
}

onMounted(startPolling)
watch(isServerError, startPolling)
onBeforeUnmount(stopPolling)
</script>

<template>
  <main class="login-page relative min-h-screen w-full overflow-hidden text-14">
    <img :src="bannerImage" alt="" class="pointer-events-none absolute inset-0 h-full w-full object-cover object-center">
    <div class="relative z-10 flex min-h-screen items-center justify-center px-4 py-6 sm:px-6 sm:py-8">
      <section class="w-full max-w-[480px] rounded-3xl border border-white-soft bg-surface px-5 py-8 text-center sm:px-8 sm:py-10">
        <img :src="logoImage" alt="Logo" class="mx-auto h-16 w-auto object-contain sm:h-[72px]">
        <div class="mx-auto mt-6 flex h-16 w-16 items-center justify-center rounded-full bg-[#638840]/10 text-[32px]" aria-hidden="true">
          🛠️
        </div>
        <h1 class="mt-4 text-20 font-bold leading-tight tracking-tight text-content-dark">
          Website Sedang Dalam Perbaikan
        </h1>
        <p class="mt-3 text-14 leading-relaxed text-[#3d4a34]">{{ message }}</p>
        <p class="mt-2 text-13 text-[#6b7563]">
          Halaman ini akan kembali otomatis setelah perbaikan selesai. Terima kasih atas kesabaran Anda.
        </p>
        <p v-if="isServerError && stillDown" class="mt-2 text-12 text-[#a15c2b]" role="status">
          Server masih belum merespons. Kami akan mencoba lagi otomatis.
        </p>
        <button
          type="button"
          class="mt-6 rounded-xl bg-[#638840] px-5 py-2.5 text-13 font-semibold text-white disabled:opacity-60"
          :disabled="checking"
          @click="retry"
        >
          {{ checking ? 'Memeriksa…' : 'Coba Lagi' }}
        </button>
      </section>
    </div>
  </main>
</template>

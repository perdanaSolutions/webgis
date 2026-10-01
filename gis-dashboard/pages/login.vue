<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import bannerImage from '~/assets/image/banner-login.png'
import logoImage from '~/assets/image/logo-1.png'
import { useAuthStore } from '~/stores/authStore'

defineOptions({
  name: 'LoginPage',
})

const authStore = useAuthStore()
const showPassword = ref(false)
const form = reactive({
  email: '',
  password: '',
})

function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}

onMounted(async () => {
  if (authStore.token) {
    const me = await authStore.validateToken()
    if (me) {
      await navigateTo('/dashboard')
    }
  }
})

async function onSubmit() {
  await authStore.login(form.email, form.password)
}
</script>

<template>
  <main class="login-page relative w-full overflow-hidden text-14">
    <img :src="bannerImage" alt=""
      class="pointer-events-none absolute inset-0 h-full w-full object-cover object-center">

    <div class="relative z-10 h-full overflow-y-auto">
      <div class="flex min-h-full items-center justify-center px-4 py-6 sm:px-6 sm:py-8">
        <section class="w-full max-w-[440px] rounded-3xl border border-white-soft bg-surface px-5 py-7 sm:px-8 sm:py-9">
          <div class="flex flex-col items-center text-center">
            <img :src="logoImage" alt="TLDN Productivity Technology Science"
              class="h-16 w-auto object-contain sm:h-[72px]">
            <h1 class="mt-4 text-20 font-bold leading-tight tracking-tight text-content-dark">
              Masuk ke akun Anda
            </h1>
            <p class="mt-2 max-w-[320px] text-13 leading-6 text-muted-ios sm:text-14">
              Gunakan email dan kata sandi terdaftar untuk mengakses dashboard.
            </p>
          </div>

          <form class="mt-7 space-y-5" @submit.prevent="onSubmit">
            <div>
              <label for="email" class="mb-2 block text-14 font-bold leading-none text-content-dark">
                Email
              </label>
              <input id="email" v-model="form.email" type="email" autocomplete="email" placeholder="Masukan email Anda"
                class="h-12 w-full rounded-2xl border border-input bg-surface px-4 text-14 text-content-dark outline-none placeholder-text-placeholder-light focus-border-brand-secondary focus:ring-2 focus-ring-brand-secondary-20 sm:h-14 sm:px-5">
            </div>

            <div>
              <label for="password" class="mb-2 block text-14 font-bold leading-none text-content-dark">
                Kata Sandi
              </label>
              <div class="relative">
                <input id="password" v-model="form.password" :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password" placeholder="Masukan kata sandi Anda"
                  class="h-12 w-full rounded-2xl border border-input bg-surface px-4 pr-12 text-14 text-content-dark outline-none placeholder-text-placeholder-light focus-border-brand-secondary focus:ring-2 focus-ring-brand-secondary-20 sm:h-14 sm:px-5 sm:pr-14">
                <button type="button" :aria-label="showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'"
                  class="absolute inset-y-0 right-3 my-auto flex h-8 w-8 items-center justify-center text-muted-ios hover-text-brand-secondary sm:right-4"
                  @click="togglePasswordVisibility">
                  <svg v-if="showPassword" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none"
                    viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 3l18 18" />
                    <path stroke-linecap="round" stroke-linejoin="round"
                      d="M10.58 10.58A3 3 0 0 0 12 15a3 3 0 0 0 2.42-4.42" />
                    <path stroke-linecap="round" stroke-linejoin="round"
                      d="M9.88 5.09A10.94 10.94 0 0 1 12 5c4.48 0 8.27 2.94 9.54 7a10.6 10.6 0 0 1-4.13 5.13" />
                    <path stroke-linecap="round" stroke-linejoin="round"
                      d="M6.61 6.61A10.95 10.95 0 0 0 2.46 12C3.73 16.06 7.52 19 12 19c1.18 0 2.32-.18 3.39-.5" />
                  </svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
                    stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round"
                      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- <div class="flex items-center justify-end">
              <a href="#"
                class="text-13 text-muted-ios underline underline-offset-4 hover-text-brand-secondary sm:text-14">
                Lupa Kata Sandi?
              </a>
            </div> -->

            <button type="submit" :disabled="authStore.loading"
              class="flex h-12 w-full items-center justify-center rounded-2xl bg-brand text-14 font-semibold text-on-brand transition-colors hover-bg-brand-hover disabled:cursor-not-allowed disabled:opacity-70">
              {{ authStore.loading ? 'Memproses...' : 'Masuk' }}
            </button>

            <p v-if="authStore.errorMessage" class="text-size-sm text-error">
              {{ authStore.errorMessage }}
            </p>
          </form>
        </section>
      </div>
    </div>
  </main>
</template>

<style scoped>
.login-page {
  height: 100vh;
  height: 100dvh;
}
</style>

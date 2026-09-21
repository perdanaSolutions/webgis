<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import loginImage from '~/assets/image/image_login.png'
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
  // Saat pertama load halaman login:
  // - cek cookie token
  // - validasi ke /api/v1/auth/me (di authStore.validateToken)
  // - jika valid, akan redirect ke /dashboard
  // - jika invalid/expired, tetap di /login
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
  <main class="login-page min-h-screen w-full overflow-hidden bg-splash text-14">
    <div class="relative grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <section class="relative z-10 flex items-center px-6 py-10 sm:px-10 md:px-16 lg:px-20">
        <div class="w-full max-w-[560px]">
          <h1 class="text-20 font-bold leading-tight tracking-tight text-content-dark">
            Masuk ke akun Anda!
          </h1>
          <p class="mt-5 max-w-[520px] text-14 leading-7 text-muted-ios">
            Masukkan alamat email dan kata sandi terdaftar Anda untuk mengakses dashboard dan mengelola semua fitur
            sistem dengan mudah.
          </p>

          <form class="mt-12 space-y-7" @submit.prevent="onSubmit">
            <div>
              <label for="email" class="mb-3 block text-16 font-bold leading-none text-content-dark">
                Email
              </label>
              <input id="email" v-model="form.email" type="email" placeholder="Masukan Email Anda"
                class="h-14 w-full rounded-2xl border border-input bg-surface px-6 text-14 text-content-dark outline-none placeholder-text-placeholder-light focus-border-brand-secondary focus:ring-2 focus-ring-brand-secondary-20">
            </div>

            <div>
              <label for="password" class="mb-3 block text-16 font-bold leading-none text-content-dark">
                Kata Sandi
              </label>
              <div class="relative">
                <input id="password" v-model="form.password" :type="showPassword ? 'text' : 'password'"
                  placeholder="Masukan Kata Sandi Anda"
                  class="h-14 w-full rounded-2xl border border-input bg-surface px-6 pr-16 text-14 text-content-dark outline-none placeholder-text-placeholder-light focus-border-brand-secondary focus:ring-2 focus-ring-brand-secondary-20">
                <button type="button" aria-label="Toggle password visibility"
                  class="absolute inset-y-0 right-5 my-auto h-8 w-8 text-muted-ios hover-text-brand-secondary"
                  @click="togglePasswordVisibility">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                    stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round"
                      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </button>
              </div>
            </div>

            <div class="flex items-center justify-between gap-4">
              <a href="#" class="text-14 text-muted-ios underline underline-offset-4 hover-text-brand-secondary">
                Lupa Kata Sandi?
              </a>
            </div>

            <button type="submit" :disabled="authStore.loading"
              class="mt-3 flex h-12 w-full items-center justify-center rounded-2xl bg-brand text-14 font-semibold text-on-brand transition-colors hover-bg-brand-hover disabled:cursor-not-allowed disabled:opacity-70">
              {{ authStore.loading ? 'Memproses...' : 'Masuk' }}
            </button>

            <p v-if="authStore.errorMessage" class="text-size-sm text-error">
              {{ authStore.errorMessage }}
            </p>
          </form>
        </div>
      </section>

      <section class="relative hidden lg:block">
        <div class="absolute inset-y-0 right-0 w-[58%] bg-brand" />
        <div class="absolute inset-0 flex items-center justify-center px-10">
          <div class="w-full max-w-[760px] overflow-hidden rounded-[24px] border border-white/40 shadow-2xl">
            <img :src="loginImage" alt="Ilustrasi login" class="h-[76vh] min-h-[520px] w-full object-cover">
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import loginImage from '~/assets/image/image_login.png'

defineOptions({
  name: 'LoginPage',
})

const showPassword = ref(false)
const form = reactive({
  email: '',
  password: '',
  remember: false,
})

function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}

async function onSubmit() {
  await navigateTo('/dashboard')
}
</script>

<template>
  <main class="login-page min-h-screen w-full overflow-hidden bg-[#FCFBFA] text-[14px]">
    <div class="relative grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <section class="relative z-10 flex items-center px-6 py-10 sm:px-10 md:px-16 lg:px-20">
        <div class="w-full max-w-[560px]">
          <h1 class="text-[20px] font-bold leading-tight tracking-tight text-[#2C1F1A]">
            Masuk ke akun Anda!
          </h1>
          <p class="mt-5 max-w-[520px] text-[14px] leading-7 text-[#8E8E93]">
            Masukkan alamat email dan kata sandi terdaftar Anda untuk mengakses dashboard dan mengelola semua fitur
            sistem dengan mudah.
          </p>

          <form class="mt-12 space-y-7" @submit.prevent="onSubmit">
            <div>
              <label for="email" class="mb-3 block text-[16px] font-bold leading-none text-[#2C1F1A]">
                Email
              </label>
              <input id="email" v-model="form.email" type="email" placeholder="Masukan Email Anda"
                class="h-14 w-full rounded-2xl border border-[#D8D8DC] bg-white px-6 text-[14px] text-[#2C1F1A] outline-none placeholder:text-[#B0B0B6] focus:border-[#5B432F] focus:ring-2 focus:ring-[#5B432F]/20">
            </div>

            <div>
              <label for="password" class="mb-3 block text-[16px] font-bold leading-none text-[#2C1F1A]">
                Kata Sandi
              </label>
              <div class="relative">
                <input id="password" v-model="form.password" :type="showPassword ? 'text' : 'password'"
                  placeholder="Masukan Kata Sandi Anda"
                  class="h-14 w-full rounded-2xl border border-[#D8D8DC] bg-white px-6 pr-16 text-[14px] text-[#2C1F1A] outline-none placeholder:text-[#B0B0B6] focus:border-[#5B432F] focus:ring-2 focus:ring-[#5B432F]/20">
                <button type="button" aria-label="Toggle password visibility"
                  class="absolute inset-y-0 right-5 my-auto h-8 w-8 text-[#8E8E93] hover:text-[#5B432F]"
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
              <label class="flex items-center gap-3 text-[14px] text-[#8E8E93]">
                <input v-model="form.remember" type="checkbox"
                  class="h-4 w-4 rounded border border-[#D8D8DC] text-[#5B432F] focus:ring-[#5B432F]/30">
                <span>Remember me?</span>
              </label>

              <a href="#" class="text-[14px] text-[#8E8E93] underline underline-offset-4 hover:text-[#5B432F]">
                Lupa Kata Sandi?
              </a>
            </div>

            <button type="submit"
              class="mt-3 flex h-12 w-full items-center justify-center rounded-2xl bg-[#4D392A] text-[14px] font-semibold text-white transition-colors hover:bg-[#3F2E22]">
              Masuk
            </button>
          </form>
        </div>
      </section>

      <section class="relative hidden lg:block">
        <div class="absolute inset-y-0 right-0 w-[58%] bg-[#4D392A]" />
        <div class="absolute inset-0 flex items-center justify-center px-10">
          <div class="w-full max-w-[760px] overflow-hidden rounded-[24px] border border-white/40 shadow-2xl">
            <img :src="loginImage" alt="Ilustrasi login" class="h-[76vh] min-h-[520px] w-full object-cover">
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

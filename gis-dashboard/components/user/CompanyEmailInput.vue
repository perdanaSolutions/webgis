<script setup lang="ts">
import { USER_EMAIL_DOMAIN } from "~/utils/userEmail";

defineOptions({ name: "UserCompanyEmailInput" });

/** Field email user (Tambah & Edit): nama email bisa diubah, domain tetap @teladanprima.com. */
const model = defineModel<string>({ default: "" });
defineProps<{ previousDomain?: string | null }>();
</script>

<template>
  <div>
    <div class="flex h-11 w-full overflow-hidden rounded-xl border border-default">
      <input v-model="model" required type="text" autocomplete="off" placeholder="nama_email"
        class="min-w-0 flex-1 px-3 outline-none" />
      <span class="flex shrink-0 items-center border-l border-default bg-surface-warm px-3 text-muted">
        @{{ USER_EMAIL_DOMAIN }}
      </span>
    </div>
    <p v-if="previousDomain" class="mt-1 text-12 text-warning">
      Domain email lama (@{{ previousDomain }}) akan diganti menjadi @{{ USER_EMAIL_DOMAIN }} saat disimpan.
    </p>
  </div>
</template>

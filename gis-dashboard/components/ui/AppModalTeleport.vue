<script setup lang="ts">
/** Memastikan overlay modal di-root body (tidak terpotong overflow ancestor). */
</script>

<template>
  <Teleport to="body">
    <slot />
  </Teleport>
</template>

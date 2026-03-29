<template>
  <div class="flex h-full">
    <AppSidebar />
    <main class="flex-1 overflow-auto bg-surface-white">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
</script>

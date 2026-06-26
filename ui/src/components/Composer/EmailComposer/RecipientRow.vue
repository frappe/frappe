<template>
  <div class="flex items-center gap-2 border-t py-1.5 last-of-type:border-b">
    <span class="text-p-sm text-ink-gray-4">{{ label }}</span>
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{ label: string }>();
</script>

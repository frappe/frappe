<template>
	<p v-if="description" class="text-xs text-ink-gray-5">{{ description }}</p>
</template>

<script lang="ts" setup>
defineProps<{
	description?: string
}>()
</script>

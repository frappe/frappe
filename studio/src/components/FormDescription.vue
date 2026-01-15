<template>
	<p v-if="description" class="text-xs leading-4 text-ink-gray-5">{{ description }}</p>
</template>

<script lang="ts" setup>
defineProps<{
	description?: string
}>()
</script>

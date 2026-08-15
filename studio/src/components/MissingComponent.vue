<template>
	<div
		class="flex h-[150px] w-[300px] items-center justify-center bg-surface-gray-1 font-mono text-sm text-ink-red-8"
	>
		<p>Component Missing: {{ componentName }}</p>
	</div>
</template>

<script setup lang="ts">
defineProps<{
	componentName?: string
}>()
</script>

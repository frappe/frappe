<template>
	<div class="flex items-center justify-between gap-8">
		<div class="flex w-3/4 flex-col">
			<span class="text-p-base-medium">{{ label }}</span>
			<span class="text-p-sm text-ink-gray-5">
				{{ description }}
			</span>
		</div>
		<div class="flex h-full w-1/4 items-center justify-end">
			<slot />
		</div>
	</div>
</template>

<script setup lang="ts">
defineProps<{
	label: string
	description: string
}>()
</script>

<template>
	<div class="flex items-center gap-8 py-4">
		<div class="min-w-0 flex-1">
			<div class="text-sm font-medium text-ink-gray-9">{{ title }}</div>
			<p v-if="description" class="mt-1.5 text-xs leading-5 text-ink-gray-6">{{ description }}</p>
		</div>
		<slot />
	</div>
</template>

<script setup>
// One setting: a title and description on the left, its control on the right.
defineProps({
	title: { type: String, required: true },
	description: { type: String, default: "" },
})
</script>

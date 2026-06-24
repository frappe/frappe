<template>
	<div class="mb-4 flex flex-col gap-3">
		<div class="flex items-center justify-between">
			<h3 class="dark:text-zinc-300 text-base-medium text-ink-gray-9">{{ title }}</h3>
			<slot name="actions"></slot>
		</div>
		<slot></slot>
	</div>
</template>

<script setup lang="ts">
defineProps<{
	title: string
}>()
</script>

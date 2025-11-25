<template>
	<div class="flex flex-col gap-3">
		<div class="flex items-center justify-between text-sm font-medium">
			<h3 class="text-base text-gray-900">{{ title }}</h3>
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

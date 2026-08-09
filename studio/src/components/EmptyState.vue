<template>
	<div
		class="flex flex-col items-center rounded border-2 border-dashed border-outline-gray-2 p-5 text-center text-sm leading-5 text-ink-gray-5"
	>
		<slot>{{ message }}</slot>
	</div>
</template>

<script setup lang="ts">
defineProps<{ message?: string }>()
</script>

<template>
	<div
		class="flex flex-col items-center rounded border-2 border-dashed border-gray-300 p-5 text-sm text-gray-600"
	>
		{{ message }}
	</div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
</script>

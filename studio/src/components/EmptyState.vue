<template>
	<div
		class="flex flex-col items-center rounded border-2 border-dashed border-gray-300 p-5 text-center text-sm leading-5 text-gray-600"
	>
		{{ message }}
	</div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
</script>

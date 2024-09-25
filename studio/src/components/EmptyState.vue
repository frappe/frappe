<template>
	<div class="py-2 text-center text-sm text-gray-600">{{ message }}</div>
</template>

<script setup lang="ts">
defineProps({
	message: {
		type: String,
		required: true,
	},
})
</script>

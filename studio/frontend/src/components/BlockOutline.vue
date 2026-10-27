<template>
	<!-- fixed and outside any transform, so the measured viewport rect lands where it was
	     measured; the editor's block-selection ring (ComponentEditor) -->
	<div
		v-if="rect"
		class="pointer-events-none fixed z-50 ring-2 ring-inset ring-outline-blue-4"
		:style="{
			left: `${rect.left}px`,
			top: `${rect.top}px`,
			width: `${rect.width}px`,
			height: `${rect.height}px`,
		}"
		aria-hidden="true"
	/>
</template>

<script setup lang="ts">
defineProps<{ rect: DOMRect | null }>()
</script>

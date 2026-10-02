<script setup>
// A labelled group of rows in one rounded panel: Gameplan's More menu
// (frontend/src/components/MobileMoreMenu.vue).
defineProps({ label: { type: String, default: "" } });
</script>

<template>
	<section>
		<div v-if="label" class="mb-2 pl-[18px] text-lg-medium text-ink-gray-5">{{ label }}</div>
		<nav class="overflow-hidden rounded-7 bg-surface-base">
			<slot />
		</nav>
	</section>
</template>

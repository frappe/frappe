<template>
	<!-- shared card frame for email/comment rows; the header (incl. its padding) is fully slotted -->
	<div
		class="grow cursor-pointer overflow-hidden rounded-md border border-outline-gray-2 bg-surface-white text-base leading-6 transition-all duration-300 ease-in-out"
	>
		<slot name="header" />
		<hr class="border-t border-outline-gray-modals" />
		<!-- content region; padding/background varies per row type -->
		<div :class="contentClass">
			<slot />
		</div>
	</div>
</template>

<script setup lang="ts">
withDefaults(
	defineProps<{
		// padding/background for the content region below the divider
		contentClass?: string;
	}>(),
	{ contentClass: "" }
);
</script>

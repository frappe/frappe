<template>
	<Transition name="setup-preview-swap" mode="out-in">
		<slot />
	</Transition>
</template>

<script setup lang="ts">
/** Blurs one view of the preview into the next. Key the slot's single child by what it shows. */
defineSlots<{
	/** One element, keyed, so a new key swaps it. */
	default?: () => unknown;
}>();
</script>

<style>
@media (prefers-reduced-motion: no-preference) {
	.setup-preview-swap-enter-active {
		transition: opacity 300ms ease-out, filter 300ms ease-out;
	}
	.setup-preview-swap-leave-active {
		transition: opacity 150ms ease-in, filter 150ms ease-in;
	}
	.setup-preview-swap-enter-from,
	.setup-preview-swap-leave-to {
		opacity: 0;
		filter: blur(6px);
	}
}
</style>

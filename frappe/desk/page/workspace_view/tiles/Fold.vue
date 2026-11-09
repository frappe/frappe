<script setup>
defineProps({
	open: { type: Boolean, required: true },
});
</script>

<template>
	<Transition name="fold">
		<div v-if="open" class="fold">
			<div class="fold-body"><slot /></div>
		</div>
	</Transition>
</template>

<style scoped>
.fold {
	display: grid;
	grid-template-rows: 1fr;
}

.fold-body {
	min-height: 0;
}

.fold-enter-active,
.fold-leave-active {
	transition: grid-template-rows 250ms cubic-bezier(0.32, 0.72, 0, 1),
		opacity 250ms cubic-bezier(0.32, 0.72, 0, 1);
}

/* only while moving, so a focus ring inside is not clipped at rest */
.fold-enter-active > .fold-body,
.fold-leave-active > .fold-body {
	overflow: hidden;
}

.fold-enter-from,
.fold-leave-to {
	grid-template-rows: 0fr;
	opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
	.fold-enter-active,
	.fold-leave-active {
		transition-property: opacity;
	}
}
</style>

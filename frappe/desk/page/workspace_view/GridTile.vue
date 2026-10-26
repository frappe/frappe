<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
	size: { type: Object, required: true },
});

const body = ref(null);
const measured_rows = ref(1);
let observer = null;

// An auto-height tile snaps to its content in whole grid rows, so nothing clips or scrolls.
onMounted(() => {
	if (props.size.rows) return;
	observer = new ResizeObserver(() => {
		const style = getComputedStyle(body.value.parentElement);
		const row = parseFloat(style.getPropertyValue("grid-auto-rows"));
		const gap = parseFloat(style.getPropertyValue("row-gap")) || 0;
		measured_rows.value = Math.max(
			1,
			Math.ceil((body.value.offsetHeight + gap) / (row + gap))
		);
	});
	observer.observe(body.value);
});

onBeforeUnmount(() => observer?.disconnect());

const style = computed(() => ({
	"--span-12": props.size.span[12],
	"--span-6": props.size.span[6],
	"--span-2": props.size.span[2],
	"--rows": props.size.rows || measured_rows.value,
}));
</script>

<template>
	<div class="ws-tile" :style="style">
		<div ref="body" :class="size.rows ? 'h-full' : ''">
			<slot />
		</div>
	</div>
</template>

<style scoped>
.ws-tile {
	min-width: 0;
	grid-column: span var(--span-2);
	grid-row: span var(--rows);
}

@media (min-width: 576px) {
	.ws-tile {
		grid-column: span var(--span-6);
	}
}

@media (min-width: 992px) {
	.ws-tile {
		grid-column: span var(--span-12);
	}
}
</style>

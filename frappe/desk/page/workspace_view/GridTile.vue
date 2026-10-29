<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref } from "vue";

const props = defineProps({
	size: { type: Object, required: true },
});

const body = ref(null);
const measured_tracks = ref(1);
const max_height = ref(null);
let observer = null;

const fixed = computed(() => props.size.rows && !props.size.shrinks);

// the height in px a shrinking tile may grow to, for a tile that fills itself to fit
provide("tile_max_height", max_height);
provide(
	"tile_size",
	computed(() => props.size.name)
);

// A grid row (a size's height unit) is 18 of the grid's tracks, gap included. See WorkspaceGrid.
const TRACKS_PER_ROW = 18;

// An auto-height tile spans just enough tracks for its content and the gap under it.
onMounted(() => {
	if (fixed.value) return;
	observer = new ResizeObserver(() => {
		const style = getComputedStyle(body.value.closest(".ws-grid"));
		const track = parseFloat(style.getPropertyValue("grid-auto-rows"));
		const gap = parseFloat(style.getPropertyValue("column-gap")) || 0;
		if (props.size.shrinks) max_height.value = props.size.rows * TRACKS_PER_ROW * track - gap;
		measured_tracks.value = Math.max(1, Math.ceil((body.value.offsetHeight + gap) / track));
	});
	observer.observe(body.value);
});

onBeforeUnmount(() => observer?.disconnect());

const style = computed(() => ({
	"--span-12": props.size.span[12],
	"--span-6": props.size.span[6],
	"--span-2": props.size.span[2],
	"--tracks": fixed.value ? props.size.rows * TRACKS_PER_ROW : measured_tracks.value,
}));
</script>

<template>
	<div class="ws-tile" :style="style">
		<div ref="body" :class="fixed ? 'h-full' : ''">
			<slot />
		</div>
	</div>
</template>

<style scoped>
.ws-tile {
	position: relative;
	min-width: 0;
	grid-column: span var(--span-2);
	grid-row: span var(--tracks);
	padding-bottom: var(--ws-gap);
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

<!--
  An app's logo, 56px, 20px or 16px: as is when it fills its square, a bare mark at half size on a
  white plate, and the title's first letter when there is no logo or it fails to load.
-->
<template>
	<span
		class="flex shrink-0 items-center justify-center"
		:class="[SIZES[size], frame]"
		data-app-logo
		:data-bare="bare || undefined"
	>
		<!-- Light on the plate: a mark that follows a dark OS theme would draw white on white. -->
		<img
			v-if="logo && !broken"
			:src="logo"
			alt=""
			loading="lazy"
			class="object-contain"
			:class="bare ? 'size-1/2 [color-scheme:light]' : 'size-full'"
			@load="measure"
			@error="broken = true"
		/>
		<span v-else aria-hidden="true">{{ title.charAt(0).toUpperCase() }}</span>
	</span>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

const props = withDefaults(
	defineProps<{ logo?: string | null; title: string; size?: 56 | 20 | 16 }>(),
	{ size: 56 }
);

const SIZES = { 56: "size-14 text-2xl", 20: "size-5 text-xs", 16: "size-4 text-2xs" };

const PLATE = "rounded-[22%] bg-white ring-1 ring-inset ring-outline-gray-2";
const LETTER = "rounded-[22%] bg-surface-gray-3 font-medium text-ink-gray-6";

const bare = ref(false);
const broken = ref(false);

const frame = computed(() => {
	if (!props.logo || broken.value) return LETTER;
	return bare.value ? PLATE : "";
});

const SIDE = 64;

// An app icon is opaque at its edge midpoints, where only a bare mark is transparent.
function measure(event: Event) {
	const canvas = document.createElement("canvas");
	canvas.width = canvas.height = SIDE;
	const context = canvas.getContext("2d");
	if (!context) return;
	const middle = SIDE / 2;
	const edges = [
		[middle, 1],
		[middle, SIDE - 2],
		[1, middle],
		[SIDE - 2, middle],
	];
	try {
		context.drawImage(event.target as HTMLImageElement, 0, 0, SIDE, SIDE);
		bare.value = edges.some(([x, y]) => context.getImageData(x, y, 1, 1).data[3] < 128);
	} catch {
		// A logo from another origin taints the canvas, and an SVG with no size cannot be drawn.
	}
}
</script>

<template>
	<div
		data-slot="setup-preview-cursor"
		class="pointer-events-none absolute left-0 top-0 z-10 transition-transform duration-700 ease-[cubic-bezier(.65,0,.35,1)] motion-reduce:transition-none"
		:style="{ transform: `translate(${x}px, ${y}px)` }"
	>
		<span
			ref="ripple"
			class="absolute -left-4 -top-4 size-8 rounded-full bg-surface-gray-9 opacity-0"
		/>
		<div ref="pointer" class="origin-top-left">
			<svg class="size-5 drop-shadow-md" viewBox="0 0 20 20" fill="none">
				<path
					d="M3 2 L3 16 L7 12.5 L9.6 18 L12 17 L9.5 11.6 L15 11.4 Z"
					fill="#111"
					stroke="#fff"
					stroke-width="1.4"
					stroke-linejoin="round"
				/>
			</svg>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";

defineProps<{
	/**
	 * Where the tip points, in the app's own pixels from its top left corner. Physical, not
	 * start-relative: the drawing it sits in keeps its left edge whatever the text direction.
	 */
	x: number;
	y: number;
}>();

const pointer = ref<HTMLElement | null>(null);
const ripple = ref<HTMLElement | null>(null);

/** Presses where the cursor is: it dips and a ring spreads. */
function click() {
	pointer.value?.animate(
		[{ transform: "scale(1)" }, { transform: "scale(.82)" }, { transform: "scale(1)" }],
		{ duration: 260, easing: "ease-out" }
	);
	ripple.value?.animate(
		[
			{ transform: "scale(.3)", opacity: 0.5 },
			{ transform: "scale(1.8)", opacity: 0 },
		],
		{ duration: 600, easing: "ease-out" }
	);
}

defineExpose({ click });
</script>

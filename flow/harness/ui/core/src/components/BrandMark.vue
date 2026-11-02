<template>
	<!-- `line`: Flow's mark as a thin line in the text's colour, for the new chat; its box hugs the
	     mark, so `size` is the mark's own -->
	<svg
		v-if="line"
		:width="size"
		:height="size"
		viewBox="3.25 2.6 17.5 17.5"
		fill="none"
		role="img"
		aria-label="Flow"
		class="block flex-none select-none text-ink-gray-6"
		:style="{ width: `${size}px`, height: `${size}px` }"
	>
		<path
			d="M4.4 4.15H14.4A5.2 5.2 0 0 1 19.6 9.35V13.35A5.2 5.2 0 0 1 14.4 18.55H9.6A5.2 5.2 0 0 1 4.4 13.35V8.45"
			stroke="currentColor"
			stroke-width="2.1"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
		<circle cx="9.1" cy="10.8" r="1.5" fill="currentColor" />
		<circle cx="14.5" cy="10.8" r="1.5" fill="currentColor" />
	</svg>
	<img
		v-else
		:src="otto"
		:width="size"
		:height="size"
		alt="Flow"
		class="block flex-none select-none object-contain"
		:style="{ width: `${size}px`, height: `${size}px` }"
	/>
</template>

<script setup>
import otto from "../assets/flow.png"

defineProps({ size: { type: Number, default: 18 }, line: { type: Boolean, default: false } })
</script>

<template>
	<!-- `line`: Flow's mark as a thin line in the text's colour, for the new chat; its box hugs the
	     mark, so `size` is the mark's own. `state` gives it a life: at rest ("idle") it blinks
	     now and then, present and attentive. Point at it, or at the button it sits in, and it winks -->
	<svg
		v-if="line"
		:width="size"
		:height="size"
		viewBox="3.25 2.6 17.5 17.5"
		fill="none"
		role="img"
		aria-label="Flow"
		class="flow-mark block flex-none select-none text-ink-gray-6"
		:class="state && `flow-mark-${state}`"
		:style="{ width: `${size}px`, height: `${size}px`, '--blink-delay': `${delay}s` }"
	>
		<path
			d="M4.4 4.15H14.4A5.2 5.2 0 0 1 19.6 9.35V13.35A5.2 5.2 0 0 1 14.4 18.55H9.6A5.2 5.2 0 0 1 4.4 13.35V8.45"
			stroke="currentColor"
			stroke-width="2.1"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
		<g class="flow-mark-eyes">
			<circle cx="9.1" cy="10.8" r="1.5" fill="currentColor" />
			<circle cx="14.5" cy="10.8" r="1.5" fill="currentColor" />
		</g>
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

defineProps({
	size: { type: Number, default: 18 },
	line: { type: Boolean, default: false },
	// "idle" blinks; null keeps the mark still
	state: { type: String, default: "idle" },
})

// each mark keeps its own moment in the blink, so two on one screen never blink as one
const delay = -(Math.random() * 6).toFixed(2)
</script>

<style scoped>
.flow-mark-eyes circle {
	transform-box: fill-box;
	transform-origin: center;
}
/* still for anyone who asked for less motion */
@media (prefers-reduced-motion: no-preference) {
	.flow-mark-idle .flow-mark-eyes circle {
		animation: flow-mark-blink 6s ease-in-out var(--blink-delay, 0s) infinite;
	}
	/* the easter egg: pointed at, it winks back */
	.flow-mark:hover .flow-mark-eyes circle:last-child,
	button:hover .flow-mark .flow-mark-eyes circle:last-child {
		animation: flow-mark-wink 0.6s ease-in-out;
	}
}
@keyframes flow-mark-wink {
	0%,
	100% {
		transform: scaleY(1);
	}
	30%,
	60% {
		transform: scaleY(0.12);
	}
}
@keyframes flow-mark-blink {
	0%,
	94%,
	100% {
		transform: scaleY(1);
	}
	97% {
		transform: scaleY(0.15);
	}
}
</style>

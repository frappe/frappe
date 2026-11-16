<template>
	<!-- `line`: Flow's mark as a thin line in the text's colour, for the new chat; its box hugs the
	     mark, so `size` is the mark's own. `state` gives it a life: at rest ("idle") it blinks
	     now and then, present and attentive. Point at it, or at the button it sits in, and it winks -->
	<svg
		v-if="line"
		ref="mark"
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
		<g class="flow-mark-eyes" :style="gaze">
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
import { computed, onBeforeUnmount, ref, watch } from "vue"
import otto from "../assets/flow.png"

const props = defineProps({
	size: { type: Number, default: 18 },
	line: { type: Boolean, default: false },
	// "idle" blinks; null keeps the mark still
	state: { type: String, default: "idle" },
	// where the line mark's eyes look: "pointer" follows it about the page, "down" reads what is
	// typed under it, "up" looks back at the one typing; null looks ahead
	look: { type: String, default: null },
})

// each mark keeps its own moment in the blink, so two on one screen never blink as one
const delay = -(Math.random() * 6).toFixed(2)

// the eyes move at most this far, in the mark's own units, and reach it this far off (px)
const REACH = 0.9
const FAR = 300
const FIXED = { down: [0, 1], up: [0, -0.7] }
const mark = ref(null)
const eyes = ref([0, 0])
const still = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches
const gaze = computed(() => {
	const [x, y] = props.look === "pointer" ? eyes.value : (FIXED[props.look] ?? [0, 0])
	return still || (!x && !y) ? null : { transform: `translate(${x}px, ${y}px)` }
})

let frame = 0
function follow(event) {
	if (frame) return
	frame = requestAnimationFrame(() => {
		frame = 0
		const box = mark.value?.getBoundingClientRect()
		if (!box) return
		const dx = event.clientX - (box.left + box.width / 2)
		const dy = event.clientY - (box.top + box.height / 2)
		const far = Math.hypot(dx, dy) || 1
		const reach = Math.min(1, far / FAR) * REACH
		eyes.value = [(dx / far) * reach, (dy / far) * reach]
	})
}
const following = computed(() => props.line && props.look === "pointer" && !still)
watch(
	following,
	(on) => {
		if (typeof window === "undefined") return
		if (on) window.addEventListener("pointermove", follow, { passive: true })
		else window.removeEventListener("pointermove", follow)
	},
	{ immediate: true }
)
onBeforeUnmount(() => {
	window.removeEventListener("pointermove", follow)
	cancelAnimationFrame(frame)
})
</script>

<style scoped>
.flow-mark-eyes circle {
	transform-box: fill-box;
	transform-origin: center;
}
/* still for anyone who asked for less motion */
@media (prefers-reduced-motion: no-preference) {
	.flow-mark-eyes {
		transition: transform 0.25s ease-out;
	}
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

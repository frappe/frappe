<template>
	<svg :height="radius * 2" :width="radius * 2">
		<circle
			:stroke-dasharray="circumference + ' ' + circumference"
			:style="{
				stroke: secondary,
				strokeDashoffset: 0,
			}"
			:stroke-width="stroke"
			fill="transparent"
			:r="normalizedRadius"
			:cx="radius"
			:cy="radius"
		/>
		<circle
			:stroke-dasharray="circumference + ' ' + circumference"
			:style="{
				stroke: primary,
				strokeDashoffset: strokeDashoffset,
			}"
			:stroke-width="stroke"
			fill="transparent"
			:r="normalizedRadius"
			:cx="radius"
			:cy="radius"
		/>
		<text
			dominant-baseline="middle"
			text-anchor="middle"
			:x="radius"
			:y="radius"
			:style="{
				color: 'var(--text-color)',
				fontSize: 'var(--text-xs)',
				fontWeight: 'var(--text-bold)',
			}"
		>
			{{ progress }}%
		</text>
	</svg>
</template>

<script setup>
import { computed, ref } from "vue";

// props
const props = defineProps({
	primary: String,
	secondary: String,
	radius: Number,
	progress: Number,
	stroke: Number,
});

// variables
let normalizedRadius = ref(props.radius - props.stroke * 2);
let circumference = ref(normalizedRadius.value * 2 * Math.PI);

// computed
let strokeDashoffset = computed(() => {
	return circumference.value - (props.progress / 100) * circumference.value;
});
</script>

<style scoped>
circle {
	transition: stroke-dashoffset 0.35s;
	transform: rotate(-90deg);
	transform-origin: 50% 50%;
}
</style>

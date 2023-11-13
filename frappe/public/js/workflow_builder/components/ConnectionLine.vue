<script setup>
import { getSmoothStepPath, SmoothStepEdge } from "@vue-flow/core";
import { computed } from "vue";

const props = defineProps({
	sourceX: { type: Number, required: true },
	sourceY: { type: Number, required: true },
	targetX: { type: Number, required: true },
	targetY: { type: Number, required: true },
	sourcePosition: { type: String, required: false },
	targetPosition: { type: String, required: false },
	sourceHandle: { type: Object, required: false },
	targetHandle: { type: Object, required: false },
	markerEnd: { type: String, required: false },
});

let opposite = {
	left: "left",
	right: "right",
	top: "bottom",
	bottom: "top",
};

const d = computed(() =>
	getSmoothStepPath({
		...props,
		borderRadius: 30,
		targetPosition: opposite[props.targetPosition],
	})
);
</script>
<template>
	<SmoothStepEdge class="animated" :path="d[0]" />
</template>

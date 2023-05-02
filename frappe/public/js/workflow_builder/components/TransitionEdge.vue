<script setup>
import { computed, watch } from "vue";
import { getSmoothStepPath, SmoothStepEdge, useVueFlow } from "@vue-flow/core";

let { findEdge } = useVueFlow();

const props = defineProps({
	id: { type: String, required: true },
	sourceX: { type: Number, required: true },
	sourceY: { type: Number, required: true },
	targetX: { type: Number, required: true },
	targetY: { type: Number, required: true },
	sourcePosition: { type: String, required: false },
	targetPosition: { type: String, required: false },
	sourceHandle: { type: String, required: false },
	targetHandle: { type: String, required: false },
	source: { type: String, required: false },
	target: { type: String, required: false },
	sourceNode: { type: Object, required: true },
	targetNode: { type: Object, required: true },
	markerEnd: { type: String, required: false },
	selected: { type: Boolean, required: false },
	data: { type: Object, required: false }
});

let marker_end = {
	type: "arrow",
	width: 15,
	height: 15,
	strokeWidth: 1.5,
	color: "#687178"
};

let marker_end_primary = {
	type: "arrow",
	width: 11,
	height: 11,
	strokeWidth: 1.7,
	color: "#2490ef"
};

watch(
	() => props.selected,
	() => {
		if (props.target?.startsWith("action-")) return;
		findEdge(props.id).markerEnd = props.selected ? marker_end_primary : marker_end;
	},
	{ immediate: true }
);

const d = computed(() => {
	return getSmoothStepPath({
		sourceX: props.sourceX,
		sourceY: props.sourceY,
		targetX: props.targetX,
		targetY: props.targetY,
		sourceHandle: props.sourceHandle,
		targetHandle: props.targetHandle,
		sourcePosition: props.sourcePosition,
		targetPosition: props.targetPosition,
		targetNode: props.targetNode,
		borderRadius: 30
	});
});
</script>
<script>
export default {
	inheritAttrs: false
};
</script>
<template>
	<SmoothStepEdge class="transition-edge" :id="id" :path="d[0]" :markerEnd="markerEnd" />
</template>

<style lang="scss" scoped>
.access {
	pointer-events: all;
	cursor: pointer;
	position: absolute;
	font-size: var(--text-sm);
	padding: 2px 6px;
	border-radius: 16px;
	background-color: var(--fg-color);
	border: 1px solid var(--gray-600);
	box-shadow: var(--shadow-base);
}
</style>

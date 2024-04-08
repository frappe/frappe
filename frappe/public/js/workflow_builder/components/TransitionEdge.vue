<script setup>
import { computed, nextTick, watch } from "vue";
import { getSmoothStepPath, SmoothStepEdge, useVueFlow, EdgeLabelRenderer } from "@vue-flow/core";

let { findEdge, getSelectedNodes } = useVueFlow();

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
	data: { type: Object, required: false },
});

let marker_end = {
	type: "arrow",
	width: 15,
	height: 15,
	strokeWidth: 1.5,
	color: "#687178",
};

let marker_end_primary = {
	type: "arrow",
	width: 11,
	height: 11,
	strokeWidth: 1.7,
	color: "#171717",
};

watch(
	() => props.selected,
	(val) => {
		let target_is_action = props.target?.startsWith("action-");
		val && selectAction(target_is_action);
		if (target_is_action) return;
		findEdge(props.id).markerEnd = val ? marker_end_primary : marker_end;
	},
	{ immediate: true }
);

function selectAction(target_is_action) {
	let action = target_is_action ? props.targetNode : props.sourceNode;
	if (action.selected) return;
	getSelectedNodes.value?.forEach((node) => (node.selected = false));
	nextTick(() => (action.selected = true));
}

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
		borderRadius: 30,
	});
});
</script>
<script>
export default {
	inheritAttrs: false,
};
</script>
<template>
	<SmoothStepEdge class="transition-edge" :id="id" :path="d[0]" :markerEnd="markerEnd" />
	<EdgeLabelRenderer v-if="markerEnd == 'url(#)'">
		<div
			@click.stop="selectAction(true)"
			:style="{
				transform: `translate(-50%, -50%) translate(${d[1]}px, ${d[2]}px)`,
				borderColor: selected ? 'var(--primary)' : 'var(--gray-600)',
				borderWidth: selected ? '1.5px' : '1px',
			}"
			class="access nodrag nopan"
		>
			<span class="mr-1" v-html="frappe.utils.icon('users', 'sm')"></span>
			<span>{{ __(targetNode.data.allowed) }}</span>
		</div>
	</EdgeLabelRenderer>
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

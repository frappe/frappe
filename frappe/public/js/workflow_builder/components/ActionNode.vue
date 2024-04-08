<script setup>
import { Handle, useVueFlow } from "@vue-flow/core";
import { watch, computed } from "vue";
import { useStore } from "../store";

const props = defineProps({
	node: {
		type: Object,
		required: true,
	},
});

const isValidConnection = ({ source, target }) => {
	if (
		(source.startsWith("action-") && !target.startsWith("action-")) ||
		(!source.startsWith("action-") && target.startsWith("action-")) ||
		(source.startsWith("action-") && target.startsWith("action-"))
	) {
		return false;
	}

	return source !== target;
};

let store = useStore();
const { edges, findNode } = useVueFlow();
watch(
	() => findNode(props.node.id)?.selected,
	(val) => {
		if (val) store.workflow.selected = props.node;

		let connected_edges = edges.value.filter(
			(edge) => edge.source === props.node.id || edge.target === props.node.id
		);
		connected_edges.forEach((edge) => (edge.selected = val));
	}
);

let label = computed(() => findNode(props.node.id)?.data?.action);

watch(
	() => props.node.data,
	() => {
		store.ref_history.commit();
	},
	{ deep: true }
);
</script>

<template>
	<div class="node" tabindex="0" @click.stop="store.workflow.selected = node">
		<div v-if="label" class="node-label">{{ __(label) }}</div>
		<div v-else class="node-placeholder text-muted">{{ __("No Label") }}</div>
		<Handle
			v-for="handle in ['top', 'right', 'bottom', 'left']"
			class="handle"
			:style="{ [handle]: '-3px', opacity: 0 }"
			type="source"
			:position="handle"
			:id="handle"
			:isValidConnection="isValidConnection"
			@click.stop
		/>
	</div>
</template>

<style lang="scss" scoped>
.node {
	position: relative;
	background-color: var(--gray-500);
	font-weight: 500;
	border-radius: 5px;
	padding: 5px 10px;
	color: var(--fg-color);
	border: 1px solid var(--fg-color);
	box-shadow: var(--shadow-base);
}

.vue-flow__node.selected .node {
	outline: 1.5px solid var(--primary);
	outline-offset: 2px;
}
</style>

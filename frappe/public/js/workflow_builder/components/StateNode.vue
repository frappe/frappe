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
		(!source.startsWith("action-") && target.startsWith("action-"))
	) {
		return false;
	}

	return source !== target;
};

let store = useStore();
const { findNode } = useVueFlow();
watch(
	() => findNode(props.node.id)?.selected,
	(val) => {
		if (val) store.workflow.selected = props.node;
	}
);

let label = computed(() => findNode(props.node.id)?.data?.state);

watch(
	() => props.node.data,
	() => {
		store.ref_history.commit();
	},
	{ deep: true }
);
</script>

<template>
	<div class="node" tabindex="0" @click.stop>
		<div v-if="label" class="node-label">{{ __(label) }}</div>
		<div v-else class="node-placeholder text-muted">{{ __("No Label") }}</div>
		<Handle
			v-for="handle in ['top', 'right', 'bottom', 'left']"
			class="handle"
			:style="{ [handle]: '-12px' }"
			type="source"
			:position="handle"
			:id="handle"
			:isValidConnection="isValidConnection"
		/>
	</div>
</template>

<style lang="scss" scoped>
.node {
	position: relative;
	background-color: var(--fg-color);
	font-weight: 500;
	border-radius: var(--border-radius-full);
	padding: 15px 25px;
	color: var(--gray-600);
	border: 1px solid var(--gray-600);
	box-shadow: var(--shadow-base);

	.node-label {
		max-width: 110px;
		text-align: center;
	}
}

.vue-flow__node.selected .node {
	outline: 1.5px solid var(--primary);
	outline-offset: 2px;
}

.handle {
	position: absolute;
	width: 7px;
	height: 7px;
	background-color: var(--gray-600);
	border-radius: 50%;
	transition: all 0.2s ease-in-out;
}
</style>

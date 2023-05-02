<script setup>
import { Handle } from "@vue-flow/core";

const props = defineProps({
	node: {
		type: Object,
		required: true
	}
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
</script>

<template>
	<div class="node" tabindex="0">
		<div v-if="node.data.state" class="node-label">{{ node.data.state }}</div>
		<div v-else class="node-placeholder text-muted">{{ __("No Label") }}</div>
		<Handle
			v-for="handle in ['top', 'right', 'bottom', 'left']"
			class="handle"
			:style="{ [handle]: '-12px'}"
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
	border-radius: 50%;
	padding: 25px;
	color: var(--gray-600);
	border: 1px solid var(--gray-600);
	box-shadow: var(--shadow-base);
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

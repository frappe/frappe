<script setup>
import { Handle, Position } from "@vue-flow/core";

const props = defineProps({
	node: {
		type: Object,
		required: true
	}
});
</script>

<template>
	<div class="node" tabindex="0">
		<div v-if="node.label" class="node-label">{{ node.label }}</div>
		<div v-else class="node-placeholder text-muted">{{ __("No Label") }}</div>
		<Handle class="handle handle-a" type="source" :position="Position.Top" id="a" />
		<Handle class="handle handle-b" type="source" :position="Position.Right" id="b" />
		<Handle class="handle handle-c" type="source" :position="Position.Bottom" id="c" />
		<Handle class="handle handle-d" type="source" :position="Position.Left" id="d" />
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

	&.handle-a {
		top: -12px;
	}

	&.handle-b {
		right: -12px;
	}

	&.handle-c {
		bottom: -12px;
	}

	&.handle-d {
		left: -12px;
	}
}
</style>

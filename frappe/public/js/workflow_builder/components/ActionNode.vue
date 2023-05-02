<script setup>
import { Handle } from "@vue-flow/core";

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
		<Handle
			v-for="handle in ['top', 'right', 'bottom', 'left']"
			class="handle"
			:style="{ [handle]: '-3px', opacity: 0 }"
			type="source"
			:position="handle"
			:id="handle"
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

<script setup>
import { VueFlow, useVueFlow, Panel, PanelPosition } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import TransitionEdge from "./components/TransitionEdge.vue";
import StateNode from "./components/StateNode.vue";
import { useStore } from "./store";

let store = useStore();
let { nodes, onConnect, addNodes, addEdges } = useVueFlow();

function add_state() {
	let state_id = (nodes.value.length + 1).toString();
	addNodes([
		{
			id: state_id,
			type: "state",
			label: "State " + state_id,
			position: { x: 250, y: 100 }
		}
	]);
}

onConnect(params => {
	params.animated = true;
	params.type = "transition";
	addEdges([params]);
});
</script>

<template>
	<div class="workflow-container">
		<VueFlow v-model="store.workflow.elements" connection-mode="loose">
			<Background pattern-color="#aaa" gap="10" />
			<Panel :position="PanelPosition.TopRight">
				<button @click="add_state">Add State</button>
			</Panel>
			<template #node-state="node">
				<StateNode :node="node" />
			</template>
			<template #edge-transition="props">
				<TransitionEdge v-bind="props" />
			</template>
		</VueFlow>
	</div>
</template>

<style lang="scss" scoped>
@import "@vue-flow/core/dist/style.css";
@import "@vue-flow/core/dist/theme-default.css";

.workflow-container {
	width: 100%;
	height: calc(100vh - var(--navbar-height) - var(--page-head-height) - 65px);
	border-radius: var(--border-radius-lg);
	border: 1px solid var(--border-color);
	background-color: var(--fg-color);
}

:deep(.transition-edge) {
	stroke: var(--gray-600);
	stroke-width: 1.5px;
}

:deep(.selected) {
	.transition-edge {
		stroke: var(--primary);
		stroke-width: 2px;
	}
}
</style>

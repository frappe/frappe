<script setup>
import { VueFlow, useVueFlow, Panel, PanelPosition } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import TransitionEdge from "./components/TransitionEdge.vue";
import StateNode from "./components/StateNode.vue";
import ActionNode from "./components/ActionNode.vue";
import ConnectionLine from "./components/ConnectionLine.vue";
import { useStore } from "./store";
import { nextTick, onMounted, watch } from "vue";

let store = useStore();
let {
	nodes,
	getEdges,
	findNode,
	onNodeDragStop,
	onConnect,
	onEdgeUpdate,
	addNodes,
	addEdges,
	setEdges,
	updateEdge,
	onPaneReady,
	fitView,
	zoomIn,
	zoomOut,
	project,
	vueFlowRef
} = useVueFlow();

onNodeDragStop(() => {
	nextTick(() => store.ref_history.commit());
});

onConnect(edge => {
	let source_node = findNode(edge.source);
	let target_node = findNode(edge.target);

	let source_center = {
		x: source_node.position.x + source_node.dimensions.width / 2,
		y: source_node.position.y + source_node.dimensions.height / 2
	};

	let target_center = {
		x: target_node.position.x + target_node.dimensions.width / 2,
		y: target_node.position.y + target_node.dimensions.height / 2
	};

	let center_x = (source_center.x + target_center.x) / 2;
	let center_y = source_center.y;

	const action_node = {
		id: "action-" + frappe.utils.get_random(5),
		type: "action",
		position: { x: center_x, y: center_y },
		data: {
			action: "",
			allowed: "All",
			from: source_node.data.state,
			to: target_node.data.state
		},
	};
	addNodes([action_node]);

	let action_edge = {
		source: edge.source,
		sourceHandle: edge.sourceHandle,
		target: action_node.id,
		targetHandle: "left",
		type: "transition",
		updatable: true,
		animated: true
	};
	let state_edge = {
		source: action_node.id,
		sourceHandle: "right",
		target: edge.target,
		targetHandle: edge.targetHandle,
		type: "transition",
		updatable: true,
		animated: true
	};
	addEdges([action_edge, state_edge]);

	nextTick(() => {
		const node = findNode(action_node.id);
		const stop = watch(
			() => node.dimensions,
			dimensions => {
				if (dimensions.width > 0 && dimensions.height > 0) {
					node.position = {
						x: node.position.x - node.dimensions.width / 2,
						y: node.position.y - node.dimensions.height / 2
					};
					stop();
					store.ref_history.commit();
				}
			},
			{ deep: true, flush: "post" }
		);
	});
});

onEdgeUpdate(({ edge, connection }) => {
	if (
		(connection.source == edge.source && connection.target != edge.target) ||
		(connection.source != edge.source && connection.target == edge.target) ||
		connection.source === connection.target
	)
		return;

	updateEdge(edge, connection);
	setEdges(getEdges.value);
	nextTick(() => store.ref_history.commit());
});

function onDragOver(event) {
	event.preventDefault();

	if (event.dataTransfer) {
		event.dataTransfer.dropEffect = "move";
	}
}

function onDrop(event) {
	const { left, top } = vueFlowRef.value.getBoundingClientRect();

	const position = project({
		x: event.clientX - left,
		y: event.clientY - top
	});

	let state_ids = nodes.value.filter(node => node.type == "state").map(node => node.id);
	let state_id = (Math.max(...state_ids) + 1).toString();
	const new_state = {
		id: state_id,
		type: "state",
		position,
		data: {
			state: "",
			doc_status: "0",
			allow_edit: "All"
		}
	};

	addNodes([new_state]);

	nextTick(() => {
		const node = findNode(new_state.id);
		const stop = watch(
			() => node.dimensions,
			dimensions => {
				if (dimensions.width > 0 && dimensions.height > 0) {
					node.position = {
						x: node.position.x - node.dimensions.width / 2,
						y: node.position.y - node.dimensions.height / 2
					};
					stop();
					store.ref_history.commit();
				}
			},
			{ deep: true, flush: "post" }
		);
	});
}

function onDragStart(event) {
	if (event.dataTransfer) {
		event.dataTransfer.effectAllowed = "move";
	}
}

onPaneReady(() => fitView({ padding: 0.4 }));
onMounted(() => store.fetch());
</script>

<template>
	<div class="workflow-container" @drop="onDrop">
		<VueFlow v-model="store.workflow.elements" connection-mode="loose" @dragover="onDragOver">
			<Background pattern-color="#aaa" gap="10" />
			<Panel :position="PanelPosition.TopRight">
				<div class="empty-state">
					<div class="btn btn-md drag-handle" :draggable="true" @dragstart="onDragStart">
						Drag to add state
					</div>
				</div>
			</Panel>
			<Panel :position="PanelPosition.BottomLeft">
				<button class="btn btn-sm btn-default mr-2" @click="zoomIn">+</button>
				<button class="btn btn-sm btn-default mr-2" @click="zoomOut">-</button>
				<button class="btn btn-sm btn-default" @click="fitView({ padding: 0.4 })">
					Fit
				</button>
			</Panel>
			<template #node-state="node">
				<StateNode :node="node" />
			</template>
			<template #node-action="node">
				<ActionNode :node="node" />
			</template>
			<template #edge-transition="props">
				<TransitionEdge v-bind="props" />
			</template>
			<template #connection-line="props">
				<ConnectionLine v-bind="props" />
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

.drag-handle {
	background-color: var(--fg-color);
	cursor: grab !important;
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

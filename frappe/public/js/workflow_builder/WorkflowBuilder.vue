<script setup>
import { VueFlow, useVueFlow, Panel, PanelPosition } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import TransitionEdge from "./components/TransitionEdge.vue";
import StateNode from "./components/StateNode.vue";
import ActionNode from "./components/ActionNode.vue";
import ConnectionLine from "./components/ConnectionLine.vue";
import Sidebar from "./components/Sidebar.vue";
import { useStore } from "./store";
import { validate_transitions } from "./utils";
import { ref, computed, nextTick, onMounted, watch } from "vue";
import { onClickOutside, useMagicKeys, whenever, useActiveElement } from "@vueuse/core";

let store = useStore();

const {
	nodes,
	getEdges,
	getSelectedNodes,
	findNode,
	onNodeDragStop,
	onConnect,
	onEdgeUpdate,
	onEdgeUpdateEnd,
	addNodes,
	addEdges,
	setEdges,
	updateEdge,
	removeNodes,
	endConnection,
	onPaneReady,
	fitView,
	zoomIn,
	zoomOut,
	project,
	vueFlowRef,
} = useVueFlow();

let main = ref(null);
onClickOutside(main, loose_focus);

// cmd/ctrl + s to save the form
const { meta_s, ctrl_s, Backspace, meta_backspace, ctrl_backspace } = useMagicKeys();
whenever(
	() => meta_s.value || ctrl_s.value,
	() => {
		store.save_changes();
	}
);

const activeElement = useActiveElement();
const notUsingInput = computed(
	() => activeElement.value?.tagName !== "INPUT" && activeElement.value?.tagName !== "TEXTAREA"
);

whenever(
	() => Backspace.value || meta_backspace.value || ctrl_backspace.value,
	() => {
		if (meta_backspace.value || ctrl_backspace.value) return;
		if (store.workflow.selected) {
			if (
				notUsingInput.value &&
				(store.workflow.selected.type === "state" ||
					store.workflow.selected.type === "action")
			) {
				removeNodes([store.workflow.selected.id]);
				if (store.workflow.selected.data?.state) {
					let connected_nodes = [];
					connected_nodes = nodes.value
						.filter(
							(node) =>
								node.data.from_id == store.workflow.selected.id ||
								node.data.to_id == store.workflow.selected.id
						)
						.map((node) => node.id);
					removeNodes(connected_nodes);
				}
				store.workflow.selected = null;
				nextTick(() => store.ref_history.commit());
			}
		}
	}
);

onNodeDragStop(() => {
	nextTick(() => store.ref_history.commit());
});

onConnect((edge) => {
	let source_node = findNode(edge.source);
	let target_node = findNode(edge.target);

	let error = validate_transitions(source_node.data, target_node.data);
	if (error) {
		endConnection();
		nextTick(() =>
			frappe.throw({
				title: "Invalid Transition",
				message: error,
			})
		);
		return;
	}

	let source_center = {
		x: source_node.position.x + source_node.dimensions.width / 2,
		y: source_node.position.y + source_node.dimensions.height / 2,
	};

	let target_center = {
		x: target_node.position.x + target_node.dimensions.width / 2,
		y: target_node.position.y + target_node.dimensions.height / 2,
	};

	let center_x = (source_center.x + target_center.x) / 2;
	let center_y = source_center.y;

	let action_ids = nodes.value
		.filter((node) => node.type == "action")
		.map((node) => parseInt(node.id.replace("action-", "")));
	let action_id = action_ids.length ? (Math.max(...action_ids) + 1).toString() : "1";

	const action_node = {
		id: "action-" + action_id,
		type: "action",
		position: { x: center_x, y: center_y },
		selected: true,
		data: {
			action: "",
			allowed: "All",
			allow_self_approval: 1,
			from: source_node.data.state,
			to: target_node.data.state,
			from_id: source_node.id,
			to_id: target_node.id,
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
		animated: true,
	};
	let state_edge = {
		source: action_node.id,
		sourceHandle: "right",
		target: edge.target,
		targetHandle: edge.targetHandle,
		type: "transition",
		updatable: true,
		animated: true,
	};
	addEdges([action_edge, state_edge]);

	nextTick(() => {
		const node = findNode(action_node.id);
		const stop = watch(
			() => node.dimensions,
			(dimensions) => {
				if (dimensions.width > 0 && dimensions.height > 0) {
					node.position = {
						x: node.position.x - node.dimensions.width / 2,
						y: node.position.y - node.dimensions.height / 2,
					};
					stop();
					node.selected = true;
					store.workflow.selected = node;
					store.ref_history.commit();
				}
			},
			{ deep: true, flush: "post" }
		);
	});
});

onEdgeUpdateEnd(({ edge }) => {
	getSelectedNodes.value?.forEach((node) => (node.selected = false));
	if (edge.source.startsWith("action-")) {
		setTimeout(() => (findNode(edge.source).selected = true));
	} else if (edge.target.startsWith("action-")) {
		setTimeout(() => (findNode(edge.target).selected = true));
	}
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

	getSelectedNodes.value?.forEach((node) => (node.selected = false));

	const position = project({
		x: event.clientX - left,
		y: event.clientY - top,
	});

	let state_ids = nodes.value.filter((node) => node.type == "state").map((node) => node.id);
	let state_id = state_ids.length ? (Math.max(...state_ids) + 1).toString() : "1";
	const new_state = {
		id: state_id,
		type: "state",
		position,
		selected: true,
		data: {
			state: "",
			doc_status: "Draft",
			allow_edit: "All",
		},
	};

	addNodes([new_state]);

	nextTick(() => {
		const node = findNode(new_state.id);
		const stop = watch(
			() => node.dimensions,
			(dimensions) => {
				if (dimensions.width > 0 && dimensions.height > 0) {
					node.position = {
						x: node.position.x - node.dimensions.width / 2,
						y: node.position.y - node.dimensions.height / 2,
					};
					stop();
					store.workflow.selected = node;
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
	loose_focus();
}

function loose_focus() {
	if (store.workflow.selected) {
		getSelectedNodes.value?.forEach((node) => (node.selected = false));
		store.workflow.selected = null;
		store.ref_history.commit();
	}
}

onPaneReady(() => fitView());
onMounted(() => store.fetch());
</script>

<template>
	<div class="main" ref="main">
		<div class="sidebar-container" @click.stop>
			<Sidebar />
		</div>
		<div class="workflow-container" @drop="onDrop" @click.stop="loose_focus">
			<VueFlow
				v-model="store.workflow.elements"
				connection-mode="loose"
				@dragover="onDragOver"
				:delete-key-code="null"
			>
				<Background pattern-color="#aaa" gap="10" />
				<Panel :position="PanelPosition.TopRight">
					<div class="empty-state">
						<div
							class="btn btn-md drag-handle"
							:draggable="true"
							@dragstart="onDragStart"
						>
							{{ __("Drag to add state") }}
						</div>
					</div>
				</Panel>
				<Panel :position="PanelPosition.BottomLeft">
					<button class="btn btn-sm btn-default mr-2" @click="zoomIn">+</button>
					<button class="btn btn-sm btn-default mr-2" @click="zoomOut">-</button>
					<button class="btn btn-sm btn-default" @click="fitView()">
						{{ __("Fit") }}
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
	</div>
</template>

<style lang="scss" scoped>
@import "@vue-flow/core/dist/style.css";
@import "@vue-flow/core/dist/theme-default.css";

.main {
	display: flex;
	flex-direction: row;
	height: calc(100vh - var(--navbar-height) - var(--page-head-height) - 65px);

	&.resizing {
		user-select: none;
		cursor: col-resize;
	}

	.sidebar-container {
		position: relative;
		height: 100%;
		margin-right: 10px;
		border-radius: var(--border-radius-lg);
		border: 1px solid var(--border-color);
		background-color: var(--fg-color);
	}
}
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

<script setup>
import { Handle, useVueFlow } from "@vue-flow/core";
import { watch, computed, ref } from "vue";
import { useStore } from "../store";

const props = defineProps({
	node: {
		type: Object,
		required: true,
	},
});

const isValidConnection = ({ source, target, sourceHandle }) => {
	// Allow dragging from the condition diamond to a State node for the false_state transition
	if (
		source.startsWith("action-") &&
		sourceHandle === "false_state" &&
		!target.startsWith("action-")
	) {
		return true;
	}

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
const { edges, findNode, getNodes } = useVueFlow();
const is_dragover = ref(false);

function onDropZoneDragEnter(event) {
	event.preventDefault();
	is_dragover.value = true;
}

function onDropZoneDragLeave() {
	is_dragover.value = false;
}

async function onDropZoneDrop(event) {
	is_dragover.value = false;
	onDrop(event);
}

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
		if (store.ref_history) {
			store.ref_history.commit();
		}
	},
	{ deep: true }
);

function onDragOver(event) {
	event.preventDefault();
	event.stopPropagation(); // Stop bubbling
	event.dataTransfer.dropEffect = "move";
}

async function onDrop(event) {
	event.stopPropagation(); // Stop bubbling to canvas
	const item_type = event.dataTransfer.getData("item_type");
	const item_name = event.dataTransfer.getData("item_name");

	if (item_type === "transition_task" && item_name) {
		// "transition_task" refers to the dropped Task name
		// We need to link this task to the current Transition (Action Node)
		try {
			await store.add_task_to_transition(props.node, item_name);
			frappe.show_alert({
				message: __("Task '{0}' added to transition", [item_name]),
				indicator: "green",
			});
		} catch (e) {
			console.error(e);
		}
	}
}

function onTaskDragStart(event, index) {
	console.log("Drag Start", index);
	event.dataTransfer.effectAllowed = "move";
	event.dataTransfer.dropEffect = "move";
	event.dataTransfer.setData("type", "sort_task");
	event.dataTransfer.setData("from_index", index);
}

function onTaskDragOver(event) {
	if (event.dataTransfer.types.includes("type") || true) {
		// simplified check
		event.preventDefault(); // allow drop
		event.dataTransfer.dropEffect = "move";
	}
}

async function onTaskDrop(event, to_index) {
	const type = event.dataTransfer.getData("type");
	if (type === "sort_task") {
		const from_index = parseInt(event.dataTransfer.getData("from_index"));
		if (from_index !== to_index) {
			await store.move_task(props.node, from_index, to_index);
		}
	}
}

async function removeTask(task) {
	console.log("Removing task:", task.task);
	try {
		await store.remove_task_from_transition(props.node, task);
	} catch (e) {
		console.error(e);
	}
}
</script>

<template>
	<div
		class="node"
		tabindex="0"
		@click.stop="
			() => {
				store.focus_condition = false;
				store.workflow.selected = node;
			}
		"
		@drop.stop="onDrop"
		@dragover.stop="onDragOver"
	>
		<div v-if="label" class="node-label">{{ __(label) }}</div>
		<div v-else class="node-placeholder text-muted">{{ __("No Label") }}</div>

		<!-- Display added tasks -->
		<div v-if="node.data && node.data.tasks && node.data.tasks.length" class="tasks-container">
			<div
				v-for="(task, index) in node.data.tasks"
				:key="task.task"
				class="task-badge"
				draggable="true"
				@dragstart.stop="(e) => onTaskDragStart(e, index)"
				@drop.stop="(e) => onTaskDrop(e, index)"
				@dragover.stop="(e) => onTaskDragOver(e)"
			>
				<div
					class="flex items-center justify-between"
					@click.stop="
						() => {
							store.workflow.selected.selected_task = task;
							store.workflow.selected.selected_task_index = index;
						}
					"
				>
					<span>{{ task.link || task.script_name || task.task }}</span>
					<div class="remove-icon" @click.stop="removeTask(task)" title="Remove Task">
						<svg
							width="12"
							height="12"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
						>
							<line x1="18" y1="6" x2="6" y2="18"></line>
							<line x1="6" y1="6" x2="18" y2="18"></line>
						</svg>
					</div>
				</div>
			</div>
		</div>

		<!-- Drop zone skeleton shown when dragging a task from sidebar -->
		<div
			v-if="store.is_dragging_task"
			class="task-drop-zone"
			:class="{ 'drag-over': is_dragover }"
			@dragenter.stop="onDropZoneDragEnter"
			@dragleave.stop="onDropZoneDragLeave"
			@dragover.stop="onDragOver"
			@drop.stop="onDropZoneDrop"
		>
			<span class="drop-zone-text">{{ __("Drop task here") }}</span>
		</div>

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

		<!-- DMN Diamond Condition Handle -->
		<div
			class="condition-diamond-click"
			@click.stop="
				() => {
					store.focus_condition = true;
					store.workflow.selected = node;
				}
			"
		/>
		<Handle
			class="condition-diamond-handle"
			:class="{ 'has-condition': !!node.data?.condition }"
			type="source"
			position="bottom"
			id="false_state"
			:isValidConnection="isValidConnection"
			@click.stop="store.workflow.selected = node"
			title="Configure Condition (Drag to state for False Transition)"
		>
			<svg
				v-if="!node.data?.condition"
				width="12"
				height="12"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<line x1="12" y1="5" x2="12" y2="19"></line>
				<line x1="5" y1="12" x2="19" y2="12"></line>
			</svg>
			<svg
				v-else
				width="12"
				height="12"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2.5"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<line x1="18" y1="6" x2="6" y2="18"></line>
				<line x1="6" y1="6" x2="18" y2="18"></line>
			</svg>
		</Handle>
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
	pointer-events: all !important;
	z-index: 10;
}

.vue-flow__node.selected .node {
	outline: 1.5px solid var(--primary);
	outline-offset: 2px;
}

.tasks-container {
	margin-top: 8px;
	padding-top: 8px;
	border-top: 1px solid rgba(0, 0, 0, 0.1);
	display: flex;
	flex-direction: column;
	gap: 4px;
	padding-bottom: 8px; /* Room for the diamond */
}

.condition-diamond-handle {
	position: absolute;
	bottom: -10px;
	left: 50%;
	transform: translateX(-50%) rotate(45deg);
	width: 18px;
	height: 18px;
	background-color: var(--fg-color);
	border: 1.5px solid var(--gray-600);
	border-radius: 3px;
	cursor: pointer;
	z-index: 20;
	display: flex;
	align-items: center;
	justify-content: center;
	transition: all 0.2s ease;

	svg {
		transform: rotate(-45deg); /* Keep icon straight */
		color: var(--gray-600);
		opacity: 0;
		transition: opacity 0.2s ease;
	}

	&:hover {
		border-color: var(--primary);
		svg {
			opacity: 1;
			color: var(--primary);
		}
	}

	&.has-condition {
		svg {
			opacity: 1;
		}
	}
}

.condition-diamond-click {
	position: absolute;
	bottom: -14px;
	left: 50%;
	transform: translateX(-50%);
	width: 26px;
	height: 26px;
	z-index: 25;
	cursor: pointer;
}

.task-badge {
	background: #ffffff !important;
	color: #1f272e !important;
	font-size: 11px;
	padding: 4px 8px;
	border-radius: 4px;
	border: 1px solid #d1d8dd;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	font-weight: 500;
	margin-bottom: 2px;
	display: block;
	width: 100%;
	box-sizing: border-box;
	text-align: left;
	cursor: pointer; /* Changed from grab to pointer for clickable effect */

	&:hover {
		border-color: var(--primary);
	}

	&:active {
		cursor: grabbing;
	}
}

.flex {
	display: flex;
}

.items-center {
	align-items: center;
}

.justify-between {
	justify-content: space-between;
}

.remove-icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 16px;
	height: 16px;
	border-radius: 50%;
	cursor: pointer;
	color: #8d99a6;
	margin-left: 4px;

	&:hover {
		background-color: #f0f4f8;
		color: #000000;
	}
}

.task-drop-zone {
	margin-top: 8px;
	padding: 10px;
	border: 2px dashed var(--gray-400);
	border-radius: 4px;
	text-align: center;
	transition: all 0.15s ease;
	min-width: 120px;

	.drop-zone-text {
		font-size: 11px;
		color: var(--gray-300);
		font-weight: 500;
	}

	&.drag-over {
		border-color: var(--primary);
		background-color: rgba(var(--primary-rgb), 0.08);

		.drop-zone-text {
			color: var(--fg-color);
		}
	}
}
</style>
```

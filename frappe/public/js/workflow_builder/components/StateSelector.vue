<script setup>
import { ref, onMounted, computed } from "vue";
import { useStore } from "../store";

const store = useStore();
const states = ref([]);
const tasks = ref([]);
const resizing = ref(false);
const sidebar_width = ref(240);
const isLoading = ref(true);

const showTasks = computed(() => {
	return store.workflow.selected && store.workflow.selected.type === "action";
});

function onDragStart(event, item, type) {
	if (event.dataTransfer) {
		event.dataTransfer.effectAllowed = "move";
		event.dataTransfer.setData("item_name", item.name);
		event.dataTransfer.setData("item_type", type);

		// Legacy support for main canvas state dropping
		if (type === "state") {
			event.dataTransfer.setData("state", item.name);
			event.dataTransfer.setData("is_new_state", true);
		}
	}
}

const task_icon_map = store.task_icons;

function getTaskIcon(taskName) {
	let iconName = task_icon_map[taskName] || "clipboard";
	return frappe.utils.icon(iconName, "sm");
}

async function fetch_states() {
	isLoading.value = true;
	try {
		states.value = await frappe.db.get_list("Workflow State", {
			fields: ["name"],
			limit: 0,
			order_by: "name asc",
		});
	} catch (e) {
		console.error("Failed to fetch Workflow States:", e);
	} finally {
		isLoading.value = false;
	}
}

async function fetch_tasks() {
	isLoading.value = true;
	try {
		const response = await frappe.call({
			method: "frappe.workflow.doctype.workflow.workflow.get_workflow_methods",
			type: "GET",
		});
		// The API returns a list of items where each item is a dict with 'label' and 'value'
		// or potentially just a list of strings depending on implementation.
		// Let's assume standard frappe.call behavior returns 'message'

		// Based on common Frappe patterns for such named methods:
		// usually returns list of dicts like [{label: 'x', value: 'x'}] or just strings.
		// We will map it to objects with 'name' property to match the existing template.

		let data = response.message || [];

		tasks.value = data.map((d) => {
			let name = typeof d === "string" ? d : d.name || d.value || d.label;
			let icon = typeof d === "object" && d.icon ? d.icon : "";
			if (icon) store.task_icons[name] = icon;
			return { name };
		});
	} catch (e) {
		console.error("Failed to fetch Workflow Tasks:", e);
		tasks.value = [];
	} finally {
		isLoading.value = false;
	}
}

function start_resize() {
	$(document).on("mousemove", resize);
	$(document).on("mouseup", stop_resize);
}

function resize(e) {
	resizing.value = true;
	const new_width = window.innerWidth - e.clientX;
	if (new_width >= 200 && new_width <= 400) {
		sidebar_width.value = new_width;
	}
}

function stop_resize() {
	resizing.value = false;
	$(document).off("mousemove", resize);
	$(document).off("mouseup", stop_resize);
}

onMounted(() => {
	fetch_states();
	fetch_tasks();
});
</script>

<template>
	<div class="state-sidebar" :style="{ width: `${sidebar_width}px` }">
		<div class="resizer" @mousedown="start_resize" :class="{ active: resizing }"></div>

		<template v-if="!showTasks">
			<div class="header p-3 border-b shrink-0">
				<h5 class="font-bold text-base mb-0">{{ __("States") }}</h5>
				<p class="text-xs text-muted mt-1 mb-0">
					{{ __("Drag to add states to workflow") }}
				</p>
			</div>

			<div class="states-list p-2 overflow-y-auto">
				<div v-if="isLoading" class="p-4 text-center text-muted">
					{{ __("Loading...") }}
				</div>

				<template v-else>
					<div class="sidebar-list-container">
						<div
							v-for="state in states"
							:key="state.name"
							class="sidebar-card"
							draggable="true"
							@dragstart="(e) => onDragStart(e, state, 'state')"
						>
							<div class="card-name">
								{{ state.name }}
							</div>
						</div>
					</div>

					<div v-if="states.length === 0" class="p-4 text-center text-muted">
						{{ __("No states found") }}
					</div>
				</template>
			</div>
		</template>
		<template v-if="showTasks">
			<div class="header p-3 border-b shrink-0">
				<h5 class="font-bold text-base mb-0">{{ __("Tasks") }}</h5>
				<p class="text-xs text-muted mt-1 mb-0">
					{{ __("Drag and drop tasks on action node to add to workflow") }}
				</p>
			</div>
			<div class="states-list p-2 overflow-y-auto">
				<div v-if="isLoading" class="p-4 text-center text-muted">
					{{ __("Loading...") }}
				</div>

				<template v-else>
					<div class="sidebar-list-container">
						<div
							v-for="task in tasks"
							:key="task.name"
							class="sidebar-card"
							draggable="true"
							@dragstart="(e) => onDragStart(e, task, 'transition_task')"
						>
							<div class="card-icon" v-html="getTaskIcon(task.name)"></div>
							<div class="card-name">
								{{ task.name }}
							</div>
						</div>
					</div>
				</template>
			</div>
		</template>
	</div>
</template>

<style lang="scss" scoped>
.state-sidebar {
	height: 100%;
	background-color: var(--fg-color);
	border-radius: var(--border-radius-lg);
	border: 1px solid var(--border-color);
	display: flex;
	flex-direction: column;
	position: relative;
	margin-left: 10px;
	overflow: hidden;
}

.resizer {
	position: absolute;
	left: -5px;
	top: 0;
	width: 5px;
	height: 100%;
	cursor: col-resize;
	z-index: 10;

	&:hover,
	&.active {
		background-color: var(--primary);
		opacity: 0.5;
	}
}

.states-list {
	flex: 1;
	overflow-y: auto;
	min-height: 0;
}

.p-3 {
	padding: 0.75rem;
}

.mb-0 {
	margin-bottom: 0;
}

.mt-1 {
	margin-top: 0.25rem;
}

.text-base {
	font-size: var(--text-base);
}

.text-muted {
	color: var(--text-muted);
}

.p-2 {
	padding: 0.5rem;
}

.p-4 {
	padding: 1rem;
}

.w-full {
	width: 100%;
}
.border-b {
	border-bottom: 1px solid var(--border-color);
}

/* Common List Styles */
.sidebar-list-container {
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 4px;
}

.sidebar-card {
	display: flex;
	align-items: center;
	width: 100%;
	padding: 8px 10px;
	background-color: var(--bg-light-gray);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-md);
	cursor: grab;
	transition: all 0.2s ease;
	text-align: left;

	&:hover {
		background-color: var(--bg-gray);
		border-color: var(--primary);
		transform: translateX(2px);
		box-shadow: var(--shadow-sm);
	}

	.card-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		margin-right: 10px;
		color: var(--text-muted);
		flex-shrink: 0;
	}

	&:hover .card-icon {
		color: var(--primary);
	}

	.card-name {
		font-size: var(--text-sm);
		font-weight: 500;
		color: var(--text-color);
		line-height: 1.4;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
}
</style>

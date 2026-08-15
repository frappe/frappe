<template>
	<VueFlow
		:id="flowId"
		ref="flowRoot"
		:nodes="flowNodes"
		:edges="edges"
		class="automation-canvas"
		:fit-view-options="fitViewOptions"
		:nodes-draggable="!readonly"
		:nodes-connectable="false"
		:elements-selectable="!readonly"
		:pan-on-drag="true"
		@nodes-initialized="refitFlow"
		@node-drag-stop="rememberPosition"
		@node-click="selectNode($event.node.id)"
		@pane-click="selectStartNode"
	>
		<Background pattern-color="#5e5e5e" :gap="18" :size="1" />
		<Panel position="bottom-left">
			<div
				class="flex items-center gap-0.5 rounded-[10px] border border-outline-gray-2 bg-surface-gray-1 p-1 shadow-md"
			>
				<Button
					icon="lucide-minus"
					variant="ghost"
					:aria-label="translate('Zoom out')"
					@click="zoomOut({ duration: 150 })"
				/>
				<span
					class="min-w-11 text-center text-xs font-medium tabular-nums text-ink-gray-7"
				>
					{{ zoomPercent }}
				</span>
				<Button
					icon="lucide-plus"
					variant="ghost"
					:aria-label="translate('Zoom in')"
					@click="zoomIn({ duration: 150 })"
				/>
				<span class="mx-0.5 h-4 w-px bg-outline-gray-2" />
				<Button
					icon="lucide-maximize"
					variant="ghost"
					:aria-label="translate('Fit entire flow')"
					@click="refitFlow"
				/>
			</div>
		</Panel>
		<template #node-automation="{ id, data }">
			<div class="relative">
				<div
					class="absolute bottom-[calc(100%)] left-2 rounded-sm border border-b-0 px-1.5 py-0.5 text-[10px] font-medium"
					:class="kickerClasses(id)"
				>
					{{ data.kicker }}
				</div>
				<div class="flex items-center">
					<Combobox
						:options="startOptions"
						:disabled="!picksStart(data)"
						trigger="button"
						:placeholder="translate('Search triggers')"
						@update:model-value="emit('pick-start', $event)"
					>
						<template #item-prefix />
						<template #item-label="{ item }">
							<AutomationCanvasOption :item="item" />
						</template>
						<template #trigger>
							<div
								class="relative flex w-[180px] items-center gap-2.5 rounded-[10px] border px-3 py-2.5 shadow-sm transition-colors"
								:class="nodeClasses(id, data)"
								:tabindex="readonly ? -1 : 0"
								:role="readonly ? undefined : 'button'"
								:aria-label="`${data.kicker}: ${data.label}`"
								@click.stop="selectNode(id)"
								@keydown.enter="selectNode(id)"
								@keydown.space.prevent="selectNode(id)"
							>
								<Handle
									v-if="!data.start"
									type="target"
									:position="Position.Left"
								/>
								<div
									v-if="!data.empty"
									class="flex size-8 shrink-0 items-center justify-center rounded-[7px]"
									:class="iconTone(data).chip"
								>
									<Icon
										v-if="data.icon"
										:name="data.icon"
										class="size-[18px]"
										:class="iconTone(data).icon"
									/>
								</div>
								<div class="min-w-0 flex-1" :class="{ 'text-center': data.empty }">
									<div class="truncate text-base-medium text-ink-gray-8">
										{{ data.label }}
									</div>
									<div
										v-if="data.detail"
										class="truncate text-p-sm text-ink-gray-5"
									>
										{{ data.detail }}
									</div>
								</div>
								<Icon
									v-if="data.error"
									name="lucide-circle-alert"
									class="size-4 shrink-0 text-ink-red-4"
								/>
								<Handle type="source" :position="Position.Right" />
							</div>
						</template>
					</Combobox>
					<div v-if="showAdd(data)" class="nodrag flex items-center" @click.stop>
						<span class="h-px w-5 bg-outline-gray-3" />
						<Combobox
							:options="blockOptions"
							trigger="button"
							side="right"
							:placeholder="translate('Search blocks')"
							@update:model-value="addNode(id, data, null, $event)"
						>
							<template #item-prefix />
							<template #item-label="{ item }">
								<AutomationCanvasOption :item="item" />
							</template>
							<template #trigger>
								<Button icon="lucide-plus" :aria-label="translate('Add block')" />
							</template>
						</Combobox>
					</div>
				</div>
				<div
					v-if="data.arms?.length && !readonly"
					class="nodrag absolute left-[calc(100%+12px)] top-1/2 flex -translate-y-1/2 flex-col gap-1.5"
					@click.stop
				>
					<Combobox
						v-for="arm in data.arms"
						:key="arm.key"
						:options="blockOptions"
						trigger="button"
						side="right"
						:placeholder="translate('Search blocks')"
						@update:model-value="addNode(id, data, arm.key, $event)"
					>
						<template #item-prefix />
						<template #item-label="{ item }">
							<AutomationCanvasOption :item="item" />
						</template>
						<template #trigger>
							<Button icon-left="lucide-plus" size="sm">{{ arm.label }}</Button>
						</template>
					</Combobox>
				</div>
			</div>
		</template>
	</VueFlow>
</template>

<script setup lang="ts">
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import { Background } from "@vue-flow/background";
import { Handle, Panel, Position, VueFlow, useVueFlow } from "@vue-flow/core";
import { Button, Combobox, Icon } from "frappe-ui";
import {
	computed,
	getCurrentInstance,
	nextTick,
	onBeforeUnmount,
	onMounted,
	ref,
	watch,
} from "vue";
import AutomationCanvasOption from "./AutomationCanvasOption.vue";
import type {
	AutomationCanvasEmits,
	AutomationCanvasExposed,
	AutomationCanvasNodeData,
	AutomationCanvasProps,
} from "./types";

const props = withDefaults(defineProps<AutomationCanvasProps>(), {
	selectedId: "",
	startOptions: () => [],
	blockOptions: () => [],
	readonly: false,
});
const emit = defineEmits<AutomationCanvasEmits>();
const flowId = `automation-canvas-${getCurrentInstance()?.uid ?? "root"}`;
const flowRoot = ref<InstanceType<typeof VueFlow> | null>(null);
const moved = ref<Record<string, { x: number; y: number }>>({});
const fitViewOptions = { padding: 0.05, minZoom: 0.3, maxZoom: 1, duration: 200 };
const { fitView: fitVueFlow, setViewport, viewport, zoomIn, zoomOut } = useVueFlow(flowId);
let resizeObserver: ResizeObserver | undefined;

const flowNodes = computed(() =>
	props.nodes.map((node) => ({
		...node,
		type: "automation",
		position: moved.value[node.id] || node.position,
	}))
);
const zoomPercent = computed(() => `${Math.round(viewport.value.zoom * 100)}%`);
const startNodeId = computed(() => props.nodes.find((node) => node.data.start)?.id);
const translate = (globalThis as any).__ || ((message: string) => message);

watch(
	[() => props.nodes.map((node) => node.id).join("|"), () => props.nodes[0]?.data.empty],
	refitFlow,
	{ flush: "post" }
);
onMounted(observeSize);
onBeforeUnmount(() => resizeObserver?.disconnect());

async function refitFlow(): Promise<void> {
	if (!props.nodes.length) return;
	await nextTick();
	await nextFrame();
	await fitVueFlow({ ...fitViewOptions, duration: 0 });
	await (props.nodes[0]?.data.empty ? centerEmptyFlow() : alignFlowLeft());
}

function nextFrame() {
	return new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
}

function alignFlowLeft() {
	const leftmost = Math.min(...flowNodes.value.map((node) => node.position.x));
	return setViewport(
		{ ...viewport.value, x: 48 - leftmost * viewport.value.zoom },
		{ duration: fitViewOptions.duration }
	);
}

function centerEmptyFlow() {
	const root = canvasRoot();
	const canvas = root?.getBoundingClientRect();
	const node = root?.querySelector(".vue-flow__node")?.getBoundingClientRect();
	if (!canvas || !node) return;
	const offset = canvas.left + canvas.width / 2 - node.left - node.width / 2;
	return setViewport({ ...viewport.value, x: viewport.value.x + offset }, { duration: 200 });
}

function canvasRoot() {
	const root = flowRoot.value as any;
	return (root?.$el || root) as HTMLElement | undefined;
}

function observeSize() {
	const root = canvasRoot();
	if (!root || typeof ResizeObserver === "undefined") return;
	resizeObserver = new ResizeObserver(() => void refitFlow());
	resizeObserver.observe(root);
}

function rememberPosition({ node }: { node: { id: string; position: { x: number; y: number } } }) {
	moved.value = { ...moved.value, [node.id]: { ...node.position } };
}

function selectNode(id: string) {
	if (!props.readonly) emit("select", id);
}

function selectStartNode() {
	if (startNodeId.value) selectNode(startNodeId.value);
}

function picksStart(data: AutomationCanvasNodeData) {
	return Boolean(data.empty) && !props.readonly;
}

function isSelected(id: string) {
	return !props.readonly && props.selectedId === id;
}

function kickerClasses(id: string) {
	return isSelected(id)
		? "bg-surface-blue-3 text-ink-blue-7 border-outline-blue-5"
		: "bg-surface-gray-2 text-ink-gray-8 border-outline-gray-2";
}

function nodeClasses(id: string, data: AutomationCanvasNodeData) {
	return [picksStart(data) ? "nodrag" : "", nodeSurface(id, data)];
}

function nodeSurface(id: string, data: AutomationCanvasNodeData) {
	if (data.empty) return "border-dashed border-outline-gray-3 bg-surface-base shadow-none";
	if (data.error) return "border-outline-red-2 bg-surface-modal";
	if (isSelected(id)) return "border-outline-blue-5 bg-surface-base";
	return "border-outline-gray-2 bg-surface-base hover:border-outline-blue-5 hover:bg-surface-hover";
}

function iconTone(data: AutomationCanvasNodeData) {
	return ICON_TONES[data.tone || (data.start ? "trigger" : "action")];
}

function showAdd(data: AutomationCanvasNodeData) {
	if (props.readonly || data.branching || data.empty) return false;
	return Boolean(data.terminal);
}

function addNode(
	id: string,
	data: AutomationCanvasNodeData,
	branch: string | null,
	value: string
) {
	emit("add-node", { afterId: data.start ? null : id, branch, value });
}

defineExpose<AutomationCanvasExposed>({ fitView: refitFlow });

const ICON_TONES = {
	trigger: { chip: "bg-surface-blue-2 border border-outline-blue-4", icon: "text-ink-blue-7" },
	action: {
		chip: "bg-surface-violet-2 border border-outline-violet-4",
		icon: "text-ink-violet-7",
	},
	wait: { chip: "bg-surface-amber-2 border border-outline-amber-4", icon: "text-ink-amber-7" },
	event: {
		chip: "bg-surface-purple-2 border border-outline-purple-4",
		icon: "text-ink-purple-7",
	},
	condition: {
		chip: "bg-surface-orange-2 border border-outline-orange-4",
		icon: "text-ink-orange-7",
	},
};
</script>

<style scoped>
.automation-canvas {
	height: 100%;
	width: 100%;
	background: var(--surface-base);
}

.automation-canvas :deep(.vue-flow__pane) {
	cursor: grab;
}

.automation-canvas :deep(.vue-flow__pane:active) {
	cursor: grabbing;
}

.automation-canvas :deep(.vue-flow__node) {
	cursor: grab;
}

.automation-canvas :deep(.vue-flow__node.dragging) {
	cursor: grabbing;
}
</style>

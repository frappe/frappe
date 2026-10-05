<template>
	<VueFlow
		:id="flowId"
		ref="flowRoot"
		:nodes="flowNodes"
		:edges="flowEdges"
		class="automation-canvas"
		:fit-view-options="fitViewOptions"
		:nodes-draggable="!readonly"
		:nodes-connectable="false"
		:elements-selectable="!readonly"
		:pan-on-drag="true"
		@nodes-initialized="() => refitFlow()"
		@node-drag-stop="rememberPosition"
		@node-click="selectNode($event.node.id)"
		@pane-click="selectStartNode"
	>
		<Background color="var(--surface-gray-4)" :gap="20" :size="3" />
		<Panel position="bottom-center">
			<div
				class="flex items-center gap-0.5 rounded-[10px] border border-outline-gray-2 bg-surface-gray-1 p-1 shadow-md"
			>
				<template v-if="!readonly">
					<Button
						icon="lucide-undo-2"
						variant="ghost"
						:disabled="!canUndo"
						:aria-label="translate('Undo')"
						@click="emit('undo')"
					/>
					<Button
						icon="lucide-redo-2"
						variant="ghost"
						:disabled="!canRedo"
						:aria-label="translate('Redo')"
						@click="emit('redo')"
					/>
					<span
						class="mx-1 h-5 w-px border-l border-outline-gray-2"
						aria-hidden="true"
					/>
				</template>
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
				<span class="mx-1 h-5 w-px border-l border-outline-gray-2" aria-hidden="true" />
				<Button
					icon="lucide-maximize"
					variant="ghost"
					:aria-label="translate('Fit entire flow')"
					@click="refitFlow()"
				/>
				<Button
					v-if="canDelete && selectedId && !readonly"
					icon="lucide-trash-2"
					variant="ghost"
					class="text-ink-red-5"
					:aria-label="
						selectedId === startNodeId
							? translate('Remove trigger')
							: translate('Remove step')
					"
					@click.stop="emit('request-remove', selectedId)"
				/>
			</div>
		</Panel>
		<template #node-automation="{ id, data }">
			<div class="relative">
				<div class="flex items-center">
					<div class="relative w-[212px] shrink-0">
						<Handle
							v-if="!data.start"
							id="input"
							class="automation-canvas-port"
							type="target"
							:position="Position.Left"
						/>
						<AutomationCanvasPicker
							:options="startOptions"
							:disabled="!picksStart(data)"
							:placeholder="translate('Search triggers')"
							@pick="emit('pick-start', $event)"
						>
							<div
								class="automation-canvas-node relative flex h-[87px] w-[212px] flex-col overflow-hidden rounded-[10px] border bg-surface-base shadow-sm transition-all"
								:class="[
									nodeClasses(id, data),
									{ 'opacity-40': data.dimmed || isFaded(id, data) },
								]"
								:tabindex="readonly ? -1 : 0"
								:role="readonly ? undefined : 'button'"
								:aria-label="`${data.kicker}: ${data.label}`"
								@click.stop="selectNode(id)"
								@keydown.enter.prevent="pressNode"
								@keydown.space.prevent="pressNode"
							>
								<div
									class="flex h-[47px] shrink-0 items-center gap-1.5 border-b border-outline-gray-3 px-2"
								>
									<AutomationCanvasIcon
										v-if="!data.empty"
										:icon="data.icon"
										:tone="data.tone"
									/>
									<div
										class="min-w-0 flex-1 truncate text-base font-medium text-ink-gray-9"
										:class="{ 'text-center': data.empty }"
									>
										{{ data.label }}
									</div>
									<Badge
										v-if="data.forced"
										:label="translate('Forced')"
										theme="amber"
										variant="subtle"
									/>
									<Spinner
										v-if="data.status === 'running'"
										size="sm"
										class="shrink-0 text-ink-gray-7"
									/>
									<Icon
										v-else-if="data.status && RUN_STATES[data.status]"
										:name="RUN_STATES[data.status].icon"
										class="size-4 shrink-0"
										:class="RUN_STATES[data.status].color"
									/>
									<Icon
										v-else-if="data.error"
										name="lucide-circle-alert"
										class="size-4 shrink-0 text-ink-red-3"
									/>
									<Tooltip v-else-if="data.incomplete" :text="data.incomplete">
										<Icon
											name="lucide-triangle-alert"
											class="size-4 shrink-0 text-ink-amber-5"
										/>
									</Tooltip>
								</div>
								<div class="flex min-h-0 flex-1 items-end gap-2 px-2 py-[7px]">
									<div
										class="line-clamp-2 min-w-0 flex-1 text-[10px] leading-3 text-ink-gray-7"
									>
										{{ data.detail }}
									</div>
									<div
										class="shrink-0 text-[10px] font-medium leading-3 text-ink-gray-8"
									>
										{{ data.kicker }}
									</div>
								</div>
							</div>
						</AutomationCanvasPicker>
						<Handle
							v-if="outgoing.has(id)"
							id="output"
							class="automation-canvas-port"
							type="source"
							:position="Position.Right"
						/>
					</div>
					<div
						v-if="showAdd(data)"
						class="automation-canvas-add nodrag flex items-center"
						@click.stop
					>
						<span class="h-px w-5 bg-outline-gray-3" />
						<AutomationCanvasPicker
							:options="blockOptions"
							side="right"
							:placeholder="translate('Search blocks')"
							@pick="addNode(id, data, null, $event)"
						>
							<Button
								icon="lucide-plus"
								variant="ghost"
								:aria-label="translate('Add block')"
							/>
						</AutomationCanvasPicker>
					</div>
				</div>
				<div
					v-if="data.retryArms?.length"
					class="automation-canvas-add nodrag absolute left-0 top-[calc(100%+8px)] flex gap-1.5"
					@click.stop
				>
					<Button
						v-for="arm in data.retryArms"
						:key="arm.key"
						size="sm"
						icon-left="lucide-play"
						@click="emit('run-branch', { nodeId: id, arm })"
					>
						{{ translate("Run {0}", [arm.label]) }}
					</Button>
				</div>
				<div
					v-if="(data.arms?.length || data.canContinue) && !readonly"
					class="automation-canvas-add nodrag absolute left-[calc(100%+12px)] top-1/2 flex -translate-y-1/2 flex-col gap-1.5"
					@click.stop
				>
					<AutomationCanvasPicker
						v-for="arm in data.arms"
						:key="arm.key"
						:options="blockOptions"
						side="right"
						:placeholder="translate('Search blocks')"
						@pick="addNode(id, data, arm.key, $event)"
					>
						<Button
							icon-left="lucide-plus"
							size="sm"
							:class="arm.key === 'Else' ? 'mt-2' : ''"
						>
							{{ arm.label }}
						</Button>
					</AutomationCanvasPicker>
					<AutomationCanvasPicker
						v-if="data.canContinue"
						:options="blockOptions"
						side="right"
						:placeholder="translate('Search blocks')"
						@pick="addNode(id, data, null, $event)"
					>
						<Button icon-left="lucide-plus" size="sm" class="ml-6">
							{{ translate("After branches") }}
						</Button>
					</AutomationCanvasPicker>
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
import { useDebounceFn, useResizeObserver } from "@vueuse/core";
import { Badge, Button, Icon, Spinner, Tooltip } from "frappe-ui";
import { computed, getCurrentInstance, nextTick, ref, watch } from "vue";
import AutomationCanvasIcon from "./AutomationCanvasIcon.vue";
import AutomationCanvasPicker from "./AutomationCanvasPicker.vue";
import type {
	AutomationCanvasEmits,
	AutomationCanvasExposed,
	AutomationCanvasNodeData,
	AutomationCanvasProps,
	AutomationCanvasStatus,
} from "./types";

const props = withDefaults(defineProps<AutomationCanvasProps>(), {
	selectedId: "",
	startOptions: () => [],
	blockOptions: () => [],
	dimUnselected: false,
	canDelete: false,
	canUndo: false,
	canRedo: false,
	readonly: false,
});
const emit = defineEmits<AutomationCanvasEmits>();

const RUN_STATES: Partial<Record<AutomationCanvasStatus, { icon: string; color: string }>> = {
	Success: { icon: "lucide-circle-check", color: "text-ink-green-4" },
	Skipped: { icon: "lucide-circle-minus", color: "text-ink-gray-4" },
	Failed: { icon: "lucide-circle-x", color: "text-ink-red-4" },
	Waiting: { icon: "lucide-clock", color: "text-ink-amber-5" },
};
const EDGE_PADDING = 48;

type Point = { x: number; y: number };

const flowId = `automation-canvas-${getCurrentInstance()?.uid ?? "root"}`;
const flowRoot = ref<InstanceType<typeof VueFlow> | null>(null);
// Where the user dragged each node, kept only while the app still places it where it was.
const moved = ref<Record<string, { from: Point; to: Point }>>({});
const { fitView, setViewport, viewport, zoomIn, zoomOut } = useVueFlow(flowId);

const isBlankFlow = computed(() => props.nodes.length === 1 && props.nodes[0]?.data.empty);
// Fit as tight as the flow allows: a short flow can pass 100%, a long one caps there.
const fitViewOptions = computed(() => ({
	padding: 0.08,
	minZoom: 0.3,
	maxZoom: isBlankFlow.value ? 1.1 : props.nodes.length <= 3 ? 1.25 : 1,
	duration: 200,
}));

const flowNodes = computed(() =>
	props.nodes.map((node) => ({
		...node,
		type: "automation",
		position: draggedPosition(node.id, node.position) || node.position,
	}))
);
const flowEdges = computed(() =>
	props.edges.map((edge) => ({
		type: "bezier",
		sourceHandle: "output",
		targetHandle: "input",
		labelBgPadding: [14, 2] as [number, number],
		labelBgBorderRadius: 6,
		...edge,
		style: { stroke: "#4E4E4E", strokeWidth: 1, ...edge.style },
	}))
);
const outgoing = computed(() => new Set(props.edges.map((edge) => edge.source)));
const zoomPercent = computed(() => `${Math.round(viewport.value.zoom * 100)}%`);
const startNodeId = computed(() => props.nodes.find((node) => node.data.start)?.id);

watch(
	[() => props.nodes.map((node) => node.id).join("|"), () => props.nodes[0]?.data.empty],
	(current, previous) => refitFlow(previous?.[1] === true && current[1] === false),
	{ flush: "post" }
);

// A sliding side panel keeps resizing the pane, so refit once it settles.
const refitAfterResize = useDebounceFn(() => refitFlow(), 80);
useResizeObserver(canvasRoot, ([entry]) => {
	if (entry.contentRect.width) refitAfterResize();
});

function translate(message: string, args: unknown[] = []) {
	const __ = (globalThis as any).__;
	if (__) return __(message, args);
	return message.replace(/\{(\d+)\}/g, (match, index) => String(args[index] ?? match));
}

async function refitFlow(animateLeft = false): Promise<void> {
	if (!props.nodes.length) return;
	await nextTick();
	await nextFrame();
	if (animateLeft) return alignFlowLeft(viewport.value.zoom, fitViewOptions.value.duration);
	await fitView({ ...fitViewOptions.value, duration: 0 });
	if (props.nodes[0]?.data.empty) return centerEmptyFlow();
	await alignFlowLeft();
	await nextFrame();
	await keepAddControlsVisible();
}

function nextFrame() {
	return new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
}

async function alignFlowLeft(zoom = viewport.value.zoom, duration = 0) {
	const leftmost = Math.min(...flowNodes.value.map((node) => node.position.x));
	await setViewport(
		{ ...viewport.value, zoom, x: EDGE_PADDING - leftmost * zoom },
		{ duration }
	);
}

/** fitView only measures node bounds, so the add controls hanging off the last node can
 *  still overflow. Scale down to bring them back rather than panning off the left edge. */
async function keepAddControlsVisible() {
	const root = canvasRoot();
	const controls = root?.querySelectorAll(".automation-canvas-add") || [];
	if (!root || !controls.length) return;
	const canvas = root.getBoundingClientRect();
	const right = Math.max(...[...controls].map((item) => item.getBoundingClientRect().right));
	const used = right - canvas.left - EDGE_PADDING;
	const available = canvas.width - EDGE_PADDING * 2;
	if (used <= available || used <= 0) return;
	const zoom = Math.max(viewport.value.zoom * (available / used), fitViewOptions.value.minZoom);
	await alignFlowLeft(zoom);
}

async function centerEmptyFlow() {
	const root = canvasRoot();
	const node = root?.querySelector(".vue-flow__node")?.getBoundingClientRect();
	if (!root || !node) return;
	const canvas = root.getBoundingClientRect();
	const x = viewport.value.x + canvas.left + canvas.width / 2 - node.left - node.width / 2;
	const y = viewport.value.y + canvas.top + canvas.height * 0.3 - node.top - node.height / 2;
	await setViewport({ ...viewport.value, x, y }, { duration: 0 });
}

function canvasRoot() {
	const root = flowRoot.value as any;
	return (root?.$el || root) as HTMLElement | undefined;
}

function rememberPosition({ node }: { node: { id: string; position: Point } }) {
	const from = props.nodes.find((item) => item.id === node.id)?.position;
	if (from) moved.value = { ...moved.value, [node.id]: { from, to: { ...node.position } } };
}

/** A drag holds until the app moves the node itself, e.g. on undo or a new layout. */
function draggedPosition(id: string, position: Point) {
	const drag = moved.value[id];
	return drag && drag.from.x === position.x && drag.from.y === position.y ? drag.to : null;
}

/** A div with role="button" gets no click from Enter or Space, and the start picker opens on click. */
function pressNode(event: KeyboardEvent) {
	(event.currentTarget as HTMLElement).click();
}

function selectNode(id: string) {
	if (!props.readonly) emit("select", id);
}

function selectStartNode() {
	if (startNodeId.value) selectNode(startNodeId.value);
}

/** Until a trigger is chosen the start node is the picker itself. */
function picksStart(data: AutomationCanvasNodeData) {
	return Boolean(data.empty) && !props.readonly;
}

function isFaded(id: string, data: AutomationCanvasNodeData) {
	if (!props.dimUnselected || data.empty) return false;
	return Boolean(props.selectedId) && props.selectedId !== id;
}

/** `nodrag` because dragging swallows the click that opens the start picker. */
function nodeClasses(id: string, data: AutomationCanvasNodeData) {
	return [picksStart(data) ? "nodrag" : "", nodeSurface(id, data)];
}

// One surface per state: stacked border utilities would let stylesheet order pick the winner.
function nodeSurface(id: string, data: AutomationCanvasNodeData) {
	if (data.empty) return "border-dashed border-outline-gray-3 shadow-none";
	if (data.status === "Failed") return "border-outline-red-2 bg-surface-modal shadow-sm";
	if (data.status === "running") return "border-outline-gray-5 shadow-md";
	if (data.error) return "border-outline-red-2 bg-surface-modal shadow-sm";
	if (!props.readonly && props.selectedId === id) return "border-outline-gray-8 shadow-sm";
	if (data.incomplete) return "border-outline-amber-2 shadow-md hover:border-outline-gray-8";
	return "border-outline-gray-2 shadow-md hover:border-outline-gray-8";
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

defineExpose<AutomationCanvasExposed>({ fitView: () => refitFlow() });
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

.automation-canvas .automation-canvas-node {
	box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.16);
}

/* A faint black shadow reads as nothing on the dark canvas. */
:global([data-theme="dark"] .automation-canvas .automation-canvas-node) {
	box-shadow: 0 2px 6px 0 rgba(0, 0, 0, 0.6);
}

.automation-canvas .automation-canvas-node.shadow-none {
	box-shadow: none;
}

.automation-canvas .automation-canvas-node.shadow-md {
	box-shadow: var(--elevation-md);
}

.automation-canvas :deep(.automation-canvas-port) {
	z-index: 20 !important;
	top: calc(50% + 4px);
	width: 6px !important;
	min-width: 6px !important;
	height: 6px !important;
	min-height: 6px !important;
	border: 0 !important;
	background: var(--ink-gray-5) !important;
	box-shadow: none;
	opacity: 1 !important;
	visibility: visible !important;
}

.automation-canvas :deep(.vue-flow__edge-path) {
	stroke: var(--ink-gray-4);
	stroke-width: 1;
}

.automation-canvas :deep(.vue-flow__edge-textbg) {
	fill: var(--surface-base);
	stroke: var(--outline-gray-2);
	stroke-width: 1px;
}

.automation-canvas :deep(.vue-flow__edge-text) {
	fill: var(--ink-gray-6);
	font-size: 10px;
	font-weight: 500;
}
</style>

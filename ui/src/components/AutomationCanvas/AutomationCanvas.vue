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
		:nodes-focusable="false"
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
				<template v-if="$slots.toolbar">
					<slot name="toolbar" :selectedId="selectedId" />
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
			</div>
		</Panel>
		<template #node-automation="{ id, data }">
			<div class="relative">
				<div class="flex items-center">
					<div :class="blockClasses(id, data)" :style="hueVars(data.tone)">
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
								:class="
									data.empty
										? 'relative flex h-[87px] w-[212px] flex-col overflow-hidden rounded-[10px] border border-dashed border-outline-gray-3 bg-surface-base shadow-none transition-all'
										: 'w-[252px] text-left focus-visible:outline-none'
								"
								:tabindex="readonly ? -1 : 0"
								:role="readonly ? undefined : 'button'"
								:aria-label="nodeLabel(data)"
								@click.stop="selectNode(id)"
								@keydown.enter.prevent="pressNode"
								@keydown.space.prevent="pressNode"
							>
								<template v-if="data.empty">
									<div
										class="flex h-[47px] shrink-0 items-center gap-1.5 border-b border-outline-gray-3 px-2"
									>
										<div
											class="min-w-0 flex-1 truncate text-center text-base font-medium text-ink-gray-9"
										>
											{{ data.label }}
										</div>
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
								</template>
								<template v-else>
									<div class="automation-canvas-tab">
										<span class="automation-canvas-hair" />
										<Icon
											v-if="data.icon"
											:icon="data.icon"
											class="size-3 shrink-0"
										/>
										<span class="truncate">{{ data.kicker }}</span>
									</div>
									<div class="automation-canvas-card">
										<div class="px-3 py-2.5">
											<div
												class="truncate text-[14px] font-semibold leading-5 text-ink-gray-9"
											>
												{{ data.label }}
											</div>
											<div
												class="truncate text-xs leading-4 text-ink-gray-5"
											>
												{{ data.detail || "\u00a0" }}
											</div>
										</div>
										<div class="automation-canvas-foot">
											<Tooltip
												:text="data.issue?.message || ''"
												:disabled="!data.issue"
											>
												<span class="flex items-center gap-1.5">
													<span
														:key="nodeState(data).key"
														class="automation-canvas-dot"
													/>
													<span class="automation-canvas-status">
														{{ translate(nodeState(data).label) }}
													</span>
												</span>
											</Tooltip>
											<Badge
												v-if="data.run?.forced"
												:label="translate('Forced')"
												theme="amber"
												variant="subtle"
												size="sm"
											/>
											<span v-else class="tabular-nums text-ink-gray-4">
												{{ formatDuration(data.run?.durationMs) }}
											</span>
										</div>
									</div>
								</template>
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
						class="automation-canvas-add nodrag flex translate-y-[10.5px] items-center"
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
					v-if="data.run?.retryArms?.length"
					class="automation-canvas-add nodrag absolute left-0 top-[calc(100%+8px)] flex gap-1.5"
					@click.stop
				>
					<Button
						v-for="arm in data.run.retryArms"
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
					class="automation-canvas-add nodrag absolute left-[calc(100%+12px)] flex -translate-y-1/2 flex-col gap-1.5"
					:class="armsPosition(data)"
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
import { Badge, Button, Icon, Tooltip } from "frappe-ui";
import { computed, getCurrentInstance, nextTick, ref, watch } from "vue";
import AutomationCanvasPicker from "./AutomationCanvasPicker.vue";
import type {
	AutomationCanvasEmits,
	AutomationCanvasExposed,
	AutomationCanvasNodeData,
	AutomationCanvasProps,
	AutomationCanvasStatus,
	AutomationCanvasTone,
} from "./types";

const props = withDefaults(defineProps<AutomationCanvasProps>(), {
	selectedId: "",
	startOptions: () => [],
	blockOptions: () => [],
	readonly: false,
});
const emit = defineEmits<AutomationCanvasEmits>();
defineSlots<{
	/** Extra controls before the zoom buttons, e.g. undo and redo. */
	toolbar?(props: { selectedId: string }): unknown;
}>();

// A trial run's outcome wins over how the node is set up.
const RUN_STATES: Record<AutomationCanvasStatus, [string, string]> = {
	running: ["running", "Running"],
	Success: ["done", "Done"],
	Skipped: ["skipped", "Skipped"],
	Failed: ["failed", "Failed"],
	Waiting: ["waiting", "Waiting"],
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
	if (!from) return;
	const to = { ...node.position };
	moved.value = { ...moved.value, [node.id]: { from, to } };
	emit("move", { nodeId: node.id, position: to });
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

/** `nodrag` because dragging swallows the click that opens the start picker. */
function blockClasses(id: string, data: AutomationCanvasNodeData) {
	if (data.empty) return ["relative w-[212px] shrink-0", { nodrag: picksStart(data) }];
	return [
		"automation-canvas-block relative w-[252px] shrink-0",
		`is-${nodeState(data).key}`,
		{
			"is-selected": !props.readonly && props.selectedId === id,
			nodrag: picksStart(data),
			"opacity-[0.65]": data.dimmed,
		},
	];
}

function nodeState(data: AutomationCanvasNodeData) {
	const [key, label] = data.run ? RUN_STATES[data.run.status] : setupState(data);
	return { key, label };
}

function setupState(data: AutomationCanvasNodeData): [string, string] {
	if (data.issue?.level === "error") return ["error", "Has errors"];
	if (data.issue) return ["incomplete", "Needs setup"];
	return ["ready", "Ready"];
}

/** The CSS vars a block reads its identity colour from. */
function hueVars(tone: AutomationCanvasTone = "gray") {
	return {
		"--hue-line": `var(--outline-${tone}-3)`,
		"--hue-ink": `var(--ink-${tone}-7)`,
		"--hue-dot": `var(--ink-${tone}-6)`,
	};
}

function formatDuration(ms?: number) {
	if (ms === undefined || ms === null) return "";
	return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** The status dot and tooltip are visual only, so the label carries the run result and issue too. */
function nodeLabel(data: AutomationCanvasNodeData) {
	const parts = [`${data.kicker}: ${data.label}`];
	if (data.run) parts.push(translate(RUN_STATES[data.run.status][1]));
	if (data.issue) parts.push(data.issue.message);
	return parts.join(". ");
}

/** A lone open arm steps off the port, so it never sits on the filled arm's edge. */
function armsPosition(data: AutomationCanvasNodeData) {
	const lone = data.arms?.length === 1 && !data.canContinue ? data.arms[0].key : null;
	if (lone === "Else") return "top-[calc(50%+34.5px)]";
	if (lone) return "top-[calc(50%-13.5px)]";
	return "top-[calc(50%+10.5px)]";
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

.automation-canvas :deep(.automation-canvas-block) {
	--line: var(--outline-gray-2);
	--fill: var(--surface-gray-1);
	filter: drop-shadow(0 1px 1px rgb(0 0 0 / 0.12)) drop-shadow(0 4px 8px rgb(0 0 0 / 0.06));
	transition: transform 180ms cubic-bezier(0.2, 0.8, 0.2, 1), filter 180ms, opacity 180ms;
}

.automation-canvas :deep(.automation-canvas-block:hover) {
	--line: var(--outline-gray-3);
	transform: translateY(-1px);
}

.automation-canvas :deep(.automation-canvas-block:has(:focus-visible)) {
	--line: var(--hue-line);
}

.automation-canvas :deep(.automation-canvas-tab) {
	position: relative;
	z-index: 1;
	display: flex;
	width: fit-content;
	max-width: calc(100% - 40px);
	align-items: center;
	gap: 5px;
	height: 22px;
	margin: 0 0 -1px 20px;
	padding: 0 9px;
	font-size: 11px;
	font-weight: 500;
	color: var(--hue-ink);
	background: var(--fill);
	border: 1px solid var(--line);
	border-bottom: 0;
	border-radius: 7px 7px 0 0;
	transition: border-color 150ms;
}

.automation-canvas :deep(.automation-canvas-tab::before),
.automation-canvas :deep(.automation-canvas-tab::after) {
	content: "";
	position: absolute;
	bottom: 0;
	width: 10px;
	height: 10px;
}

/* Concave corners where the tab flows into the card's top edge. */
.automation-canvas :deep(.automation-canvas-tab::before) {
	left: -10px;
	background: radial-gradient(
		circle at 0 0,
		transparent 8.6px,
		var(--line) 9px,
		var(--line) 9.6px,
		var(--fill) 10px
	);
}

.automation-canvas :deep(.automation-canvas-tab::after) {
	right: -10px;
	background: radial-gradient(
		circle at 100% 0,
		transparent 8.6px,
		var(--line) 9px,
		var(--line) 9.6px,
		var(--fill) 10px
	);
}

.automation-canvas :deep(.automation-canvas-hair) {
	position: absolute;
	top: -1px;
	left: 6px;
	right: 6px;
	height: 2px;
	border-radius: 0 0 2px 2px;
	background: var(--hue-dot);
}

.automation-canvas :deep(.automation-canvas-card) {
	position: relative;
	border-radius: 10px;
	background: var(--fill);
	border: 1px solid var(--line);
	transition: border-color 150ms;
}

.automation-canvas :deep(.automation-canvas-foot) {
	position: relative;
	display: flex;
	height: 29px;
	align-items: center;
	justify-content: space-between;
	padding: 0 12px;
	border-top: 1px dashed var(--outline-gray-2);
	font-size: 11px;
	color: var(--ink-gray-6);
}

.automation-canvas :deep(.automation-canvas-dot) {
	width: 6px;
	height: 6px;
	border-radius: 99px;
	background: var(--ink-gray-4);
	animation: automation-canvas-pop 320ms cubic-bezier(0.3, 1.6, 0.5, 1);
}

.automation-canvas :deep(.is-done .automation-canvas-dot) {
	background: var(--ink-green-6);
}

.automation-canvas :deep(.is-failed .automation-canvas-dot),
.automation-canvas :deep(.is-error .automation-canvas-dot) {
	background: var(--ink-red-6);
}

.automation-canvas :deep(.is-waiting .automation-canvas-dot) {
	background: var(--ink-amber-6);
}

.automation-canvas :deep(.automation-canvas-block.is-failed),
.automation-canvas :deep(.automation-canvas-block.is-error) {
	--line: var(--outline-red-2);
}

.automation-canvas :deep(.automation-canvas-block.is-selected) {
	--line: var(--hue-line);
	filter: drop-shadow(0 0 0.5px var(--hue-line))
		drop-shadow(0 2px 5px color-mix(in oklch, var(--hue-dot) 14%, transparent));
}

.automation-canvas :deep(.is-incomplete .automation-canvas-card) {
	border-style: dashed;
}

.automation-canvas :deep(.automation-canvas-block.is-incomplete) {
	--line: var(--outline-amber-3);
}

.automation-canvas :deep(.is-incomplete .automation-canvas-dot) {
	background: var(--ink-amber-6);
	animation: automation-canvas-breathe 2.4s ease-in-out infinite;
}

.automation-canvas :deep(.is-running .automation-canvas-dot) {
	background: var(--hue-dot);
	animation: automation-canvas-ping 1.4s ease-out infinite;
}

.automation-canvas :deep(.is-running .automation-canvas-foot::before) {
	content: "";
	position: absolute;
	top: -1px;
	left: 0;
	right: 0;
	height: 1px;
	background: linear-gradient(90deg, transparent, var(--hue-dot), transparent) no-repeat;
	background-size: 35% 100%;
	animation: automation-canvas-sweep 1.8s ease-in-out infinite;
}

.automation-canvas :deep(.is-running .automation-canvas-status) {
	color: transparent;
	background: linear-gradient(
		90deg,
		var(--ink-gray-6) 30%,
		var(--ink-gray-9) 50%,
		var(--ink-gray-6) 70%
	);
	background-size: 250% 100%;
	-webkit-background-clip: text;
	background-clip: text;
	animation: automation-canvas-shimmer 1.8s linear infinite;
}

/* vue-flow positions handles with transform, so grow them by size instead. */
.automation-canvas :deep(.automation-canvas-port) {
	z-index: 20 !important;
	top: calc(50% + 10.5px);
	width: 9px !important;
	min-width: 0 !important;
	height: 9px !important;
	min-height: 0 !important;
	border-radius: 99px;
	border: 1.5px solid var(--outline-gray-4) !important;
	background: var(--surface-base) !important;
	opacity: 1 !important;
	visibility: visible !important;
	transition: width 150ms, height 150ms, border-color 150ms;
}

.automation-canvas :deep(.automation-canvas-block:hover .automation-canvas-port),
.automation-canvas :deep(.automation-canvas-block.is-selected .automation-canvas-port) {
	width: 11px !important;
	height: 11px !important;
	border-color: var(--hue-dot) !important;
}

@keyframes automation-canvas-pop {
	from {
		transform: scale(0.2);
	}
}

@keyframes automation-canvas-ping {
	from {
		box-shadow: 0 0 0 0 var(--hue-line);
	}
	to {
		box-shadow: 0 0 0 5px transparent;
	}
}

@keyframes automation-canvas-sweep {
	from {
		background-position: -50% 0;
	}
	to {
		background-position: 150% 0;
	}
}

@keyframes automation-canvas-shimmer {
	from {
		background-position: 100% 0;
	}
	to {
		background-position: -100% 0;
	}
}

@keyframes automation-canvas-breathe {
	50% {
		opacity: 0.35;
	}
}

@media (prefers-reduced-motion: reduce) {
	.automation-canvas :deep(.automation-canvas-block),
	.automation-canvas :deep(.automation-canvas-block *) {
		animation: none !important;
		transition: none !important;
	}
}

.automation-canvas :deep(.vue-flow__edge-path) {
	stroke: var(--ink-gray-6);
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

<style>
/* A faint black shadow reads as nothing on the dark canvas. */
[data-theme="dark"] .automation-canvas .automation-canvas-block:not(.is-selected) {
	filter: drop-shadow(0 1px 1px rgb(0 0 0 / 0.5)) drop-shadow(0 6px 12px rgb(0 0 0 / 0.35));
}
</style>

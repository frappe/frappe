<template>
	<div class="flex min-h-screen flex-col gap-4 bg-surface-gray-1 p-6">
		<div class="flex flex-wrap items-end gap-3">
			<Select v-model="scenario" label="Canvas state" :options="scenarioOptions" />
			<Select v-model="width" label="Container width" :options="widthOptions" />
		</div>
		<div
			class="overflow-hidden rounded border border-outline-gray-2 bg-surface-base transition-[width]"
			:style="{ width, height: '560px', maxWidth: '100%' }"
		>
			<AutomationCanvas
				:nodes="activeSample.nodes"
				:edges="activeSample.edges"
				:start-options="startOptions"
				:block-options="blockOptions"
				:selected-id="activeSample.selectedId"
				:readonly="activeSample.readonly"
				@select="lastEvent = `Selected ${$event}`"
				@pick-start="lastEvent = `Picked start ${$event}`"
				@add-node="lastEvent = `Add ${$event.value} after ${$event.afterId || 'start'}`"
			/>
		</div>
		<div class="text-p-sm text-ink-gray-6">{{ lastEvent || "Interact with the canvas" }}</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Select } from "frappe-ui";
import AutomationCanvas from "../AutomationCanvas.vue";
import type {
	AutomationCanvasEdge,
	AutomationCanvasNode,
	AutomationCanvasOptionGroup,
} from "../types";

interface Sample {
	nodes: AutomationCanvasNode[];
	edges: AutomationCanvasEdge[];
	selectedId?: string;
	readonly?: boolean;
}

const scenario = ref("empty");
const width = ref("960px");
const lastEvent = ref("");
const scenarioOptions = [
	{ label: "Empty start", value: "empty" },
	{ label: "Linear flow", value: "linear" },
	{ label: "Branched with empty arm", value: "branched" },
	{ label: "Selected node", value: "selected" },
	{ label: "Error node", value: "error" },
	{ label: "Read-only flow", value: "readonly" },
];
const widthOptions = [
	{ label: "Wide · 960 px", value: "960px" },
	{ label: "Narrow · 420 px", value: "420px" },
];

const startOptions: AutomationCanvasOptionGroup[] = [
	{
		group: "Records",
		options: [
			{
				value: "created",
				label: "Record is created",
				description: "Start whenever a new record is created.",
				icon: "lucide-list-plus",
			},
		],
	},
];
const blockOptions: AutomationCanvasOptionGroup[] = [
	{
		group: "Flow",
		options: [
			{
				value: "wait",
				label: "Wait",
				description: "Pause for a fixed time.",
				icon: "lucide-timer",
			},
			{
				value: "if",
				label: "If / Else",
				description: "Split into two arms.",
				icon: "lucide-git-branch",
			},
		],
	},
	{
		group: "Actions",
		options: [{ value: "email", label: "Send email", icon: "lucide-mail" }],
	},
];

const samples: Record<string, Sample> = {
	empty: { nodes: [emptyStart()], edges: [] },
	linear: linearSample(),
	branched: branchedSample(),
	selected: { ...linearSample(), selectedId: "wait" },
	error: errorSample(),
	readonly: { ...branchedSample(false), readonly: true },
};
const activeSample = computed(() => samples[scenario.value]);

function emptyStart(): AutomationCanvasNode {
	return node("start", 0, 0, {
		kicker: "Trigger",
		label: "Start from scratch",
		detail: "Pick initial trigger",
		tone: "trigger",
		start: true,
		empty: true,
	});
}

function startNode(): AutomationCanvasNode {
	return node("start", 0, 0, {
		kicker: "Trigger",
		label: "Record is created",
		detail: "on CRM Lead",
		icon: "lucide-play",
		tone: "trigger",
		start: true,
	});
}

function linearSample(): Sample {
	const nodes = [
		startNode(),
		node("email", 260, 0, actionData("Send welcome email")),
		node("wait", 520, 0, waitData(true)),
	];
	return { nodes, edges: chainEdges(nodes) };
}

function errorSample(): Sample {
	const sample = linearSample();
	sample.nodes[1] = node("email", 260, 0, { ...actionData("Configure action"), error: true });
	return sample;
}

function branchedSample(openArm = true): Sample {
	const start = startNode();
	const condition = node("condition", 260, 0, {
		kicker: "Condition",
		label: "Status is Qualified",
		icon: "lucide-git-branch",
		tone: "condition",
		branching: true,
		arms: openArm ? [{ key: "Else", label: "Otherwise" }] : [],
	});
	const action = node("qualified-email", 540, -90, actionData("Send qualified email", true));
	return {
		nodes: [start, condition, action],
		edges: [edge(start, condition), { ...edge(condition, action), label: "If yes" }],
	};
}

function actionData(label: string, terminal = false) {
	return { kicker: "Action", label, icon: "lucide-zap", tone: "action" as const, terminal };
}

function waitData(terminal = false) {
	return {
		kicker: "Wait",
		label: "Wait 2 hours",
		icon: "lucide-timer",
		tone: "wait" as const,
		terminal,
	};
}

function node(id: string, x: number, y: number, data: AutomationCanvasNode["data"]) {
	return { id, position: { x, y }, data };
}

function edge(source: AutomationCanvasNode, target: AutomationCanvasNode): AutomationCanvasEdge {
	return {
		id: `${source.id}->${target.id}`,
		source: source.id,
		target: target.id,
		animated: true,
	};
}

function chainEdges(nodes: AutomationCanvasNode[]) {
	return nodes.slice(1).map((target, index) => edge(nodes[index], target));
}
</script>
